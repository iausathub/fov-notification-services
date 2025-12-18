# ruff: noqa: S101

from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import httpx
import pytest
from app.models.observation import Observation, ObservationStatus
from app.models.schedule import Schedule
from app.tasks.cleanup_schedules import cleanup_schedules
from app.tasks.retrieve_schedules import (
    ScheduleRetrievalError,
    fetch_schedule_data,
    process_schedule_data,
    retrieve_schedule,
)
from astropy.time import Time


@pytest.fixture
def new_schedule_data():
    """Example new schedule data (format from the Rubin schedule API)"""
    return [
        {
            "t_planning": 61019.35632748149,
            "target_name": "ddf_edfs_b, lowdust",
            "s_ra": 123,
            "s_dec": 30,
            "s_fov": 3,
            "t_exptime": 30,
            "instrument_name": "LSSTCam",
        },
    ]


class TestCleanupSchedules:
    """Tests for the cleanup_schedules task."""

    @pytest.mark.asyncio
    async def test_archives_past_observations(self, db_session, create_schedule):
        """Test that past observations are moved to ARCHIVED status."""
        create_schedule("test_observatory")
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
    async def test_preserves_future_observations(self, db_session, create_schedule):
        """Test that future observations remain in SCHEDULED status."""
        create_schedule("test_observatory")
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
            observatory_latitude=0.0,
            observatory_longitude=0.0,
            observatory_elevation=0.0,
            source="https://example.com/empty",
            schedule_start=datetime.now(UTC),
            schedule_end=datetime.now(UTC) + timedelta(days=1),
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


