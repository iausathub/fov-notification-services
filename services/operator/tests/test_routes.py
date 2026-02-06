# ruff: noqa: S101
import pytest
from app.database import get_db
from app.dependencies import get_current_user
from app.main import app
from fastapi.testclient import TestClient


@pytest.fixture
def client(db_session):
    """Create a test client with overridden dependencies."""

    def override_get_db():
        yield db_session

    def override_get_current_user():
        return {"api_key": "test-key"}

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user

    yield TestClient(app)

    app.dependency_overrides.clear()


class TestScheduleRoutes:
    """Tests for schedule endpoints."""

    def test_get_schedule_requires_auth(self, db_session):
        """Test that endpoints require authentication."""

        # Create client without auth override
        def override_get_db():
            yield db_session

        app.dependency_overrides[get_db] = override_get_db

        client = TestClient(app)
        response = client.get("/schedule")

        # Should fail without X-API-Key header
        assert response.status_code == 422  # Missing required header

        app.dependency_overrides.clear()

    def test_get_full_schedule(self, client, create_schedule):
        """Test getting combined schedule for all observatories."""
        create_schedule("Observatory_A")
        create_schedule("Observatory_B")

        response = client.get("/schedule", headers={"X-API-Key": "test"})

        assert response.status_code == 200
        data = response.json()

        assert "schedules" in data
        assert len(data["schedules"]) == 2
        names = {s["observatory_name"] for s in data["schedules"]}
        assert names == {"Observatory_A", "Observatory_B"}

        # Each schedule should only include scheduled (not archived) observations
        for schedule in data["schedules"]:
            assert len(schedule["observations"]) == 1

    def test_get_observatory_schedule(self, client, create_schedule):
        """Test getting schedule for a specific observatory."""
        create_schedule("test_observatory")
        response = client.get(
            "/schedule/test_observatory",
            headers={"X-API-Key": "test"},
        )

        assert response.status_code == 200
        data = response.json()

        assert data["observatory_name"] == "test_observatory"
        assert "observations" in data
        assert "schedule_start" in data
        assert "created_at" in data

    def test_get_observatory_schedule_not_found(self, client):
        """Test 404 when observatory doesn't exist."""
        response = client.get(
            "/schedule/NonExistent",
            headers={"X-API-Key": "test"},
        )

        assert response.status_code == 404
        assert "not found" in response.json()["detail"]

    def test_get_schedule_with_hours_filter(self, client, create_schedule):
        """Test filtering observations by hours parameter."""
        create_schedule("test_observatory")
        # Request next 6 hours - should get the observation (future obs is 1 hour ahead)
        response = client.get(
            "/schedule/test_observatory?hours=6",
            headers={"X-API-Key": "test"},
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["observations"]) == 1

        # Verify hours parameter is accepted
        response = client.get(
            "/schedule/test_observatory?hours=1",
            headers={"X-API-Key": "test"},
        )
        assert response.status_code == 200
