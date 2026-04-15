import os

# Use test DB for the app (must set before any app import).
TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5432/test_fov_notifications",
)
os.environ["DATABASE_URL"] = TEST_DATABASE_URL

from datetime import UTC, datetime, timedelta  # noqa: E402

import pytest  # noqa: E402
from app.database import Base  # noqa: E402
from app.models.api_key import APIKey  # noqa: E402
from app.models.observation import Observation, ObservationStatus  # noqa: E402
from app.models.schedule import Schedule  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402


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


@pytest.fixture(autouse=True)
def run_task_db_work_inline(mocker):
    async def inline(fn, /, *args, **kwargs):
        return fn(*args, **kwargs)

    mocker.patch("app.tasks.retrieve_schedules.asyncio.to_thread", new=inline)
    mocker.patch("app.tasks.cleanup_schedules.asyncio.to_thread", new=inline)


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

    def _create(observatory_name="Test_Observatory", *, past_obs_still_scheduled=False):
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

        # Past observation: ARCHIVED by default (survives schedule refresh)
        past_obs = Observation(
            schedule_id=schedule.id,
            observatory_name=observatory_name,
            status=(
                ObservationStatus.SCHEDULED
                if past_obs_still_scheduled
                else ObservationStatus.ARCHIVED
            ),
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
            start_time=now + timedelta(hours=4),
            end_time=now + timedelta(hours=5),
            fov_radius=1.5,
        )

        db_session.add_all([past_obs, future_obs])
        db_session.commit()

        return schedule

    return _create


@pytest.fixture
def api_key_in_db(db_session):
    """Insert a known API key into the test DB; return the raw key for the header."""
    from auth import hash_api_key

    raw = "test-api-key"
    db_session.add(APIKey(key_hash=hash_api_key(raw), label="test"))
    db_session.commit()
    return raw
