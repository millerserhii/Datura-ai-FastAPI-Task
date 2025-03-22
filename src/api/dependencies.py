from fastapi import Security
from fastapi.security import APIKeyHeader

from src.config import settings
from src.exceptions import AuthenticationError


API_KEY_HEADER = APIKeyHeader(name="Authorization", auto_error=False)
API_KEY_SECURITY = Security(API_KEY_HEADER)


async def get_api_key(api_key_header: str = API_KEY_SECURITY) -> str:
    """Validate API key from header."""
    if not api_key_header:
        raise AuthenticationError(detail="API key is missing")

    # Check if the header has the format "Bearer {token}"
    if api_key_header.startswith("Bearer "):
        token = api_key_header.replace("Bearer ", "")
    else:
        token = api_key_header

    # Validate the token - get the actual string value from SecretStr
    if token != settings.API_AUTH_TOKEN.get_secret_value():
        raise AuthenticationError(detail="Invalid API key")

    return token