"""Pydantic schemas for schedule and observation endpoints."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ObservationResponse(BaseModel):
    """Observation response schema."""

    model_config = ConfigDict(from_attributes=True)

    ra: float | None
    dec: float | None
    start_time: datetime
    end_time: datetime
    fov_radius: float | None
    on_sky_angle: float | None


class ScheduleResponse(BaseModel):
    """Schedule response schema with observations."""

    model_config = ConfigDict(from_attributes=True)

    observatory_name: str
    observatory_latitude: float
    observatory_longitude: float
    observatory_elevation: float
    schedule_start: datetime
    schedule_end: datetime
    created_at: datetime
    updated_at: datetime | None
    observations: list[ObservationResponse]


class MultipleScheduleResponse(BaseModel):
    """Multiple schedule response schema with schedules."""

    model_config = ConfigDict(from_attributes=True)

    schedules: list[ScheduleResponse]


class HealpixScheduleResponse(BaseModel):
    """Healpix schedule response schema."""

    model_config = ConfigDict(from_attributes=True)

    observatory_name: str
    observatory_latitude: float
    observatory_longitude: float
    observatory_elevation: float
    schedule_start: datetime
    schedule_end: datetime
    created_at: datetime
    updated_at: datetime | None
    n_side: int
    ordering: str
    pixel_indices: list[int]


class MultipleHealpixScheduleResponse(BaseModel):
    """Multiple schedule response schema with HEALPix schedules."""

    model_config = ConfigDict(from_attributes=True)

    schedules: list[HealpixScheduleResponse]
