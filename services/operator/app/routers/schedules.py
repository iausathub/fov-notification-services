from datetime import UTC, datetime, timedelta
from typing import Annotated, Any, cast

import astropy.units as u
import numpy as np
from astropy.coordinates import AltAz, EarthLocation, SkyCoord
from astropy.time import Time
from fastapi import APIRouter, Depends, Query
from healpy import pixelfunc, query_disc
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models.observation import Observation, ObservationStatus
from app.models.schedule import Schedule
from app.schemas.schedule import (
    HealpixPixelDirection,
    HealpixScheduleResponse,
    MultipleHealpixScheduleResponse,
    MultipleScheduleResponse,
    ObservationResponse,
    ScheduleResponse,
)

router = APIRouter(
    prefix="/schedule",
    tags=["schedule"],
    dependencies=[Depends(get_current_user)],
)

RUBIN_RADIUS_DEG = 5


def _get_healpix_indices(
    observations: list[Observation],
) -> tuple[list[int], int, bool]:
    nside = 16
    use_nested = True
    if observations:
        ras = np.array([obs.ra for obs in observations])
        decs = np.array([obs.dec for obs in observations])
        return (
            list(
                set(pixelfunc.ang2pix(nside, ras, decs, lonlat=True, nest=use_nested))
            ),
            nside,
            use_nested,
        )
    return ([], nside, use_nested)


def _get_healpix_indices_rubin(
    observations: list[Observation],
) -> tuple[list[int], int, bool]:
    nside = 32
    use_nested = True

    if observations:
        vecs = pixelfunc.ang2vec(
            np.array([obs.ra for obs in observations]),
            np.array([obs.dec for obs in observations]),
            lonlat=True,
        )

        covered_pixels = np.unique(
            np.concatenate(
                [
                    query_disc(
                        nside=nside,
                        vec=vec,
                        radius=np.radians(RUBIN_RADIUS_DEG),
                        nest=use_nested,
                    )
                    for vec in vecs
                ]
            )
        )

        return (covered_pixels.tolist(), nside, use_nested)
    return ([], nside, use_nested)


def _compute_pixel_directions(
    observations: list[Observation],
    nside: int,
    use_nested: bool,
    radius: int | None,
    location: EarthLocation,
) -> list[HealpixPixelDirection]:
    """Compute the AltAz direction of each scheduled HEALPix pixel as seen from the
    observatory, at the time of the observation that scheduled it.

    Unlike the deduplicated ``pixel_indices`` list, this keeps one entry per
    (pixel, observation) pair, because the horizontal direction of a fixed sky pixel
    changes as the Earth rotates.
    """
    pixels: list[int] = []
    times: list[datetime] = []
    for obs in observations:
        if obs.ra is None or obs.dec is None:
            continue
        if radius is not None:
            vec = pixelfunc.ang2vec(obs.ra, obs.dec, lonlat=True)
            obs_pixels = query_disc(
                nside=nside, vec=vec, radius=np.radians(radius), nest=use_nested
            )
        else:
            obs_pixels = [
                pixelfunc.ang2pix(nside, obs.ra, obs.dec, lonlat=True, nest=use_nested)
            ]
        for pixel in obs_pixels:
            pixels.append(int(pixel))
            times.append(obs.start_time)

    if not pixels:
        return []

    # Pixel-centre sky coordinates (ICRS RA/Dec, degrees)
    ras, decs = pixelfunc.pix2ang(nside, np.array(pixels), nest=use_nested, lonlat=True)

    altaz = cast(
        Any,
        SkyCoord(ra=ras * u.deg, dec=decs * u.deg, frame="icrs").transform_to(
            AltAz(obstime=Time(times), location=location)
        ),
    )
    az_deg = np.asarray(altaz.az.deg, dtype=float)
    alt_deg = np.asarray(altaz.alt.deg, dtype=float)

    return [
        HealpixPixelDirection(
            index=pixels[i],
            time=times[i],
            azimuth=round(float(az_deg[i]), 8),
            altitude=round(float(alt_deg[i]), 8),
        )
        for i in range(len(pixels))
    ]


