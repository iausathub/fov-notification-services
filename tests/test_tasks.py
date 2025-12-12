"""Tests for scheduled tasks."""

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from app.models.observation import Observation, ObservationStatus
from app.models.schedule import Schedule
from app.tasks.cleanup_schedules import cleanup_schedules


class TestCleanupSchedules:
    """Tests for the cleanup_schedules task."""

    @pytest.fixture
    def schedule_with_observations(self, db_session):
        """Create a schedule with past and future observations for testing."""
        now = datetime.now(timezone.utc)

        schedule = Schedule(
            observatory_name="test_observatory",
            source="https://example.com/schedule",
            schedule_start=now - timedelta(days=2),
            schedule_end=now + timedelta(days=2),
        )
        db_session.add(schedule)
        db_session.flush()

        # Past observation (should be archived)
        past_obs = Observation(
            schedule_id=schedule.id,
            observatory_name="test_observatory",
            status=ObservationStatus.SCHEDULED,
            target_name="Past Target",
            ra=180.0,
            dec=45.0,
            start_time=now - timedelta(hours=2),
            end_time=now - timedelta(hours=1),
        )

        # Future observation (should remain SCHEDULED)
        future_obs = Observation(
            schedule_id=schedule.id,
            observatory_name="test_observatory",
            status=ObservationStatus.SCHEDULED,
            target_name="Future Target",
            ra=90.0,
            dec=-30.0,
            start_time=now + timedelta(hours=1),
            end_time=now + timedelta(hours=2),
        )

        db_session.add_all([past_obs, future_obs])
        db_session.commit()

        return schedule

    @pytest.mark.asyncio
    async def test_archives_past_observations(
        self, db_session, schedule_with_observations
    ):
        """Test that past observations are moved to ARCHIVED status."""
        # Patch SessionLocal to return the test session
        with patch("app.tasks.cleanup_schedules.SessionLocal", return_value=db_session):
            await cleanup_schedules()

        # Verify: past observation should be archived
        past_obs = (
            db_session.query(Observation)
            .filter(Observation.target_name == "Past Target")
            .first()
        )
        assert past_obs.status == ObservationStatus.ARCHIVED
        assert past_obs.archived_at is not None

    @pytest.mark.asyncio
    async def test_preserves_future_observations(
        self, db_session, schedule_with_observations
    ):
        """Test that future observations remain in SCHEDULED status."""
        with patch("app.tasks.cleanup_schedules.SessionLocal", return_value=db_session):
            await cleanup_schedules()

        # Verify: future observation should still be scheduled
        future_obs = (
            db_session.query(Observation)
            .filter(Observation.target_name == "Future Target")
            .first()
        )
        assert future_obs.status == ObservationStatus.SCHEDULED
        assert future_obs.archived_at is None

    @pytest.mark.asyncio
    async def test_handles_empty_schedule(self, db_session):
        """Test that cleanup handles schedules with no observations gracefully."""
        schedule = Schedule(
            observatory_name="empty_observatory",
            source="https://example.com/empty",
            schedule_start=datetime.now(timezone.utc),
            schedule_end=datetime.now(timezone.utc) + timedelta(days=1),
        )
        db_session.add(schedule)
        db_session.commit()

        with patch("app.tasks.cleanup_schedules.SessionLocal", return_value=db_session):
            # Should not raise any errors
            await cleanup_schedules()

    @pytest.mark.asyncio
    async def test_handles_no_schedules(self, db_session):
        """Test that cleanup works when there are no schedules at all."""
        with patch("app.tasks.cleanup_schedules.SessionLocal", return_value=db_session):
            # Should not raise any errors
            await cleanup_schedules()
