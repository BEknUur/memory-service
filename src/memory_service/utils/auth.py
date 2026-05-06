#python imports
from typing import Annotated

#third-party imports
from fastapi import Header, HTTPException, status

#project imports
from memory_service.config import get_settings


async def require_auth(authorization: Annotated[str | None, Header()] = None) -> None:
    token = get_settings().memory_auth_token
    if not token:
        return

    expected = f"Bearer {token}"
    if authorization != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing authorization token",
        )
