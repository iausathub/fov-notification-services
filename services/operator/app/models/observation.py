from __future__ import annotations

import enum
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.schedule import Schedule


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

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    schedule_id: Mapped[int | None] = mapped_column(
        ForeignKey("schedules.id"), nullable=True
    )  # NULL for archived
    observatory_name: Mapped[str] = mapped_column(
        String(255), nullable=False, index=True
    )  # Denormalized for use in archive queries
    status: Mapped[ObservationStatus] = mapped_column(
        Enum(ObservationStatus),
        default=ObservationStatus.SCHEDULED,
        nullable=False,
        index=True,
    )

    target_name: Mapped[str | None] = mapped_column(String(255), index=True)
    ra: Mapped[float | None] = mapped_column(Float)  # Right ascension (degrees)
    dec: Mapped[float | None] = mapped_column(Float)  # Declination (degrees)
    start_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    end_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    fov_radius: Mapped[float | None] = mapped_column(Float)  # Field of view radius
    on_sky_angle: Mapped[float | None] = mapped_column(Float)
    instrument: Mapped[str | None] = mapped_column(String(255))

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    archived_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    schedule: Mapped[Schedule | None] = relationship(
        "Schedule", back_populates="observations"
    )
