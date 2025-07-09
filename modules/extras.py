import secrets
import modules.constants as const

def generate_unique_name(size: int = 16) -> str:
    return secrets.token_hex(size)

#returns whether file should go in Videos/Images or none 
def get_target_dir(suffix: str) -> const.Path | None:
    if suffix in const.VIDEO_EXT:
        return const.VIDEOS
    elif suffix in const.IMAGE_EXT:
        return const.IMAGES
    
    return None