import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.scheduler import lifespan_scheduler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
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
    title="FOV Notification Service",
    description="Notification service for observation schedules and satellite FOV interference",
    version="0.1.0",
    lifespan=lifespan,
)


# TODO: Add routers


@app.get("/health", tags=["status"])
async def health_check():
    """Public health check endpoint."""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
