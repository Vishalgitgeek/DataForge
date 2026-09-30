import hashlib
import secrets
from base64 import urlsafe_b64encode

REFRESH_TOKEN_BYTES = 32


def generate_refresh_token() -> str:
    token_bytes = secrets.token_bytes(REFRESH_TOKEN_BYTES)
    return urlsafe_b64encode(token_bytes).rstrip(b"=").decode("ascii")


def hash_refresh_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("ascii")).hexdigest()
