"""Pytest fixtures for the test suite."""

import os

import pytest
from app.database import Base
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