@router.get("", response_model=MultipleScheduleResponse)
async def get_full_schedule(
    db: Annotated[Session, Depends(get_db)],
    hours: int = Query(
        24, ge=1, le=48, description="Hours ahead to include (max 2 days)"
    ),
):
    """Get a combined planned schedule of where and when telescopes plan to point for
    all supported ground-based astronomical observatories.

    Returns a list of schedules (one per observatory), each containing planned
    observations of the sky within the next N hours, sorted by start time.

    Planned observations are subject to change and updated on a best effort basis by
    individual observatories.
    """
    now = datetime.now(UTC)
    end_time = now + timedelta(hours=hours)

    # Get all schedules with their observations filtered by time window
    schedules = db.query(Schedule).all()

    result = []
    for schedule in schedules:
        # Filter observations to the time window
        filtered_obs = [
            obs
            for obs in schedule.observations
            if obs.status == ObservationStatus.SCHEDULED
            and obs.start_time >= now
            and obs.start_time <= end_time
        ]
        # Sort by start time
        filtered_obs.sort(key=lambda o: o.start_time)

        result.append(
            ScheduleResponse(
                observatory_name=schedule.observatory_name,
                observatory_latitude=schedule.observatory_latitude,
                observatory_longitude=schedule.observatory_longitude,
                observatory_elevation=schedule.observatory_elevation,
                schedule_start=schedule.schedule_start,
                schedule_end=schedule.schedule_end,
                created_at=schedule.created_at,
                updated_at=schedule.updated_at,
                observations=[
                    ObservationResponse.model_validate(o) for o in filtered_obs
                ],
            )
        )

    return MultipleScheduleResponse(schedules=result)


@router.get("/healpix", response_model=MultipleHealpixScheduleResponse)
async def get_full_healpix_schedule(
    db: Annotated[Session, Depends(get_db)],
    hours: int = Query(
        24, ge=1, le=48, description="Hours ahead to include (max 2 days)"
    ),
    include_direction: bool = Query(
        False,
        description="If true, also return pixel_directions: the AltAz direction "
        "(azimuth/altitude) of each scheduled HEALPix pixel relative to the "
        "observatory, at the time of the observation that scheduled it. These are "
        "not deduplicated.",
    ),
):

    now = datetime.now(UTC)
    end_time = now + timedelta(hours=hours)

    # Get all schedules with their observations filtered by time window
    schedules = db.query(Schedule).all()

    result = []
    for schedule in schedules:
        # Filter observations to the time window
        filtered_obs = [
            obs
            for obs in schedule.observations
            if obs.status == ObservationStatus.SCHEDULED
            and obs.start_time >= now
            and obs.start_time <= end_time
        ]
        # Sort by start time
        filtered_obs.sort(key=lambda o: o.start_time)

        radius = None
        if schedule.observatory_name.lower() == "rubin":
            healpix_indices, nside, use_nested = _get_healpix_indices_rubin(
                filtered_obs
            )
            radius = RUBIN_RADIUS_DEG
        else:
            healpix_indices, nside, use_nested = _get_healpix_indices(filtered_obs)

        pixel_directions = None
        if include_direction:
            location = EarthLocation.from_geodetic(
                lon=schedule.observatory_longitude * u.deg,
                lat=schedule.observatory_latitude * u.deg,
                height=schedule.observatory_elevation * u.m,
            )
            pixel_directions = _compute_pixel_directions(
                filtered_obs, nside, use_nested, radius, location
            )

        result.append(
            HealpixScheduleResponse(
                observatory_name=schedule.observatory_name,
                observatory_latitude=schedule.observatory_latitude,
                observatory_longitude=schedule.observatory_longitude,
                observatory_elevation=schedule.observatory_elevation,
                schedule_start=schedule.schedule_start,
                schedule_end=schedule.schedule_end,
                created_at=schedule.created_at,
                updated_at=schedule.updated_at,
                n_side=nside,
                ordering="nested" if use_nested else "ring",
                pixel_indices=healpix_indices,
                radius=radius,
                pixel_directions=pixel_directions,
            )
        )

    return MultipleHealpixScheduleResponse(schedules=result)


