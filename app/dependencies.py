"""Shared dependencies for FastAPI endpoints."""

from fastapi import Header, HTTPException, status


async def get_current_user(
    x_api_key: str = Header(..., description="API key for authentication")
):
    # TODO: Implement real authentication (placeholder for now)

    if not x_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API key",
        )
    # Accept any non-empty key for now
    return {"api_key": x_api_key}
