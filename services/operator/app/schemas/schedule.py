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


class HealpixPixelDirection(BaseModel):
    """Direction of a single scheduled HEALPix pixel relative to the observatory.

    The direction is the pixel centre expressed in the observatory's local
    horizontal (AltAz) frame at ``time``. Because a fixed sky pixel's horizontal
    direction changes as the Earth rotates, each entry is tied to the time of the
    observation that scheduled it, and pixels are NOT deduplicated.
    """

    index: int
    time: datetime
    azimuth: float  # degrees, 0-360, measured from North towards East
    altitude: float  # degrees, -90 to +90 above the horizon


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
    radius: int | None
    # Populated only when the request sets include_direction=true. One entry per
    # (pixel, observation) pair, so this list is not deduplicated.
    pixel_directions: list[HealpixPixelDirection] | None = None


class MultipleHealpixScheduleResponse(BaseModel):
    """Multiple schedule response schema with HEALPix schedules."""

    model_config = ConfigDict(from_attributes=True)

    schedules: list[HealpixScheduleResponse]
