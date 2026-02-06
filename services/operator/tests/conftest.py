import os
from datetime import UTC, datetime, timedelta

import pytest
from app.database import Base
from app.models.observation import Observation, ObservationStatus
from app.models.schedule import Schedule
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5432/test_fov_notifications",
)


def _create_database_if_not_exists():
    """Create the test database if it doesn't exist."""
    # Parse the database URL to get the database name and base URL
    parts = TEST_DATABASE_URL.rsplit("/", 1)
    base_url = parts[0] + "/postgres"
    db_name = parts[1]

    engine = create_engine(base_url, isolation_level="AUTOCOMMIT")
    with engine.connect() as conn:
        result = conn.execute(
            text("SELECT 1 FROM pg_database WHERE datname = :db_name"),
            {"db_name": db_name},
        )
        if not result.fetchone():
            conn.execute(text(f'CREATE DATABASE "{db_name}"'))
    engine.dispose()


@pytest.fixture(scope="session")
def db_engine():
    """
    Creates the database if it doesn't exist, then creates all tables.
    """
    _create_database_if_not_exists()

    engine = create_engine(TEST_DATABASE_URL)
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture
def db_session(db_engine):
    """Create a database session for testing.

    Each test gets a fresh session. All changes are rolled back
    after the test to ensure test isolation.
    """
    connection = db_engine.connect()
    transaction = connection.begin()

    testing_session_local = sessionmaker(
        autocommit=False, autoflush=False, bind=connection
    )
    session = testing_session_local()

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def create_schedule(db_session):
    """Factory fixture to create schedules with custom observatory names."""

    def _create(observatory_name="Test_Observatory"):
        now = datetime.now(UTC)
        schedule = Schedule(
            observatory_name=observatory_name,
            observatory_latitude=100.0,
            observatory_longitude=10.0,
            observatory_elevation=1000.0,
            source="https://example.com/schedule",
            schedule_start=now - timedelta(days=2),
            schedule_end=now + timedelta(days=2),
        )
        db_session.add(schedule)
        db_session.flush()

        # Past observation (archived)
        past_obs = Observation(
            schedule_id=schedule.id,
            observatory_name=observatory_name,
            status=ObservationStatus.ARCHIVED,
            target_name="Past Target",
            ra=180.0,
            dec=45.0,
            start_time=now - timedelta(hours=2),
            end_time=now - timedelta(hours=1),
            fov_radius=1.5,
        )

        # Future observation (scheduled)
        future_obs = Observation(
            schedule_id=schedule.id,
            observatory_name=observatory_name,
            status=ObservationStatus.SCHEDULED,
            target_name="Future Target",
            ra=90.0,
            dec=-30.0,
            start_time=now + timedelta(hours=1),
            end_time=now + timedelta(hours=2),
            fov_radius=1.5,
        )

        db_session.add_all([past_obs, future_obs])
        db_session.commit()

        return schedule

    return _create
