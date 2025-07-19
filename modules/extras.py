import orjson
import aiofiles

import secrets
from typing import Iterator
from pathlib import Path

import modules.constants as const

def generate_unique_name(size: int = 16) -> str:
    return secrets.token_hex(size)

#returns whether file should go in Videos/Images or none 
def get_target_dir(suffix: str) -> Path | None:
    if suffix in const.VIDEO_EXT:
        return const.VIDEOS
    elif suffix in const.IMAGE_EXT:
        return const.IMAGES
    
    return None

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

def attempt_delete(file: Path) -> tuple[bool, str | None]:
    target = get_target_dir(file.suffix)
    if not target:
        return False, f"Unsupported file type: '{file}'"
    
    file = target / file
    if not file.is_file():
        return False, "File is not found"
    
    file.unlink()
    return True, None 

async def create_metadata(metadata: const.Metadata):
    async with aiofiles.open(const.JSONS / metadata['name'], "wb") as file:
        await file.write(orjson.dumps(metadata))

#"Hello/Bo/HelloWorld.txt" -> Path("HelloWorld.txt")
#def check_filename(filename: str) -> Path | None:
#    
#    file: Path = Path(filename)
#    suffix: str = file.suffix.lower()
#
#    target_dir: Path | None = get_target_dir(suffix)
#    if not target_dir:
#        return None
#    
#    candidate = target_dir / file.name
#    if not candidate.exists():
#        return candidate
#    
#    while True:
#        name = f"{file.stem}_{generate_unique_name(8)}{suffix}"
#        candidate = target_dir / name
#
#        if not candidate.exists():
#            return candidate

#def _light_clean():
#    files: list[Path] = list(const.JSONS.iterdir())
#
#    seen: set[Path] = set()
#    
#    for file in const.JSONS.iterdir():
#        if not file in seen:
#            seen.add(file)
#            continue
#
#        try:
#            file.unlink(missing_ok=True)
#        except Exception as e:
#            const.logger.error(f"Failed to delete {file} reason: {e}")
#
#     
#
#def _heavy_clean():
#    for file in const.JSONS.iterdir():
#        try:
#            file.unlink(missing_ok=True)
#        except Exception as e:
#            const.logger.error(f"Failed to delete {file} reason: {e}")
#
#def clean(light: bool=True):
#    if light:
#        _light_clean()
#    else:
#        _heavy_clean()

'''
    * Create a clean up function
    * It can lightly clean up
        * delete duplicates
        * delete oldest (until we cleared 300MB of space)

    * It can heavily clean up
        * delete all of the images/videos
'''
