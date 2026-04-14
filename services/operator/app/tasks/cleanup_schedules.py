import asyncio
import logging
from datetime import UTC, datetime

from app.database import SessionLocal
from app.models.observation import ObservationStatus
from app.models.schedule import Schedule

logger = logging.getLogger(__name__)


def _cleanup_schedules_sync() -> None:
    db = SessionLocal()
    try:
        now_utc = datetime.now(UTC)
        archived_observations = 0
        for schedule in db.query(Schedule).all():
            for observation in schedule.observations:
                if observation.start_time < now_utc:
                    observation.status = ObservationStatus.ARCHIVED
                    observation.archived_at = now_utc
                    archived_observations += 1
        db.commit()
        logger.info(f"Moved {archived_observations} observations to ARCHIVED status")
    finally:
        db.close()


async def cleanup_schedules() -> None:
    """Cleanup schedules that are no longer needed."""
    await asyncio.to_thread(_cleanup_schedules_sync)
