"""APScheduler configuration and management."""

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from contextlib import asynccontextmanager
from app.tasks.retrieve_schedules import retrieve_schedule, close_http_client
from app.tasks.cleanup_schedules import cleanup_schedules

logger = logging.getLogger(__name__)

# Scheduler instance - initialized on app startup
scheduler: AsyncIOScheduler | None = None

# Configure observatory schedule sources
# TODO: Move to config/database
OBSERVATORY_SCHEDULES = {
    "Rubin": {
        "url": "https://usdf-rsp.slac.stanford.edu/obsloctap/schedule",
        "interval_minutes": 10,
    },
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
            args=[obs_name, config["url"]],
            id=f"retrieve_schedule_{obs_name}",
            name=f"Retrieve schedule for {obs_name}",
            replace_existing=True,
        )
        logger.info(
            f"Scheduled retrieval for {obs_name} every {config['interval_minutes']} minutes"
        )


def add_schedule_cleanup_jobs(sched: AsyncIOScheduler) -> None:
    """Add schedule cleanup jobs for all configured observatories."""
    sched.add_job(
        cleanup_schedules,
        trigger=IntervalTrigger(minutes=1),
        id="cleanup_schedules",
        name="Cleanup schedules",
        replace_existing=True,
    )
    logger.info("Scheduled cleanup of schedules every 1 minute")


@asynccontextmanager
async def lifespan_scheduler():
    """Context manager for scheduler lifecycle."""
    global scheduler

    scheduler = configure_scheduler()
    add_schedule_retrieval_jobs(scheduler)
    add_schedule_cleanup_jobs(scheduler)
    scheduler.start()
    logger.info("APScheduler started")

    try:
        yield scheduler
    finally:
        scheduler.shutdown(wait=True)
        await close_http_client()
        logger.info("APScheduler shutdown complete")
        scheduler = None
