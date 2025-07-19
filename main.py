from fastapi import (
    FastAPI, File, UploadFile,
    HTTPException, Request, Header
)
from fastapi.responses import (
    StreamingResponse,
    FileResponse
)
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
import aiofiles
import orjson

from pathlib import Path
from datetime import datetime, timezone
import hashlib
import asyncio
import secrets

import modules.extras as extras
import modules.constants as const

app = FastAPI(
    docs_url=None,
    redoc_url=None,
    openapi_url=None
)
limiter = Limiter(key_func=get_remote_address)

app.state.limiter = limiter
app.add_exception_handler(
    RateLimitExceeded,
    _rate_limit_exceeded_handler # type:ignore
)

@app.get("/")
async def home():
    return {"Hello": "World"}

#will handle files asynchronously
# *hold on to the file size in the future*
async def handle_file(file: UploadFile, sem: asyncio.Semaphore) -> const.Result:
    if file.filename is None:
        return const.Result(
            filename="(none)",
            status=const.Status.REJECTED,
            reason="missing filename"
        )

    async with sem:
        print(f"Handling file: {file.filename}")
        filename = Path(file.filename)
        target_dir = extras.get_target_dir(filename.suffix)
        if not target_dir:
            return const.Result(
               filename=file.filename or "(none)",
               status=const.Status.REJECTED,
               reason=f"Unsupported file type: '{file.filename}'"
           )

        # create a temporary file (so I don't have to load the contents into memory)
        # where are python temporary scopes when you need em?
        rfilename = secrets.token_hex(32)
        file_hash = hashlib.sha256()

        async with aiofiles.open(const.TEMP / rfilename, 'wb') as rbuffer:
            while content := await file.read(65536): # 64KB
                file_hash.update(content)
                await rbuffer.write(content)

            size: int = await rbuffer.tell()

        # now we check if file already exists using our hash
        hash_filename = target_dir / (file_hash.hexdigest() + filename.suffix)

        if hash_filename.is_file():

            try:
                (const.TEMP / rfilename).unlink(missing_ok=True)
            except Exception as e:
                const.logger.error(f"Failed to delete {rfilename} reason: {e}")

            return const.Result(
                filename=hash_filename.name,
                status=const.Status.DUPLICATE,
                reason=f"{hash_filename.name} is a duplicate file"
            )

        temp = const.TEMP / rfilename

        try:
            temp.rename(hash_filename)
        except Exception as e:
            const.logger.error(f"Failed to rename {rfilename} to {hash_filename.name}: {e}")

            # delete lingering files if it failed
            try:
                temp.unlink(missing_ok=True)
            except Exception as e:
                const.logger.error(f"Failed to delete {rfilename}")

            return const.Result (
                filename=file.filename,
                status=const.Status.REJECTED,
                reason="Failed to save file"
            )

        await extras.create_metadata(const.Metadata(
            name=hash_filename.with_suffix(".json").name,
            original=file.filename,
            uploaded_at=f'{datetime.now():%a %b %d %-I:%M %p}',
            size_bytes=size,
            content_type=const.MEDIA_TYPE_MAP.get(
                filename.suffix, "application/octet-stream"),
        ))

        print("Done!")

        return const.Result(
            filename=hash_filename.name,
            status=const.Status.ACCEPTED,
            reason= None
        )

@app.post("/upload")
@limiter.limit("5/minute")  # type: ignore
async def upload_files(request: Request, files: list[UploadFile] = File(..., max_length=10)):
    if len(files) > 5:
        raise HTTPException(
            status_code=413,
            detail=f"File limit is 5 but received {len(files)}"
        )

    tasks = [
        handle_file(file, const.Semaphore)
        for file in files
    ]

    results = await asyncio.gather(*tasks)

    return {
        "results": results
    }

@app.delete("/delete")
@limiter.limit("5/minute") #type:ignore
async def delete_files(request: Request, files: list[Path]):

    errors: list[str]  = []
    deleted: list[str] = []

    for file in files:
        result, err = extras.attempt_delete(file)

        if not result and err:
            errors.append(err)
        else:
            deleted.append(f'deleted {file.name}')

    return {
        "deleted": deleted,
        "errors": errors
    }

@app.get("/attachments/{file_id}")
@limiter.limit("100/minute") # type:ignore
async def serve_video(
    request: Request,
    file_id: Path,
    range: str = Header(None, convert_underscores=False), # "Range"  header
    accept: str = Header("", alias="Accept")              # "Accept" header
):
    #file validation.
    target_dir = extras.get_target_dir(file_id.suffix)
    if not target_dir:
        raise HTTPException(
            status_code=404,
            detail=f"File is not found"
        )

    file = target_dir / file_id.name
    if not file.is_file():
        raise HTTPException(
            status_code=404,
            detail=f"File is not found"
        )

    # decide whether we download or stream
    force_download = (
        "text/html" in accept.lower() and "video/" not in accept.lower()
    ) or request.query_params.get("download") == "1"

    if force_download:
        return FileResponse(
            path=file,
            media_type="application/octet-stream",
            filename=file.name,
            headers={
                "Content-Disposition": f"attachment; filename=\"{file.name}\"",

                # caching
                "Cache-Control": "public, max-age=86400, immutable",  # 1 day
                "ETag": f'"{file.stat().st_mtime_ns}"',
            }
        )

    # smart streaming
    file_size = file.stat().st_size
    start = 0
    end = file_size - 1

    if range:
        try:
            res = extras.handle_range(range)
            if not res: raise Exception("E")
            start, end = res
        except Exception:
            start, end = 0, file_size - 1

    chunk_size = (end - start) + 1
    file_stat = file.stat()
    file_size=  file_stat.st_size

    headers = {
        "Content-Range": f"bytes {start}-{end}/{file_size}",
        "Accept-Ranges": "bytes",
        "Content-Length": str(chunk_size),
        "Content-Type": const.MEDIA_TYPE_MAP.get(file.suffix, "application/octet-stream"),

        "Cache-Control": "public, max-age=86400, immutable",  # 1 day cache
        "ETag": f'"{file_stat.st_mtime_ns}"',
        "Last-Modified": datetime.fromtimestamp(
            file_stat.st_mtime, tz=timezone.utc
        ).strftime('%a, %d %b %Y %H:%M:%S GMT'),
    }

    status_code = 206 if range else 200
    return StreamingResponse(
        extras.iterfile(file, start, end),
        status_code=status_code,
        headers=headers
    )

@app.get("/list")
async def list_files():
    return {
        "Videos": [
            video.name
            for video in const.VIDEOS.iterdir()
        ],
        "Images": [
            image.name
            for image in const.IMAGES.iterdir()
        ]
    }

@app.get("/file/{file_id}")
async def list_file(file_id: Path) -> dict[str, str | int]:
    filename = const.JSONS / (file_id.stem + ".json")
    if not filename.is_file():
        raise HTTPException(
            status_code=404,
            detail=f"File {file_id} not found"
        )

    return orjson.loads(filename.read_text())