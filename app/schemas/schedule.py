"""Pydantic schemas for schedule and observation endpoints."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ObservationResponse(BaseModel):
    """Observation response schema."""

    model_config = ConfigDict(from_attributes=True)

    ra: float | None = Field(description="Right ascension in degrees")
    dec: float | None = Field(description="Declination in degrees")
    start_time: datetime = Field(description="Observation start time (UTC)")
    end_time: datetime = Field(description="Observation end time (UTC)")
    fov_radius: float | None = Field(description="Field of view radius in degrees")
    on_sky_angle: float | None = Field(description="???")


class ScheduleResponse(BaseModel):
    """Schedule response schema with observations."""

    model_config = ConfigDict(from_attributes=True)

    observatory_name: str = Field(description="Name of the observatory")
    observatory_latitude: float = Field(description="Observatory latitude in degrees")
    observatory_longitude: float = Field(description="Observatory longitude in degrees")
    observatory_elevation: float = Field(description="Observatory elevation in meters")
    schedule_start: datetime = Field(description="Start of schedule window (UTC)")
    schedule_end: datetime = Field(description="End of schedule window (UTC)")
    created_at: datetime = Field(description="When the schedule was first retrieved")
    updated_at: datetime | None = Field(
        description="When the schedule was last updated"
    )
    observations: list[ObservationResponse] = Field(
        description="List of scheduled observations"
    )


class MultipleScheduleResponse(BaseModel):
    """Multiple schedule response schema with schedules."""

    model_config = ConfigDict(from_attributes=True)

    schedules: list[ScheduleResponse]
