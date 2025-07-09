from fastapi import (
    FastAPI, File, UploadFile,
    HTTPException
)
from fastapi.responses import StreamingResponse

from pathlib import Path
from typing import Iterator
import asyncio

import modules.extras as extras
import modules.constants as const

app = FastAPI(
    docs_url=None,
    redoc_url=None,
    openapi_url=None
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
        
        with open(filename, 'wb') as buffer:
            while content := await file.read(1_024):
                buffer.write(content)

            print(f"Uploaded a file of size: {buffer.tell():_} bytes")

        return const.Result(
            filename = filename.name,
            status = "saved",
            reason =  None
        )
    
    '''
        * So far this uploads a file with the correct suffix.
        * Should add salting in case of duplicate files. 

    '''

@app.post("/upload")
async def upload_files(files: list[UploadFile] = File(...)):
    sem = asyncio.Semaphore(3)

    tasks = [
        handle_file(file, sem)
        for file in files
    ]

    results = await asyncio.gather(*tasks)

    return {
        "results": results
    }

@app.get("/attachments/{file_id}")
async def serve_attachment(file_id: str):
    file = Path(file_id)
    target_dir = extras.get_target_dir(file.suffix)

    if not target_dir:
        raise HTTPException(
            status_code=404,
            detail=fr"File '{file}' not found"
        ) 

    file = target_dir / file.name
    print(file)

    if not file.is_file():
        raise HTTPException(
            status_code=404,
            detail="File not found"
        )
    
    def iterfile() -> Iterator[bytes]:
        with file.open("rb") as f:
            yield from f

    return StreamingResponse(
        iterfile(),
        media_type=const.MEDIA_TYPE_MAP.get(
            file.suffix, "application/octet-stream"
        )
    )