class TestRetrieveSchedules:
    """Tests for the retrieve_schedules task."""

    @pytest.fixture
    def example_schedule_data(self):
        """Example schedule data for testing. (format from the Rubin schedule API)"""
        return [
            {
                "t_planning": 61019.35632748149,
                "target_name": "ddf_edfs_b, lowdust",
                "s_ra": 65.77732051949559,
                "s_dec": -46.70068946263419,
                "s_fov": 3,
                "t_exptime": 30,
                "instrument_name": "LSSTCam",
            },
            {
                "t_planning": 61019.35600404545,
                "target_name": "lowdust",
                "s_ra": 61.78003509187598,
                "s_dec": -41.55606824815095,
                "s_fov": 3,
                "t_exptime": 30,
                "instrument_name": "LSSTCam",
            },
            {
                "t_planning": 61019.35588171854,
                "target_name": "lowdust",
                "s_ra": 68.01621252389484,
                "s_dec": -49.24758246665158,
                "s_fov": 3,
                "t_exptime": 30,
                "instrument_name": "LSSTCam",
            },
        ]

    @pytest.mark.asyncio
    async def test_retrieves_schedule(self, db_session, example_schedule_data):
        """Test that the retrieve_schedules task retrieves the current schedule
        data and stores it in the database, replacing existing future observations."""

        # Patch fetch_schedule_data to return the example schedule data
        with patch(
            "app.tasks.retrieve_schedules.fetch_schedule_data",
            return_value=example_schedule_data,
        ):
            with patch(
                "app.tasks.retrieve_schedules.SessionLocal", return_value=db_session
            ):
                await retrieve_schedule(
                    "test_observatory", "https://example.com/schedule", 0.0, 0.0, 0.0
                )

            # Verify: future observations should be replaced with the new schedule
            future_obs = (
                db_session.query(Observation).order_by(Observation.start_time).all()
            )

            assert len(future_obs) == len(example_schedule_data)

            for obs in future_obs:
                assert obs.status == ObservationStatus.SCHEDULED
                assert obs.archived_at is None
                assert obs.target_name in [
                    obs["target_name"] for obs in example_schedule_data
                ]
                assert obs.ra in [obs["s_ra"] for obs in example_schedule_data]
                assert obs.dec in [obs["s_dec"] for obs in example_schedule_data]
                assert obs.fov_radius in [obs["s_fov"] for obs in example_schedule_data]
                assert obs.instrument in [
                    obs["instrument_name"] for obs in example_schedule_data
                ]
                assert obs.start_time in [
                    Time(obs["t_planning"], format="mjd").to_datetime(timezone=UTC)
                    for obs in example_schedule_data
                ]
                assert obs.end_time in [
                    Time(
                        obs["t_planning"] + obs["t_exptime"] / 86400, format="mjd"
                    ).to_datetime(timezone=UTC)
                    for obs in example_schedule_data
                ]

    @pytest.mark.asyncio
    async def test_update_schedule(
        self, db_session, example_schedule_data, new_schedule_data
    ):
        """
        Test that the retrieve_schedules task updates the schedule if it already exists.
        """

        # Patch fetch_schedule_data to return the example schedule data
        with patch(
            "app.tasks.retrieve_schedules.SessionLocal", return_value=db_session
        ):
            with patch(
                "app.tasks.retrieve_schedules.fetch_schedule_data",
                return_value=example_schedule_data,
            ):
                await retrieve_schedule(
                    "test_observatory", "https://example.com/schedule", 0.0, 0.0, 0.0
                )

                future_obs = (
                    db_session.query(Observation).order_by(Observation.start_time).all()
                )

                assert len(future_obs) == len(example_schedule_data)

            with patch(
                "app.tasks.retrieve_schedules.fetch_schedule_data",
                return_value=new_schedule_data,
            ):
                await retrieve_schedule(
                    "test_observatory", "https://example.com/schedule", 0.0, 0.0, 0.0
                )

                future_obs = (
                    db_session.query(Observation).order_by(Observation.start_time).all()
                )

                assert len(future_obs) == len(new_schedule_data)

                for obs in future_obs:
                    assert obs.status == ObservationStatus.SCHEDULED
                    assert obs.archived_at is None
                    assert obs.target_name in [
                        obs["target_name"] for obs in new_schedule_data
                    ]
                    assert obs.ra in [obs["s_ra"] for obs in new_schedule_data]
                    assert obs.dec in [obs["s_dec"] for obs in new_schedule_data]
                    assert obs.fov_radius in [obs["s_fov"] for obs in new_schedule_data]

    @pytest.mark.asyncio
    async def test_retrieves_schedule_errors(self, db_session):
        """
        Test that fetch_schedule_data raises ScheduleRetrievalError and
        retrieve_schedule handles it correctly.
        """
        # Test that fetch_schedule_data raises the error
        with patch("app.tasks.retrieve_schedules.get_http_client") as mock_get_client:
            mock_client = mock_get_client.return_value
            mock_client.get.side_effect = httpx.TimeoutException("Connection timed out")

            with pytest.raises(ScheduleRetrievalError, match="Request timed out"):
                await fetch_schedule_data("https://example.com/schedule")

        # Test that retrieve_schedule catches the error
        with patch(
            "app.tasks.retrieve_schedules.SessionLocal", return_value=db_session
        ):
            with patch(
                "app.tasks.retrieve_schedules.fetch_schedule_data",
                side_effect=ScheduleRetrievalError("Request timed out"),
            ):
                # Should not raise - error is caught and logged
                await retrieve_schedule(
                    "test_observatory", "https://example.com/schedule", 0.0, 0.0, 0.0
                )

    @pytest.mark.asyncio
    async def test_retrieve_empty_schedule(self, db_session, create_schedule):
        """Test that an empty schedule does not delete any observations."""
        create_schedule("test_observatory")
        with patch(
            "app.tasks.retrieve_schedules.SessionLocal", return_value=db_session
        ):
            with patch(
                "app.tasks.retrieve_schedules.fetch_schedule_data", return_value=[]
            ):
                await retrieve_schedule(
                    "test_observatory", "https://example.com/schedule", 0.0, 0.0, 0.0
                )

        # Fixture creates 2 observations: "Past Target" and "Future Target"
        obs = db_session.query(Observation).all()
        assert len(obs) == 2
        assert {o.target_name for o in obs} == {"Past Target", "Future Target"}

    @pytest.mark.asyncio
    async def test_retrieve_schedule_archived_obs(
        self, db_session, create_schedule, new_schedule_data
    ):
        """Test that archived obs are not deleted and future obs are replaced."""
        create_schedule("test_observatory")
        with patch(
            "app.tasks.retrieve_schedules.SessionLocal", return_value=db_session
        ):
            with patch(
                "app.tasks.retrieve_schedules.fetch_schedule_data",
                return_value=new_schedule_data,
            ):
                await retrieve_schedule(
                    "test_observatory", "https://example.com/schedule", 0.0, 0.0, 0.0
                )

        obs = db_session.query(Observation).all()
        assert len(obs) == 2
        # Check that the archived observation is not deleted and the future observation
        # is replaced with the new schedule data
        assert {o.target_name for o in obs} == {"Past Target", "ddf_edfs_b, lowdust"}

    @pytest.mark.asyncio
    async def test_retrieve_schedule_new_obs(
        self, db_session, create_schedule, new_schedule_data
    ):
        """Test that a new schedule object is created if it does not exist, and that
        future observations are associate with the correct schedule."""
        create_schedule("test_observatory")
        with patch(
            "app.tasks.retrieve_schedules.SessionLocal", return_value=db_session
        ):
            with patch(
                "app.tasks.retrieve_schedules.fetch_schedule_data",
                return_value=new_schedule_data,
            ):
                await retrieve_schedule(
                    "test_new_observatory",
                    "https://example.com/schedule",
                    200.0,
                    20.0,
                    2000.0,
                )

                # Check that a new schedule object is created and has only the new
                # observations
                schedules = db_session.query(Schedule).all()
                assert len(schedules) == 2
                assert {s.observatory_name for s in schedules} == {
                    "test_new_observatory",
                    "test_observatory",
                }

                for schedule in schedules:
                    if schedule.observatory_name == "test_new_observatory":
                        # Check that the observatory location is set correctly
                        assert schedule.observatory_latitude == 200.0
                        assert schedule.observatory_longitude == 20.0
                        assert schedule.observatory_elevation == 2000.0

                        assert len(schedule.observations) == len(new_schedule_data)
                        assert {o.target_name for o in schedule.observations} == {
                            obs["target_name"] for obs in new_schedule_data
                        }
                        assert {o.ra for o in schedule.observations} == {
                            obs["s_ra"] for obs in new_schedule_data
                        }
                        assert {o.dec for o in schedule.observations} == {
                            obs["s_dec"] for obs in new_schedule_data
                        }
                        assert {o.fov_radius for o in schedule.observations} == {
                            obs["s_fov"] for obs in new_schedule_data
                        }
                        assert {o.instrument for o in schedule.observations} == {
                            obs["instrument_name"] for obs in new_schedule_data
                        }
                        assert {o.start_time for o in schedule.observations} == {
                            Time(obs["t_planning"], format="mjd").to_datetime(
                                timezone=UTC
                            )
                            for obs in new_schedule_data
                        }
                        assert {o.end_time for o in schedule.observations} == {
                            Time(
                                obs["t_planning"] + obs["t_exptime"] / 86400,
                                format="mjd",
                            ).to_datetime(timezone=UTC)
                            for obs in new_schedule_data
                        }
                    else:
                        # There are only two schedules so the other one is the
                        # test schedule
                        assert len(schedule.observations) == 2
                        assert {o.target_name for o in schedule.observations} == {
                            "Past Target",
                            "Future Target",
                        }

    @pytest.mark.asyncio
    async def test_retrieve_schedule_bad_data(self, db_session):
        """
        Test that a bad schedule data format raises ScheduleRetrievalError from
        process_schedule_data.
        """
        # Test that process_schedule_data raises the error directly since
        # retrieve_schedule catches ScheduleRetrievalError and logs it
        with pytest.raises(
            ScheduleRetrievalError, match="Error processing schedule data"
        ):
            process_schedule_data(
                db_session,
                "test_observatory",
                "https://example.com/schedule",
                ["not a valid schedule"],
                0.0,
                0.0,
                0.0,
            )
