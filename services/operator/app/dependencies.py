"""Shared dependencies for FastAPI endpoints."""

from datetime import UTC, datetime, timedelta
from typing import Annotated

from auth import MAX_API_KEY_BYTES, hash_api_key, verify_key
from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.api_key import APIKey


async def get_current_user(
    db: Annotated[Session, Depends(get_db)],
    x_api_key: str = Header(..., description="API key for authentication"),
):
    # Reject oversized keys to prevent hashing very large strings.
    if len(x_api_key.encode("utf-8")) > MAX_API_KEY_BYTES:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
        )
    key_hash = hash_api_key(x_api_key)
    api_key = db.query(APIKey).filter(APIKey.key_hash == key_hash).first()
    stored_hash = api_key.key_hash if api_key else hash_api_key("")
    if not verify_key(x_api_key, stored_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
        )
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
        )
    if api_key.revoked_at:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key has been revoked",
        )

    expiration_cutoff = datetime.now(UTC) - timedelta(days=90)
    if api_key.created_at < expiration_cutoff:
        if not api_key.revoked_at:
            api_key.revoked_at = datetime.now(UTC)
            db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key has expired",
        )

    return api_key.id