@router.get("/{observatory_name}", response_model=ScheduleResponse)
async def get_observatory_schedule(
    observatory_name: str,
    db: Annotated[Session, Depends(get_db)],
    hours: int | None = Query(
        None,
        ge=1,
        description="Hours ahead to include. If not provided, returns all \
            scheduled observations.",
    ),
):
    """Get schedule for a specific observatory.

    Returns the schedule with observations within the next N hours,
    or all scheduled observations if hours is not specified.
    """
    schedule = (
        db.query(Schedule)
        .filter(func.lower(Schedule.observatory_name) == func.lower(observatory_name))
        .first()
    )

    if not schedule:
        from fastapi import HTTPException, status

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Observatory '{observatory_name}' not found",
        )

    # Filter observations
    if hours is not None:
        now = datetime.now(UTC)
        end_time = now + timedelta(hours=hours)
        filtered_obs = [
            obs
            for obs in schedule.observations
            if obs.status == ObservationStatus.SCHEDULED
            and obs.start_time >= now
            and obs.start_time <= end_time
        ]
    else:
        # Return all scheduled observations
        filtered_obs = [
            obs
            for obs in schedule.observations
            if obs.status == ObservationStatus.SCHEDULED
        ]

    filtered_obs.sort(key=lambda o: o.start_time)

    return ScheduleResponse(
        observatory_name=schedule.observatory_name,
        observatory_latitude=schedule.observatory_latitude,
        observatory_longitude=schedule.observatory_longitude,
        observatory_elevation=schedule.observatory_elevation,
        schedule_start=schedule.schedule_start,
        schedule_end=schedule.schedule_end,
        created_at=schedule.created_at,
        updated_at=schedule.updated_at,
        observations=[ObservationResponse.model_validate(o) for o in filtered_obs],
    )


@router.get("/{observatory_name}/healpix", response_model=HealpixScheduleResponse)
async def get_healpix_observatory_schedule(
    observatory_name: str,
    db: Annotated[Session, Depends(get_db)],
    hours: int | None = Query(
        None,
        ge=1,
        description="Hours ahead to include. If not provided, returns all \
            scheduled observations.",
    ),
    include_direction: bool = Query(
        False,
        description="If true, also return pixel_directions: the AltAz direction "
        "(azimuth/altitude) of each scheduled HEALPix pixel relative to the "
        "observatory, at the time of the observation that scheduled it. These are "
        "not deduplicated.",
    ),
):
    """Get HEALPix schedule for a specific observatory.

    Returns the HEALPix schedule with pixel indices within the next N hours,
    or all scheduled HEALPix pixel indices if hours is not specified.
    """
    schedule = (
        db.query(Schedule)
        .filter(func.lower(Schedule.observatory_name) == func.lower(observatory_name))
        .first()
    )

    if not schedule:
        from fastapi import HTTPException, status

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Observatory '{observatory_name}' not found",
        )

    # Filter observations
    if hours is not None:
        now = datetime.now(UTC)
        end_time = now + timedelta(hours=hours)
        filtered_obs = [
            obs
            for obs in schedule.observations
            if obs.status == ObservationStatus.SCHEDULED
            and obs.start_time >= now
            and obs.start_time <= end_time
        ]
    else:
        # Return all scheduled observations
        filtered_obs = [
            obs
            for obs in schedule.observations
            if obs.status == ObservationStatus.SCHEDULED
        ]

    filtered_obs.sort(key=lambda o: o.start_time)

    radius = None
    if schedule.observatory_name.lower() == "rubin":
        healpix_indices, nside, use_nested = _get_healpix_indices_rubin(filtered_obs)
        radius = RUBIN_RADIUS_DEG
    else:
        healpix_indices, nside, use_nested = _get_healpix_indices(filtered_obs)

    pixel_directions = None
    if include_direction:
        location = EarthLocation.from_geodetic(
            lon=schedule.observatory_longitude * u.deg,
            lat=schedule.observatory_latitude * u.deg,
            height=schedule.observatory_elevation * u.m,
        )
        pixel_directions = _compute_pixel_directions(
            filtered_obs, nside, use_nested, radius, location
        )

    return HealpixScheduleResponse(
        observatory_name=schedule.observatory_name,
        observatory_latitude=schedule.observatory_latitude,
        observatory_longitude=schedule.observatory_longitude,
        observatory_elevation=schedule.observatory_elevation,
        schedule_start=schedule.schedule_start,
        schedule_end=schedule.schedule_end,
        created_at=schedule.created_at,
        updated_at=schedule.updated_at,
        n_side=nside,
        ordering="nested" if use_nested else "ring",
        pixel_indices=healpix_indices,
        radius=radius,
        pixel_directions=pixel_directions,
    )
