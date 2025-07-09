from pathlib import Path
import logging

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
_ASSETS = Path("Assets")

#used folders
VIDEOS = _ASSETS / "Videos"
IMAGES = _ASSETS / "Images"
JSONS = _ASSETS / "Json"

#supported image/video extensions
VIDEO_EXT: set[str] = { '.mp4', 'webm', '.mov' }
IMAGE_EXT: set[str] = { '.jpg', '.jpeg', '.png', '.gif', '.webp', '.avif' }


#make sure folders are created
_ASSETS.mkdir(exist_ok=True)

VIDEOS.mkdir(exist_ok=True)
IMAGES.mkdir(exist_ok=True)
JSONS.mkdir(exist_ok=True)
