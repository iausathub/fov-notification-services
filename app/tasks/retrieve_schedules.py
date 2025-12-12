"""APScheduler task to retrieve observation schedules from external sources."""

import logging
from datetime import datetime, timezone

import httpx
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.observation import Observation, ObservationStatus
from app.models.schedule import Schedule
from astropy.time import Time

logger = logging.getLogger(__name__)

# Shared HTTP client for connection pooling across observatory polls
_http_client: httpx.AsyncClient | None = None


def get_http_client() -> httpx.AsyncClient:
    """Get or create the shared HTTP client."""
    global _http_client
    if _http_client is None:
        _http_client = httpx.AsyncClient(
            timeout=30.0,
            follow_redirects=True,
        )
    return _http_client


async def close_http_client() -> None:
    """Close the shared HTTP client. Call on shutdown."""
    global _http_client
    if _http_client is not None:
        await _http_client.aclose()
        _http_client = None


class ScheduleRetrievalError(Exception):
    """Raised when schedule retrieval fails."""

    pass


async def fetch_schedule_data(url: str) -> dict:
    """Fetch schedule data from the given URL.

    Args:
        url: The API endpoint to fetch schedule data from.

    Returns:
        The parsed JSON response as a dictionary.

    Raises:
        ScheduleRetrievalError: If the request fails or returns invalid data.
    """
    client = get_http_client()
    try:
        logger.info(f"Fetching schedule from {url}")
        response = await client.get(url)
        response.raise_for_status()
        logger.info(f"Schedule fetched from {url}")
        return response.json()
    except httpx.TimeoutException as e:
        logger.error(f"Timeout fetching schedule from {url}: {e}")
        raise ScheduleRetrievalError(f"Request timed out: {url}") from e
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error fetching schedule from {url}: {e}")
        raise ScheduleRetrievalError(f"HTTP {e.response.status_code}: {url}") from e
    except httpx.RequestError as e:
        logger.error(f"Request error fetching schedule from {url}: {e}")
        raise ScheduleRetrievalError(f"Request failed: {url}") from e


def process_schedule_data(
    db: Session,
    observatory_name: str,
    source_url: str,
    schedule_data: dict,
) -> Schedule:
    """Process and store schedule data in the database.

    Implements the schedule replacement logic:
    1. Delete only SCHEDULED observations (future, replaceable)
    2. ARCHIVED observations remain untouched (permanent history)
    3. Replace schedule record with new data

    All operations are wrapped in a single transaction for atomicity.

    Args:
        db: Database session.
        observatory_name: Name of the observatory.
        source_url: The URL the data was fetched from.
        schedule_data: The parsed schedule data.

    Returns:
        The created or updated Schedule record.
    """
    with db.begin():
        # Delete existing SCHEDULED observations for this observatory
        db.query(Observation).filter(
            Observation.observatory_name == observatory_name,
            Observation.status == ObservationStatus.SCHEDULED,
        ).delete(synchronize_session=False)

        # Get or create schedule record
        schedule = (
            db.query(Schedule)
            .filter(Schedule.observatory_name == observatory_name)
            .first()
        )

        # Get schedule bounds from observation times
        schedule_start_mjd = Time(
            min(obs["t_planning"] for obs in schedule_data), format="mjd"
        )
        schedule_start = schedule_start_mjd.to_datetime(timezone=timezone.utc)
        schedule_end_mjd = Time(
            max(obs["t_planning"] for obs in schedule_data), format="mjd"
        )
        schedule_end = schedule_end_mjd.to_datetime(timezone=timezone.utc)
        if schedule is None:
            schedule = Schedule(
                observatory_name=observatory_name,
                source=source_url,
                schedule_start=schedule_start,
                schedule_end=schedule_end,
            )
            db.add(schedule)
        else:
            schedule.source = source_url
            schedule.updated_at = datetime.now(timezone.utc)

            # update schedule_start and schedule_end if they are different from the new schedule
            if schedule.schedule_start != schedule_start:
                schedule.schedule_start = schedule_start
            if schedule.schedule_end != schedule_end:
                schedule.schedule_end = schedule_end

        # Flush to get schedule.id for new observations
        db.flush()

        # Create new SCHEDULED observations for the new schedule
        for obs_data in schedule_data:
            start_time = Time(obs_data.get("t_planning"), format="mjd").to_datetime(
                timezone=timezone.utc
            )
            # convert t_exptime from seconds to days
            t_exptime_days = obs_data.get("t_exptime") / 86400
            end_time = Time(
                obs_data.get("t_planning") + t_exptime_days, format="mjd"
            ).to_datetime(timezone=timezone.utc)
            observation = Observation(
                schedule_id=schedule.id,
                observatory_name=observatory_name,
                status=ObservationStatus.SCHEDULED,
                target_name=obs_data.get("target_name"),
                ra=obs_data.get("s_ra"),
                dec=obs_data.get("s_dec"),
                start_time=start_time,
                end_time=end_time,
                fov_radius=obs_data.get("s_fov"),
                # on_sky_angle=obs_data.get("on_sky_angle"),
                instrument=obs_data.get("instrument_name"),
            )
            db.add(observation)

    # Transaction auto-committed on successful exit from `with db.begin():`
    logger.info(f"Updated schedule for {observatory_name} from {source_url}")
    return schedule


async def retrieve_schedule(observatory_name: str, url: str) -> None:
    """Main task to retrieve and store schedule data for an observatory.

    This is the function to be called by APScheduler.

    Args:
        observatory_name: Name of the observatory to retrieve schedule for.
        url: The API endpoint to fetch schedule data from.
    """
    logger.info(f"Retrieving schedule for {observatory_name} from {url}")

    try:
        schedule_data = await fetch_schedule_data(url)
    except ScheduleRetrievalError:
        # Error already logged, just return
        return

    db = SessionLocal()
    try:
        process_schedule_data(db, observatory_name, url, schedule_data)
    except Exception as e:
        # Transaction auto-rolled-back by db.begin() context manager on exception
        logger.exception(f"Failed to process schedule data for {observatory_name}: {e}")
    finally:
        db.close()
