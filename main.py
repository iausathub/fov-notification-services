import logging
from contextlib import asynccontextmanager

from app.routers.schedules import router as schedules_router
from app.routers.status import router as status_router
from app.scheduler import lifespan_scheduler
from fastapi import FastAPI

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
    title="FOV Notification Service",
    description="Notification service for observation schedules \
        and satellite FOV interference",
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
        "name": "FOV Notification Service",
        "version": "0.1.0",
        "description": (
            "Notification service for observation schedules "
            "and satellite FOV interference"
        ),
        "documentation": "http://127.0.0.1:8000/docs",
    }


@app.get("/health", tags=["general"])
async def health_check():
    """Public health check endpoint."""
    return {"status": "healthy"}


# Development server
if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
