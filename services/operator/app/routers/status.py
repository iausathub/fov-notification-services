from fastapi import APIRouter

from app.scheduler import job_status

router = APIRouter(
    prefix="/status",
    tags=["status"],
)


@router.get("")
async def get_scheduler_health():
    """Get the health status of observatory schedule retrieval checks.

    Returns per-observatory health status. A check is healthy if its last run succeeded.

    Status: "healthy" (all checks pass), "degraded" (some checks fail),
    "unhealthy" (all checks fail).
    """
    jobs = {
        job_id.removeprefix("retrieve_schedule_"): {
            "healthy": status["error"] is None,
            "last_success": status.get("last_success"),
            "error": status["error"],
        }
        for job_id, status in job_status.items()
        if job_id.startswith("retrieve_schedule_")
    }

    if not jobs:
        status = "healthy"
    else:
        healthy_count = sum(1 for j in jobs.values() if j["healthy"])
        if healthy_count == len(jobs):
            status = "healthy"
        elif healthy_count == 0:
            status = "unhealthy"
        else:
            status = "degraded"

    return {"status": status, "jobs": jobs}
