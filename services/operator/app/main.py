import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from .routers.schedules import router as schedules_router
from .routers.status import router as status_router
from .scheduler import lifespan_scheduler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logging.getLogger("apscheduler.executors.base").setLevel(logging.CRITICAL)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting FOV Notification Service...")

    # Start background scheduler for polling observatory schedules
    async with lifespan_scheduler():
        logger.info("Service ready")
        yield

    logger.info("Service shutdown complete")


app = FastAPI(
    title="AttitudeChecker",
    description="Notification service for observation schedules \
        to reduce satellite interference",
    version="0.1.0",
    lifespan=lifespan,
)


# API routers (authenticated)
app.include_router(schedules_router)
app.include_router(status_router)


@app.get("/", tags=["general"])
async def root():
    """Root endpoint."""
    # TODO: Add real URL for documentation
    return {
        "name": "AttitudeChecker",
        "version": "0.1.0",
        "description": (
            "Notification service for observation schedules "
            "to reduce satellite interference"
        ),
        "documentation": "https://attitudechecker.cps.iau.org/docs",
    }


@app.get("/health", tags=["general"])
async def health_check():
    """Public health check endpoint."""
    return {"status": "healthy"}
