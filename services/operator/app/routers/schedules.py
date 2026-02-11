from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models.observation import ObservationStatus
from app.models.schedule import Schedule
from app.schemas.schedule import (
    MultipleScheduleResponse,
    ObservationResponse,
    ScheduleResponse,
)

router = APIRouter(
    prefix="/schedule",
    tags=["schedule"],
    dependencies=[Depends(get_current_user)],
)


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
