# ruff: noqa: S101
import pytest
from app.database import get_db
from app.main import app
from fastapi.testclient import TestClient


class _AuthClient:
    """Wraps TestClient and adds X-API-Key header by default."""

    def __init__(self, test_client: TestClient, api_key: str):
        self._client = test_client
        self._headers = {"X-API-Key": api_key}

    def get(self, url: str, **kwargs):
        headers = {**self._headers, **kwargs.pop("headers", {})}
        return self._client.get(url, headers=headers, **kwargs)


@pytest.fixture
def client(db_engine, db_session, api_key_in_db):
    """Test client using real API key auth; sends test key by default."""

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    yield _AuthClient(TestClient(app), api_key_in_db)
    app.dependency_overrides.clear()


class TestScheduleRoutes:
    """Tests for schedule endpoints."""

    def test_get_schedule_requires_auth(self):
        """Test that endpoints require authentication."""
        response = TestClient(app).get("/schedule")
        assert response.status_code == 422  # Missing API key

    def test_invalid_api_key_returns_401(self, client):
        """Test that an invalid API key is rejected by real auth."""
        response = client.get("/schedule", headers={"X-API-Key": "wrong-key"})
        assert response.status_code == 401
        assert "Invalid or missing API key" in response.json()["detail"]

    def test_get_full_schedule(self, client, create_schedule):
        """Test getting combined schedule for all observatories."""
        create_schedule("Observatory_A")
        create_schedule("Observatory_B")

        response = client.get("/schedule")

        assert response.status_code == 200
        data = response.json()

        assert "schedules" in data
        assert len(data["schedules"]) == 2
        names = {s["observatory_name"] for s in data["schedules"]}
        assert names == {"Observatory_A", "Observatory_B"}

        # Each schedule should only include scheduled (not archived) observations
        for schedule in data["schedules"]:
            assert len(schedule["observations"]) == 1

    def test_get_observatory_schedule(self, api_key_in_db, client, create_schedule):
        """Test getting schedule for a specific observatory."""
        create_schedule("test_observatory")
        response = client.get("/schedule/test_observatory")

        assert response.status_code == 200
        data = response.json()

        assert data["observatory_name"] == "test_observatory"
        assert "observations" in data
        assert "schedule_start" in data
        assert "created_at" in data

    def test_get_observatory_schedule_not_found(self, client):
        """Test 404 when observatory doesn't exist."""
        response = client.get("/schedule/NonExistent")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"]

    def test_get_schedule_with_hours_filter(self, client, create_schedule):
        """Test filtering observations by hours parameter."""
        create_schedule("test_observatory")
        # Request next 6 hours - should get the observation
        # (future obs is 4 hours ahead)
        response = client.get("/schedule/test_observatory?hours=6")
        assert response.status_code == 200
        data = response.json()
        assert len(data["observations"]) == 1

        # Verify hours parameter is accepted
        response = client.get("/schedule/test_observatory?hours=1")
        assert response.status_code == 200

        # Request next 3 hours - should not get any observations
        response = client.get("/schedule/test_observatory?hours=3")
        assert response.status_code == 200
        data = response.json()
        assert len(data["observations"]) == 0

    def test_get_healpix_schedule(self, client, create_schedule):
        """Test getting HEALPix schedule for all observatories."""
        create_schedule("Observatory_A")
        create_schedule("Observatory_B")

        response = client.get("/schedule/healpix")
        assert response.status_code == 200
        data = response.json()
        assert "schedules" in data
        assert len(data["schedules"]) == 2
        names = {s["observatory_name"] for s in data["schedules"]}
        assert names == {"Observatory_A", "Observatory_B"}

        # Each schedule should only include scheduled (not archived) observations
        for schedule in data["schedules"]:
            assert len(schedule["pixel_indices"]) == 1
            assert schedule["n_side"] == 16
            assert schedule["ordering"] == "nested"

    def test_get_healpix_observatory_schedule(self, client, create_schedule):
        """Test getting HEALPix schedule for a specific observatory."""
        create_schedule("test_observatory")
        response = client.get("/schedule/test_observatory/healpix")

        assert response.status_code == 200
        data = response.json()

        assert data["observatory_name"] == "test_observatory"
        assert "pixel_indices" in data
        assert len(data["pixel_indices"]) == 1
        assert data["n_side"] == 16
        assert data["ordering"] == "nested"

    def test_get_healpix_rubin_schedule(self, client, create_schedule):
        """Test getting HEALPix schedule for a specific observatory."""
        create_schedule("rubin")
        response = client.get("/schedule/rubin/healpix")
        assert response.status_code == 200
        data = response.json()
        assert data["observatory_name"] == "rubin"
        assert "pixel_indices" in data
        assert len(data["pixel_indices"]) == 24
        assert data["n_side"] == 32

    def test_healpix_direction_absent_by_default(self, client, create_schedule):
        """Without include_direction, pixel_directions should be omitted/null."""
        create_schedule("test_observatory")
        response = client.get("/schedule/test_observatory/healpix")
        assert response.status_code == 200
        assert response.json()["pixel_directions"] is None

    def test_healpix_direction_included(self, client, create_schedule, db_session):
        """With include_direction, each scheduled pixel gets an AltAz direction."""
        schedule = create_schedule("test_observatory")
        # The fixture uses an out-of-range latitude; set a real one so AltAz resolves.
        schedule.observatory_latitude = -30.244633
        schedule.observatory_longitude = -70.749417
        db_session.commit()

        response = client.get(
            "/schedule/test_observatory/healpix?include_direction=true"
        )
        assert response.status_code == 200
        data = response.json()

        # One SCHEDULED future observation -> one (non-deduplicated) pixel direction.
        directions = data["pixel_directions"]
        assert directions is not None
        assert len(directions) == len(data["pixel_indices"]) == 1

        entry = directions[0]
        assert entry["index"] == data["pixel_indices"][0]
        assert "time" in entry
        assert 0.0 <= entry["azimuth"] <= 360.0
        assert -90.0 <= entry["altitude"] <= 90.0

    def test_healpix_direction_included_all_observatories(
        self, client, create_schedule, db_session
    ):
        """include_direction also works on the combined (all observatories) endpoint."""
        schedule = create_schedule("Observatory_A")
        schedule.observatory_latitude = -30.244633
        schedule.observatory_longitude = -70.749417
        db_session.commit()

        response = client.get("/schedule/healpix?include_direction=true")
        assert response.status_code == 200
        schedules = response.json()["schedules"]
        assert len(schedules) == 1
        assert len(schedules[0]["pixel_directions"]) == 1
