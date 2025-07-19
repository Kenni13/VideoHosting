from pydantic import BaseModel

from pathlib import Path
from typing import TypedDict
from typing import Optional

import logging
import os
import enum
import asyncio

'''
    * These will be constants that are used by the program
'''

#ain't no way I'm boutta print. Need a logger
logger = logging.getLogger("server_logger")
logger.setLevel(logging.DEBUG)

#set up logging handlers
if not logger.handlers:
    #I'll keep formatters the same for both for simplicity
    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")

    file_handler = logging.FileHandler("server.log")
    file_handler.setFormatter(formatter)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)

#a private folder containing everything (video/image/json folders)
_ASSETS = Path(os.getenv("ASSETS_DIR", "excluded/Assets"))

#used folders
VIDEOS = _ASSETS / "Videos"
IMAGES = _ASSETS / "Images"
JSONS = _ASSETS / "JSONS"
TEMP = _ASSETS / "TEMP"

#supported image/video extensions
VIDEO_EXT: set[str] = { '.mp4', '.webm', '.mov' }
IMAGE_EXT: set[str] = { '.jpg', '.jpeg', '.png', '.gif', '.webp', '.avif' }
MEDIA_TYPE_MAP = {
    '.mp4': 'video/mp4',
    '.webm': 'video/webm',
    '.mov': 'video/quicktime',
    '.jpg': 'image/jpeg',
    '.jpeg': 'image/jpeg',
    '.png': 'image/png',
    '.gif': 'image/gif',
    '.webp': 'image/webp',
    '.avif': 'image/avif'
}

#make sure folders are created
_ASSETS.mkdir(exist_ok=True)

VIDEOS.mkdir(exist_ok=True)
IMAGES.mkdir(exist_ok=True)
JSONS .mkdir(exist_ok=True)
TEMP  .mkdir(exist_ok=True)

#thread limiter
Semaphore = asyncio.Semaphore(3)

class Status(enum.Enum):
    REJECTED = "rejected"
    ACCEPTED = "accepted"
    DUPLICATE = "duplicate"

# will be returned by "/upload"
class Result(BaseModel):
    filename: str | Path
    status: Status
    reason: Optional[str]

# file metadata
class Metadata(TypedDict):
    name: str 
    original: str
    uploaded_at: str
    size_bytes: int
    content_type: str

CHUNK_SIZE = pow(1024, 2) # 1 MiB per chunk