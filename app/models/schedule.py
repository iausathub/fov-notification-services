from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.observation import Observation


class Schedule(Base):
    """Observatory observation schedule.

    One active schedule per observatory. When a new schedule arrives:
    1. Delete only SCHEDULED observations (future, replaceable)
    2. ARCHIVED observations remain untouched (permanent history)
    3. Replace schedule record with new data
    """

    __tablename__ = "schedules"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    observatory_name: Mapped[str] = mapped_column(
        String(255), nullable=False, unique=True, index=True
    )
    observatory_latitude: Mapped[float] = mapped_column(nullable=False)
    observatory_longitude: Mapped[float] = mapped_column(nullable=False)
    observatory_elevation: Mapped[float] = mapped_column(nullable=False)
    source: Mapped[str] = mapped_column(
        String(255), nullable=False
    )  # API endpoint or manual upload
    schedule_start: Mapped[datetime] = mapped_column(
        nullable=False
    )  # First observation start
    schedule_end: Mapped[datetime] = mapped_column(
        nullable=False
    )  # Last observation end
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime | None] = mapped_column(
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    observations: Mapped[list["Observation"]] = relationship(
        "Observation", back_populates="schedule"
    )
