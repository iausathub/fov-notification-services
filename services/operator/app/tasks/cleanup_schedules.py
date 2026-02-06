import logging
from datetime import UTC, datetime

from database import SessionLocal
from models.observation import ObservationStatus
from models.schedule import Schedule

logger = logging.getLogger(__name__)


async def cleanup_schedules() -> None:
    """Cleanup schedules that are no longer needed."""
    db = SessionLocal()
    try:
        # Current time as timezone-aware UTC
        now_utc = datetime.now(UTC)

        # For all schedules, move past observations to ARCHIVED status
        for schedule in db.query(Schedule).all():
            for observation in schedule.observations:
                if observation.start_time < now_utc:
                    observation.status = ObservationStatus.ARCHIVED
                    observation.archived_at = now_utc
                    logger.info(
                        f"Moved observation {observation.id} to ARCHIVED status"
                    )

        db.commit()
    finally:
        db.close()
