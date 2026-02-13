# ruff: noqa: S101

import pytest
from app.scheduler import (
    OBSERVATORY_SCHEDULES,
    add_schedule_cleanup_jobs,
    add_schedule_retrieval_jobs,
    configure_scheduler,
    lifespan_scheduler,
)


class TestScheduler:
    """Tests for the scheduler."""

    def test_add_schedule_retrieval_jobs(self):
        """Test adding schedule retrieval jobs."""
        observatory_schedules = {
            "Observatory_A": {
                "url": "https://example.com/schedule",
                "interval_minutes": 1,
            },
            "Observatory_B": {
                "url": "https://example.com/schedule",
                "interval_minutes": 1,
            },
        }
        scheduler = configure_scheduler()
        add_schedule_retrieval_jobs(scheduler)
        assert len(scheduler.get_jobs()) == len(observatory_schedules)
        for job in scheduler.get_jobs():
            assert job.name == f"Retrieve schedule for {job.args[0]}"

    def test_add_job_listener(self):
        """Test adding job listener."""
        pass

    def test_add_schedule_cleanup_jobs(self):
        """Test adding schedule cleanup jobs."""
        scheduler = configure_scheduler()
        add_schedule_cleanup_jobs(scheduler)
        assert len(scheduler.get_jobs()) == 1
        job = scheduler.get_job("cleanup_schedules")
        assert job is not None
        assert job.name == "Cleanup schedules"

    @pytest.mark.asyncio
    async def test_scheduler_lifespan(self, mocker):
        """Test lifespan context manager starts scheduler, yields it, and cleans up."""
        mock_close_http = mocker.AsyncMock()
        mock_broker = mocker.Mock(disconnect=mocker.AsyncMock())
        mocker.patch(
            "app.scheduler.close_http_client",
            mock_close_http,
        )
        mocker.patch(
            "notifications.get_broker",
            return_value=mock_broker,
        )
        async with lifespan_scheduler() as sched:
            assert sched is not None
            assert sched.running
            jobs = sched.get_jobs()
            expected_count = len(OBSERVATORY_SCHEDULES) + 1  # retrieval + cleanup
            assert len(jobs) == expected_count
            cleanup = sched.get_job("cleanup_schedules")
            assert cleanup is not None
            assert cleanup.name == "Cleanup schedules"

        mock_close_http.assert_awaited_once()
        mock_broker.disconnect.assert_awaited_once()
