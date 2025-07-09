import secrets

def generate_unique_name(size: int = 16) -> str:
    return secrets.token_hex(size)

x: dict[str, str | int] = {
    "name": "main.py",
    "timestamp": 101
}