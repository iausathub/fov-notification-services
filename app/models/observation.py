from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Enum
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
import enum

from app.database import Base


class ObservationStatus(enum.Enum):
    SCHEDULED = "scheduled"
    ARCHIVED = "archived"


class Observation(Base):
    """Individual observation within a schedule.

    Lifecycle:
    - SCHEDULED: Future observation, can be replaced if schedule updates before obs time
    - ARCHIVED: Observation time has passed, permanent record of most recent data
    (never deleted)

    Archive behavior:
    - When observation end_time passes → status becomes ARCHIVED (permanent)
    - When schedule updates, only SCHEDULED observations are replaced
    - ARCHIVED observations accumulate into continuous history

    The archive represents "what was the most current plan at observation time"
    for each observatory, forming a continuous historical record.
    """

    __tablename__ = "observations"

    id = Column(Integer, primary_key=True, index=True)
    schedule_id = Column(
        Integer, ForeignKey("schedules.id"), nullable=True
    )  # NULL once archived
    observatory_name = Column(
        String(255), nullable=False, index=True
    )  # Denormalized for archive queries
    status = Column(
        Enum(ObservationStatus),
        default=ObservationStatus.SCHEDULED,
        nullable=False,
        index=True,
    )

    target_name = Column(String(255), index=True)
    ra = Column(Float)  # Right ascension (degrees)
    dec = Column(Float)  # Declination (degrees)
    start_time = Column(DateTime, nullable=False, index=True)
    end_time = Column(DateTime, nullable=False)
    fov_radius = Column(Float)  # Field of view radius (degrees)
    on_sky_angle = Column(Float)
    instrument = Column(String(255))

    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    archived_at = Column(DateTime, nullable=True)

    schedule = relationship("Schedule", back_populates="observations")
