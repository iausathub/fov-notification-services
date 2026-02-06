"""APScheduler configuration and management."""

import logging
from contextlib import asynccontextmanager
from datetime import UTC, datetime

from apscheduler.events import EVENT_JOB_ERROR, EVENT_JOB_EXECUTED, JobExecutionEvent
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from tasks.cleanup_schedules import cleanup_schedules
from tasks.retrieve_schedules import close_http_client, retrieve_schedule

logger = logging.getLogger(__name__)

# Tracks last run time and error per job
job_status: dict[str, dict] = {}

# Scheduler instance - initialized on app startup
scheduler: AsyncIOScheduler | None = None

# Configure observatory schedule sources
# TODO: Move to config/database
OBSERVATORY_SCHEDULES = {
    "Rubin": {
        "url": "https://usdf-rsp.slac.stanford.edu/obsloctap/schedule",
        "interval_minutes": 1,
        "latitude": -30.244633,
        "longitude": -70.749417,
        "elevation": 2647.0,
    },
    "TestFailure": {
        "url": "https://schedule-that-always-fails.com",
        "interval_minutes": 1,
        "latitude": 0.0,
        "longitude": 0.0,
        "elevation": 0.0,
    },
}


def _job_listener(event: JobExecutionEvent) -> None:
    """Listener for job execution events."""
    now = datetime.now(UTC)
    current = job_status.get(event.job_id, {})

    if event.exception:
        job_status[event.job_id] = {
            "last_run": now,
            "last_success": current.get("last_success"),
            "error": str(event.exception),
        }
        logger.warning(f"Job {event.job_id} failed: {event.exception}")
    else:
        job_status[event.job_id] = {
            "last_run": now,
            "last_success": now,
            "error": None,
        }


def configure_scheduler() -> AsyncIOScheduler:
    """Create and configure the APScheduler instance."""
    return AsyncIOScheduler(
        job_defaults={
            "coalesce": True,  # Combine missed runs into one
            "max_instances": 1,  # one instance per job
            "misfire_grace_time": 60,
        }
    )


def add_schedule_retrieval_jobs(sched: AsyncIOScheduler) -> None:
    """Add schedule retrieval jobs for all configured observatories."""
    for obs_name, config in OBSERVATORY_SCHEDULES.items():
        sched.add_job(
            retrieve_schedule,
            trigger=IntervalTrigger(minutes=config["interval_minutes"]),
            args=[
                obs_name,
                config["url"],
                config["latitude"],
                config["longitude"],
                config["elevation"],
            ],
            id=f"retrieve_schedule_{obs_name}",
            name=f"Retrieve schedule for {obs_name}",
            replace_existing=True,
            next_run_time=datetime.now(UTC),  # Run immediately on startup
        )
        interval = config["interval_minutes"]
        logger.info(f"Scheduled retrieval for {obs_name} every {interval} minutes")


def add_schedule_cleanup_jobs(sched: AsyncIOScheduler) -> None:
    """Add schedule cleanup jobs for all configured observatories."""
    sched.add_job(
        cleanup_schedules,
        trigger=IntervalTrigger(minutes=1),
        id="cleanup_schedules",
        name="Cleanup schedules",
        replace_existing=True,
        next_run_time=datetime.now(UTC),  # Run immediately on startup
    )
    logger.info("Scheduled cleanup of schedules every 1 minute")


@asynccontextmanager
async def lifespan_scheduler():
    """Context manager for scheduler lifecycle."""
    global scheduler

    scheduler = configure_scheduler()
    scheduler.add_listener(_job_listener, EVENT_JOB_EXECUTED | EVENT_JOB_ERROR)
    add_schedule_retrieval_jobs(scheduler)
    add_schedule_cleanup_jobs(scheduler)
    scheduler.start()
    logger.info("APScheduler started")

    try:
        yield scheduler
    finally:
        scheduler.shutdown(wait=True)
        await close_http_client()

        # Clean up message broker connection
        try:
            from notifications import get_broker

            broker = get_broker()
            await broker.disconnect()
        except Exception as e:
            logger.warning(f"Error disconnecting message broker: {e}", exc_info=True)

        logger.info("APScheduler shutdown complete")
        scheduler = None
