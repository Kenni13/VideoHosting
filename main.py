from fastapi import FastAPI, File, UploadFile
from pydantic import BaseModel

from pathlib import Path
from typing import Optional
import asyncio

import modules.extras as extras
import modules.constants as const

app = FastAPI(
    docs_url=None,
    redoc_url=None,
    openapi_url=None
)

result = Path("modules")
result.mkdir(exist_ok=True)

# test code
@app.get("/")
async def home():
    return {"Hello": "World"}

class Result(BaseModel):
    filename: str
    status: str
    reason: Optional[str]

#"Hello/Bo/HelloWorld.txt" -> Path("HelloWorld.txt")
def check_filename(filename: str | None) -> Path | None:
    if not filename: return None
    
    file: Path = Path(filename)
    
    name = file.stem
    suffix = file.suffix

    # I'm not boutta let myself screw everything up in the future. Better safe than sorry
    # If Its not a valid suffix then ur outta heere
    if not suffix in const.VIDEO_EXT or \
        not suffix in const.IMAGE_EXT:
        return None
    
    return Path(name + suffix)

#will handle files asynchronously
async def handle_file(file: UploadFile, sem: asyncio.Semaphore) -> Result:
    print(file.file.mode)
    async with sem:
        print(f"Handling file: {file.filename}")

        filename: Path | None = check_filename(file.filename)
        if not filename:
            print(f"{file.filename or '(none)'} was deported")
            return Result(
                filename = file.filename or "(none)",
                status = "rejected",
                reason = "missing or invalid filename"
            )
        
        print(f"Exporting to {const.IMAGES / filename}")
        with open(const.IMAGES / filename, 'wb') as buffer:
            while content := await file.read(1_024):
                buffer.write(content)

        return Result(
                      # the or won't happen but my linter says otherwise
            filename = file.filename or "(none)",
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

#class Item(BaseModel):
#    name: str
#    price: int
#    is_offer: bool | None = None
#
#@app.post("/items/")
#def create_item(item: Item):
#    return { "item": item }
#
#@app.get("/items/{item_id}")
#def read_item(item_id: int, q: str | None = None) -> dict[str, Any]:
#    return {"item_id": item_id, "q": q or "none"}

