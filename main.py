from fastapi import (
    FastAPI, File, UploadFile,
    HTTPException, Request, Header
)
from fastapi.responses import (
    StreamingResponse,
    FileResponse
)
from starlette.types import ExceptionHandler
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
import aiofiles

from pathlib import Path
from typing import Iterator, cast
import asyncio

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
    cast(ExceptionHandler, _rate_limit_exceeded_handler)
)

# test code
@app.get("/")
async def home():
    return {"Hello": "World"}

#"Hello/Bo/HelloWorld.txt" -> Path("HelloWorld.txt")
def check_filename(filename: str | None) -> Path | None:
    if not filename: return None
    
    file: Path = Path(filename)
    suffix: str = file.suffix.lower()

    target_dir: Path | None = extras.get_target_dir(suffix)
    if not target_dir:
        return None
    
    candidate = target_dir / file.name
    if not candidate.exists():
        return candidate
    
    while True:
        name = f"{file.stem}_{extras.generate_unique_name(8)}{suffix}"
        candidate = target_dir / name

        if not candidate.exists():
            return candidate
    

#will handle files asynchronously
# *hold on to the file size in the future*
async def handle_file(file: UploadFile, sem: asyncio.Semaphore) -> const.Result:
    async with sem:
        print(f"Handling file: {file.filename}")

        filename: Path | None = check_filename(file.filename)
        if not filename:
            return const.Result(
                filename = file.filename or "(none)",
                status = "rejected",
                reason = "missing or invalid filename"
            )
        
        async with aiofiles.open(filename, 'wb') as buffer:
            while content := await file.read(1_024):
                await buffer.write(content)

            print(f"Uploaded a file of size: {buffer.tell():_} bytes")

        return const.Result(
            filename = filename.name,
            status = "saved",
            reason =  None
        )
    
    '''
        * So far this uploads a file with the correct suffix.
        * Will add salting if there are duplicates
    '''

@app.post("/upload")
@limiter.limit("5/minute")  # type: ignore
async def upload_files(request: Request, files: list[UploadFile] = File(..., max_length=10)):
    sem = asyncio.Semaphore(3)

    tasks = [
        handle_file(file, sem)
        for file in files
    ]

    results = await asyncio.gather(*tasks)

    return {
        "results": results
    }

def handle_range(range: str):
    byte_range = range.strip().split('=')[-1]
    
    start_str, end_str = byte_range.split('-')

    start = int(start_str) if start_str else None
    end = int(end_str) if end_str else None

    if not (start and end):
        return None
    
    return start, end

def iterfile(path: Path, start_pos: int, end_pos: int) -> Iterator[bytes]:
    chunk_size = end_pos - start_pos + 1
    with path.open("rb") as file:
        file.seek(start_pos)
        remaining = chunk_size

        while remaining > 0:
            chunk = file.read(min(const.CHUNK_SIZE, remaining))

            if not chunk:
                break
            yield chunk
            remaining -= len(chunk)

@app.get("/attachments/{video_id}")
@limiter.limit("100/minute") # type:ignore
async def serve_video(
    request: Request,
    video_id: Path,
    range: str = Header(None, convert_underscores=False), # "Range"  header
    accept: str = Header("", alias="Accept")              # "Accept" header
) -> FileResponse | StreamingResponse:

    #file validation.
    target_dir = extras.get_target_dir(video_id.suffix)
    if not target_dir:
        raise HTTPException(
            status_code=404,
            detail=f"Unsupported file type: '{video_id}'"
        )

    file = target_dir / video_id
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
            headers={"Content-Disposition": f"attachment; filename=\"{file.name}\""}
        )

    # smart streaming
    file_size = file.stat().st_size
    start = 0
    end = file_size - 1

    if range:
        try:
            res = handle_range(range)
            if not res: raise Exception("E")
            start, end = res
        except Exception:
            start, end = 0, file_size - 1

    chunk_size = (end - start) + 1

    headers = {
        "Content-Range": f"bytes {start}-{end}/{file_size}",
        "Accept-Ranges": "bytes",
        "Content-Length": str(chunk_size),
        "Content-Type": const.MEDIA_TYPE_MAP.get(file.suffix, "application/octet-stream") 
    }

    status_code = 206 if range else 200
    return StreamingResponse(
        iterfile(file, start, end),
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
