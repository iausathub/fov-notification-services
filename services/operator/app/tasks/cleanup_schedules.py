import asyncio
import logging
from datetime import UTC, datetime
from typing import Any, cast

from sqlalchemy import update
from sqlalchemy.engine import CursorResult

from app.database import SessionLocal
from app.models.observation import Observation, ObservationStatus

logger = logging.getLogger(__name__)


def _cleanup_schedules_sync() -> None:
    db = SessionLocal()
    try:
        now_utc = datetime.now(UTC)

        result = cast(
            CursorResult[Any],
            db.execute(
                update(Observation)
                .where(Observation.start_time < now_utc)
                .values(status=ObservationStatus.ARCHIVED, archived_at=now_utc)
            ),
        )
        db.commit()
        archived = result.rowcount if result.rowcount is not None else 0
        logger.info("Moved %s observations to ARCHIVED status", archived)
    finally:
        db.close()


async def cleanup_schedules() -> None:
    """Cleanup schedules that are no longer needed."""
    await asyncio.to_thread(_cleanup_schedules_sync)
