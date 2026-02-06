from datetime import UTC, datetime

from sqlalchemy import Column, DateTime, Float, Integer, String
from sqlalchemy.orm import relationship

from database import Base


class Schedule(Base):
    """Observatory observation schedule.

    One active schedule per observatory. When a new schedule arrives:
    1. Delete only SCHEDULED observations (future, replaceable)
    2. ARCHIVED observations remain untouched (permanent history)
    3. Replace schedule record with new data
    """

    __tablename__ = "schedules"

    id = Column(Integer, primary_key=True, index=True)
    observatory_name = Column(String(255), nullable=False, unique=True, index=True)
    observatory_latitude = Column(Float, nullable=False)
    observatory_longitude = Column(Float, nullable=False)
    observatory_elevation = Column(Float, nullable=False)
    source = Column(String(255), nullable=False)  # API endpoint or manual upload
    schedule_start = Column(
        DateTime(timezone=True), nullable=False
    )  # First observation start
    schedule_end = Column(
        DateTime(timezone=True), nullable=False
    )  # Last observation end
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    observations = relationship("Observation", back_populates="schedule")
