import logging
from datetime import UTC, datetime

from app.database import SessionLocal
from app.models.observation import ObservationStatus
from app.models.schedule import Schedule

logger = logging.getLogger(__name__)


async def cleanup_schedules() -> None:
    """Cleanup schedules that are no longer needed."""
    db = SessionLocal()
    try:
        # Current time as timezone-aware UTC
        now_utc = datetime.now(UTC)

        # For all schedules, move past observations to ARCHIVED status
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
