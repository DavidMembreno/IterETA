"""
IterETA Backend Test Suite
Run from SRC/ with: pytest tests/test_main.py -v
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.database import Base, get_db
from backend.main import app

#  In-memory SQLite database for tests
# Each test run gets a fresh database -- nothing persists between runs.
# Think of it like a flight simulator: real app code, isolated environment.

import os

SQLALCHEMY_DATABASE_URL = "sqlite:///./test_itereta.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base.metadata.create_all(bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db

client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_db():
    yield
    db = TestingSessionLocal()
    for table in reversed(Base.metadata.sorted_tables):
        db.execute(table.delete())
    db.commit()
    from backend.main import seed_default_settings
    seed_default_settings(db)
    db.commit()
    db.close()


# Helpers

def register_and_login(username="testuser", password="testpass"):
    """Register a user and return their auth token and headers."""
    res = client.post("/auth/register", json={"username": username, "password": password})
    assert res.status_code == 200
    token = res.json()["token"]
    return token, {"X-Token": token}


def create_vehicle(headers, nickname="Camry", mileage=50000):
    res = client.post("/vehicles", json={
        "nickname": nickname,
        "make": "Toyota",
        "model": "Camry",
        "year": 2007,
        "current_mileage": mileage,
    }, headers=headers)
    assert res.status_code == 200
    return res.json()


def do_full_trip(headers, vehicle_id, start="Home", end="Campus"):
    """Start and immediately end a trip, returning the completed trip."""
    start_res = client.post("/trips/start", json={
        "vehicle_id": vehicle_id,
        "start_label": start,
    }, headers=headers)
    assert start_res.status_code == 200
    trip_id = start_res.json()["id"]
    end_res = client.post(f"/trips/{trip_id}/end", json={"end_label": end}, headers=headers)
    assert end_res.status_code == 200
    return end_res.json()


# AUTH TESTS

class TestAuth:

    def test_register_creates_user_and_returns_token(self):
        res = client.post("/auth/register", json={"username": "david", "password": "pass1234"})
        assert res.status_code == 200
        data = res.json()
        assert "token" in data
        assert data["username"] == "david"
        assert len(data["token"]) > 0

    def test_register_duplicate_username_fails(self):
        client.post("/auth/register", json={"username": "david", "password": "pass1234"})
        res = client.post("/auth/register", json={"username": "david", "password": "different"})
        assert res.status_code == 400
        assert "already taken" in res.json()["detail"].lower()

    def test_login_correct_credentials(self):
        client.post("/auth/register", json={"username": "david", "password": "pass1234"})
        res = client.post("/auth/login", json={"username": "david", "password": "pass1234"})
        assert res.status_code == 200
        assert "token" in res.json()

    def test_login_wrong_password_returns_401(self):
        client.post("/auth/register", json={"username": "david", "password": "pass1234"})
        res = client.post("/auth/login", json={"username": "david", "password": "wrongpass"})
        assert res.status_code == 401

    def test_login_nonexistent_user_returns_401(self):
        res = client.post("/auth/login", json={"username": "nobody", "password": "pass"})
        assert res.status_code == 401

    def test_protected_route_without_token_returns_422(self):
        res = client.get("/vehicles")
        assert res.status_code == 422

    def test_protected_route_with_invalid_token_returns_401(self):
        res = client.get("/vehicles", headers={"X-Token": "fake-token-xyz"})
        assert res.status_code == 401

    def test_me_endpoint_returns_username(self):
        token, headers = register_and_login("david")
        res = client.get("/auth/me", headers=headers)
        assert res.status_code == 200
        assert res.json()["username"] == "david"

    def test_logout_invalidates_token(self):
        token, headers = register_and_login()
        client.post("/auth/logout", headers=headers)
        res = client.get("/vehicles", headers=headers)
        assert res.status_code == 401

    def test_password_min_length_enforced(self):
        res = client.post("/auth/register", json={"username": "david", "password": "ab"})
        assert res.status_code == 422

    def test_username_min_length_enforced(self):
        res = client.post("/auth/register", json={"username": "a", "password": "validpass"})
        assert res.status_code == 422


#  VEHICLE TESTS

class TestVehicles:

    def test_create_vehicle(self):
        _, headers = register_and_login()
        vehicle = create_vehicle(headers)
        assert vehicle["nickname"] == "Camry"
        assert vehicle["make"] == "Toyota"
        assert vehicle["current_mileage"] == 50000
        assert "id" in vehicle

    def test_list_vehicles_returns_only_own(self):
        _, h1 = register_and_login("user1")
        _, h2 = register_and_login("user2")
        create_vehicle(h1, "Camry")
        create_vehicle(h2, "Civic")
        res1 = client.get("/vehicles", headers=h1)
        res2 = client.get("/vehicles", headers=h2)
        assert len(res1.json()) == 1
        assert res1.json()[0]["nickname"] == "Camry"
        assert len(res2.json()) == 1
        assert res2.json()[0]["nickname"] == "Civic"

    def test_delete_vehicle(self):
        _, headers = register_and_login()
        vehicle = create_vehicle(headers)
        res = client.delete(f"/vehicles/{vehicle['id']}", headers=headers)
        assert res.status_code == 200
        assert client.get("/vehicles", headers=headers).json() == []

    def test_cannot_delete_other_users_vehicle(self):
        _, h1 = register_and_login("user1")
        _, h2 = register_and_login("user2")
        vehicle = create_vehicle(h1)
        res = client.delete(f"/vehicles/{vehicle['id']}", headers=h2)
        assert res.status_code == 404

    def test_update_mileage(self):
        _, headers = register_and_login()
        vehicle = create_vehicle(headers, mileage=50000)
        res = client.patch(
            f"/vehicles/{vehicle['id']}/mileage",
            json={"current_mileage": 55000},
            headers=headers,
        )
        assert res.status_code == 200
        assert res.json()["current_mileage"] == 55000

    def test_cannot_update_other_users_vehicle_mileage(self):
        _, h1 = register_and_login("user1")
        _, h2 = register_and_login("user2")
        vehicle = create_vehicle(h1)
        res = client.patch(
            f"/vehicles/{vehicle['id']}/mileage",
            json={"current_mileage": 99999},
            headers=h2,
        )
        assert res.status_code == 404

    def test_vehicle_optional_fields(self):
        _, headers = register_and_login()
        res = client.post("/vehicles", json={"nickname": "Mystery Car"}, headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert data["make"] is None
        assert data["current_mileage"] is None


#  TRIP TESTS

class TestTrips:

    def test_start_trip(self):
        _, headers = register_and_login()
        vehicle = create_vehicle(headers)
        res = client.post("/trips/start", json={
            "vehicle_id": vehicle["id"],
            "start_label": "Home",
        }, headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert data["start_label"] == "Home"
        assert data["end_time"] is None
        assert data["duration_minutes"] is None

    def test_end_trip_calculates_duration(self):
        _, headers = register_and_login()
        vehicle = create_vehicle(headers)
        trip = do_full_trip(headers, vehicle["id"])
        assert trip["end_label"] == "Campus"
        assert trip["duration_minutes"] is not None
        assert trip["duration_minutes"] >= 0

    def test_cannot_end_trip_twice(self):
        _, headers = register_and_login()
        vehicle = create_vehicle(headers)
        start_res = client.post("/trips/start", json={
            "vehicle_id": vehicle["id"], "start_label": "Home"
        }, headers=headers)
        trip_id = start_res.json()["id"]
        client.post(f"/trips/{trip_id}/end", json={"end_label": "Campus"}, headers=headers)
        res = client.post(f"/trips/{trip_id}/end", json={"end_label": "Campus"}, headers=headers)
        assert res.status_code == 400

    def test_trips_scoped_to_user(self):
        _, h1 = register_and_login("user1")
        _, h2 = register_and_login("user2")
        v1 = create_vehicle(h1)
        v2 = create_vehicle(h2)
        do_full_trip(h1, v1["id"], "Home", "Campus")
        do_full_trip(h2, v2["id"], "Work", "Gym")
        res1 = client.get("/trips", headers=h1)
        res2 = client.get("/trips", headers=h2)
        assert len(res1.json()) == 1
        assert res1.json()[0]["start_label"] == "Home"
        assert len(res2.json()) == 1
        assert res2.json()[0]["start_label"] == "Work"

    def test_cannot_start_trip_on_other_users_vehicle(self):
        _, h1 = register_and_login("user1")
        _, h2 = register_and_login("user2")
        vehicle = create_vehicle(h1)
        res = client.post("/trips/start", json={
            "vehicle_id": vehicle["id"], "start_label": "Anywhere"
        }, headers=h2)
        assert res.status_code == 404

    def test_in_progress_trip_has_no_end_time(self):
        _, headers = register_and_login()
        vehicle = create_vehicle(headers)
        res = client.post("/trips/start", json={
            "vehicle_id": vehicle["id"], "start_label": "Home"
        }, headers=headers)
        trip = res.json()
        assert trip["end_time"] is None
        assert trip["end_label"] is None

    def test_completed_trip_has_duration(self):
        _, headers = register_and_login()
        vehicle = create_vehicle(headers)
        trip = do_full_trip(headers, vehicle["id"], "Home", "Work")
        assert trip["duration_minutes"] is not None
        assert trip["end_label"] == "Work"
        assert trip["end_time"] is not None


#  SAFETY INCIDENT TESTS

class TestSafety:

    def test_create_safety_incident(self):
        _, headers = register_and_login()
        vehicle = create_vehicle(headers)
        trip = do_full_trip(headers, vehicle["id"])
        res = client.post("/safety", json={
            "trip_id": trip["id"],
            "severity": 7,
            "description": "Near miss on freeway",
        }, headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert data["severity"] == 7
        assert data["description"] == "Near miss on freeway"

    def test_severity_must_be_1_to_10(self):
        _, headers = register_and_login()
        vehicle = create_vehicle(headers)
        trip = do_full_trip(headers, vehicle["id"])
        res = client.post("/safety", json={"trip_id": trip["id"], "severity": 11}, headers=headers)
        assert res.status_code == 422

    def test_severity_below_1_rejected(self):
        _, headers = register_and_login()
        vehicle = create_vehicle(headers)
        trip = do_full_trip(headers, vehicle["id"])
        res = client.post("/safety", json={"trip_id": trip["id"], "severity": 0}, headers=headers)
        assert res.status_code == 422

    def test_safety_incidents_scoped_to_user(self):
        _, h1 = register_and_login("user1")
        _, h2 = register_and_login("user2")
        v1 = create_vehicle(h1)
        v2 = create_vehicle(h2)
        t1 = do_full_trip(h1, v1["id"])
        t2 = do_full_trip(h2, v2["id"])
        client.post("/safety", json={"trip_id": t1["id"], "severity": 5}, headers=h1)
        client.post("/safety", json={"trip_id": t2["id"], "severity": 3}, headers=h2)
        res1 = client.get("/safety", headers=h1)
        res2 = client.get("/safety", headers=h2)
        assert len(res1.json()) == 1
        assert len(res2.json()) == 1
        assert res1.json()[0]["severity"] == 5
        assert res2.json()[0]["severity"] == 3

    def test_cannot_log_incident_on_other_users_trip(self):
        _, h1 = register_and_login("user1")
        _, h2 = register_and_login("user2")
        v1 = create_vehicle(h1)
        trip = do_full_trip(h1, v1["id"])
        res = client.post("/safety", json={"trip_id": trip["id"], "severity": 5}, headers=h2)
        assert res.status_code == 404

    def test_incident_optional_description(self):
        _, headers = register_and_login()
        vehicle = create_vehicle(headers)
        trip = do_full_trip(headers, vehicle["id"])
        res = client.post("/safety", json={"trip_id": trip["id"], "severity": 3}, headers=headers)
        assert res.status_code == 200
        assert res.json()["description"] is None


#  MAINTENANCE TESTS

class TestMaintenance:

    def test_create_maintenance_record(self):
        _, headers = register_and_login()
        vehicle = create_vehicle(headers)
        res = client.post("/maintenance", json={
            "vehicle_id": vehicle["id"],
            "service_type": "Oil & Filter Change",
            "cost": 65.0,
            "mileage": 50000,
            "notes": "Synthetic oil",
        }, headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert data["service_type"] == "Oil & Filter Change"
        assert data["cost"] == 65.0
        assert data["mileage"] == 50000

    def test_maintenance_scoped_to_user(self):
        _, h1 = register_and_login("user1")
        _, h2 = register_and_login("user2")
        v1 = create_vehicle(h1)
        v2 = create_vehicle(h2)
        client.post("/maintenance", json={"vehicle_id": v1["id"], "service_type": "Oil & Filter Change"}, headers=h1)
        client.post("/maintenance", json={"vehicle_id": v2["id"], "service_type": "Tire Rotation"}, headers=h2)
        assert len(client.get("/maintenance", headers=h1).json()) == 1
        assert len(client.get("/maintenance", headers=h2).json()) == 1

    def test_cannot_log_maintenance_on_other_users_vehicle(self):
        _, h1 = register_and_login("user1")
        _, h2 = register_and_login("user2")
        vehicle = create_vehicle(h1)
        res = client.post("/maintenance", json={
            "vehicle_id": vehicle["id"], "service_type": "Oil & Filter Change"
        }, headers=h2)
        assert res.status_code == 404

    def test_maintenance_optional_fields(self):
        _, headers = register_and_login()
        vehicle = create_vehicle(headers)
        res = client.post("/maintenance", json={
            "vehicle_id": vehicle["id"], "service_type": "Tire Rotation"
        }, headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert data["cost"] is None
        assert data["mileage"] is None
        assert data["notes"] is None


#  ETA TESTS

class TestETA:

    def test_eta_returns_404_when_no_history(self):
        _, headers = register_and_login()
        res = client.get("/eta", params={"start_label": "Home", "end_label": "Campus"}, headers=headers)
        assert res.status_code == 404

    def test_eta_returns_result_with_one_trip(self):
        _, headers = register_and_login()
        vehicle = create_vehicle(headers)
        do_full_trip(headers, vehicle["id"], "Home", "Campus")
        res = client.get("/eta", params={"start_label": "Home", "end_label": "Campus"}, headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert data["trip_count"] == 1
        assert data["confidence"] == "low"
        assert data["avg_duration_minutes"] is not None
        assert data["conservative_eta_minutes"] >= data["avg_duration_minutes"]

    def test_eta_confidence_improves_with_more_trips(self):
        _, headers = register_and_login()
        vehicle = create_vehicle(headers)
        for _ in range(5):
            do_full_trip(headers, vehicle["id"], "Home", "Campus")
        res = client.get("/eta", params={"start_label": "Home", "end_label": "Campus"}, headers=headers)
        assert res.status_code == 200
        assert res.json()["confidence"] in ["moderate", "high"]
        assert res.json()["trip_count"] == 5

    def test_eta_only_uses_own_trips(self):
        _, h1 = register_and_login("user1")
        _, h2 = register_and_login("user2")
        v1 = create_vehicle(h1)
        do_full_trip(h1, v1["id"], "Home", "Campus")
        res = client.get("/eta", params={"start_label": "Home", "end_label": "Campus"}, headers=h2)
        assert res.status_code == 404

    def test_eta_route_label_must_match_exactly(self):
        _, headers = register_and_login()
        vehicle = create_vehicle(headers)
        do_full_trip(headers, vehicle["id"], "Home", "Campus")
        res = client.get("/eta", params={"start_label": "home", "end_label": "campus"}, headers=headers)
        assert res.status_code == 404

    def test_eta_conservative_is_higher_than_average(self):
        _, headers = register_and_login()
        vehicle = create_vehicle(headers)
        do_full_trip(headers, vehicle["id"], "Home", "Campus")
        res = client.get("/eta", params={"start_label": "Home", "end_label": "Campus"}, headers=headers)
        data = res.json()
        assert data["conservative_eta_minutes"] >= data["avg_duration_minutes"]

    def test_eta_returns_correct_route_string(self):
        _, headers = register_and_login()
        vehicle = create_vehicle(headers)
        do_full_trip(headers, vehicle["id"], "Home", "Campus")
        res = client.get("/eta", params={"start_label": "Home", "end_label": "Campus"}, headers=headers)
        assert "Home" in res.json()["route"]
        assert "Campus" in res.json()["route"]


#  ALERTS TESTS

class TestAlerts:

    def test_alerts_returns_200(self):
        _, headers = register_and_login()
        res = client.get("/alerts", headers=headers)
        assert res.status_code == 200
        assert "alerts" in res.json()
        assert "alert_count" in res.json()

    def test_high_severity_alert_fires(self):
        _, headers = register_and_login()
        vehicle = create_vehicle(headers)
        trip = do_full_trip(headers, vehicle["id"])
        client.post("/safety", json={"trip_id": trip["id"], "severity": 8}, headers=headers)
        client.post("/safety", json={"trip_id": trip["id"], "severity": 9}, headers=headers)
        res = client.get("/alerts", headers=headers)
        rules = [a["rule"] for a in res.json()["alerts"]]
        assert "high_severity_recent" in rules

    def test_frequency_spike_alert_fires(self):
        _, headers = register_and_login()
        vehicle = create_vehicle(headers)
        trip = do_full_trip(headers, vehicle["id"])
        for _ in range(3):
            client.post("/safety", json={"trip_id": trip["id"], "severity": 5}, headers=headers)
        res = client.get("/alerts", headers=headers)
        rules = [a["rule"] for a in res.json()["alerts"]]
        assert "frequency_spike" in rules

    def test_alerts_scoped_to_user(self):
        _, h1 = register_and_login("user1")
        _, h2 = register_and_login("user2")
        v1 = create_vehicle(h1)
        trip = do_full_trip(h1, v1["id"])
        for _ in range(3):
            client.post("/safety", json={"trip_id": trip["id"], "severity": 9}, headers=h1)
        res2 = client.get("/alerts", headers=h2)
        rules = [a["rule"] for a in res2.json()["alerts"]]
        assert "high_severity_recent" not in rules
        assert "frequency_spike" not in rules

    def test_no_alerts_with_no_data(self):
        _, headers = register_and_login()
        res = client.get("/alerts", headers=headers)
        assert res.status_code == 200
        safety_rules = [
            a["rule"] for a in res.json()["alerts"]
            if a["rule"] in ["high_severity_recent", "frequency_spike", "elevated_avg_severity"]
        ]
        assert len(safety_rules) == 0


#  SETTINGS TESTS

class TestSettings:

    def test_default_settings_seeded_on_startup(self):
        _, headers = register_and_login()
        res = client.get("/settings", headers=headers)
        assert res.status_code == 200
        keys = [s["key"] for s in res.json()]
        assert "oil_change_interval_miles" in keys
        assert "tire_rotation_interval_miles" in keys
        assert "brake_service_interval_miles" in keys
        assert "maintenance_time_gap_days" in keys

    def test_default_oil_change_interval_is_5000(self):
        _, headers = register_and_login()
        res = client.get("/settings", headers=headers)
        settings = {s["key"]: s["value"] for s in res.json()}
        assert settings["oil_change_interval_miles"] == "5000"

    def test_update_setting(self):
        _, headers = register_and_login()
        res = client.put("/settings/oil_change_interval_miles", json={"value": "3000"}, headers=headers)
        assert res.status_code == 200
        assert res.json()["value"] == "3000"

    def test_update_nonexistent_setting_returns_404(self):
        _, headers = register_and_login()
        res = client.put("/settings/fake_setting", json={"value": "999"}, headers=headers)
        assert res.status_code == 404

    def test_add_custom_interval(self):
        _, headers = register_and_login()
        res = client.post("/settings/custom-interval", json={
            "service_type": "Cabin Air Filter",
            "interval_miles": 15000,
        }, headers=headers)
        assert res.status_code == 200
        assert "cabin_air_filter" in res.json()["key"]
        assert res.json()["value"] == "15000"

    def test_delete_custom_interval(self):
        _, headers = register_and_login()
        client.post("/settings/custom-interval", json={
            "service_type": "Cabin Air Filter", "interval_miles": 15000
        }, headers=headers)
        res = client.delete(
            "/settings/custom-interval/custom_interval_cabin_air_filter_miles",
            headers=headers,
        )
        assert res.status_code == 200

    def test_cannot_delete_default_setting_via_custom_endpoint(self):
        _, headers = register_and_login()
        res = client.delete(
            "/settings/custom-interval/oil_change_interval_miles",
            headers=headers,
        )
        assert res.status_code == 400


#  ANALYTICS TESTS

class TestAnalytics:

    def test_reliability_summary_empty(self):
        _, headers = register_and_login()
        res = client.get("/analytics/reliability", headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert data["total_trips"] == 0
        assert data["completed_trips"] == 0
        assert data["completion_rate_pct"] == 0

    def test_reliability_summary_with_completed_trip(self):
        _, headers = register_and_login()
        vehicle = create_vehicle(headers)
        do_full_trip(headers, vehicle["id"], "Home", "Campus")
        res = client.get("/analytics/reliability", headers=headers)
        data = res.json()
        assert data["total_trips"] == 1
        assert data["completed_trips"] == 1
        assert data["completion_rate_pct"] == 100.0
        assert data["avg_duration_minutes"] is not None

    def test_reliability_scoped_to_user(self):
        _, h1 = register_and_login("user1")
        _, h2 = register_and_login("user2")
        v1 = create_vehicle(h1)
        do_full_trip(h1, v1["id"])
        do_full_trip(h1, v1["id"])
        res2 = client.get("/analytics/reliability", headers=h2)
        assert res2.json()["total_trips"] == 0

    def test_routes_empty_with_no_trips(self):
        _, headers = register_and_login()
        res = client.get("/analytics/routes", headers=headers)
        assert res.status_code == 200
        assert res.json() == []

    def test_routes_returns_known_route(self):
        _, headers = register_and_login()
        vehicle = create_vehicle(headers)
        do_full_trip(headers, vehicle["id"], "Home", "Campus")
        do_full_trip(headers, vehicle["id"], "Home", "Campus")
        res = client.get("/analytics/routes", headers=headers)
        assert res.status_code == 200
        routes = res.json()
        assert len(routes) == 1
        assert routes[0]["start_label"] == "Home"
        assert routes[0]["end_label"] == "Campus"
        assert routes[0]["trip_count"] == 2

    def test_routes_scoped_to_user(self):
        _, h1 = register_and_login("user1")
        _, h2 = register_and_login("user2")
        v1 = create_vehicle(h1)
        do_full_trip(h1, v1["id"], "Home", "Campus")
        res2 = client.get("/analytics/routes", headers=h2)
        assert res2.json() == []

    def test_in_progress_trip_not_counted_in_routes(self):
        _, headers = register_and_login()
        vehicle = create_vehicle(headers)
        client.post("/trips/start", json={
            "vehicle_id": vehicle["id"], "start_label": "Home"
        }, headers=headers)
        res = client.get("/analytics/routes", headers=headers)
        assert res.json() == []


#  EXPORT TESTS

class TestExports:

    def test_export_trips_returns_csv(self):
        _, headers = register_and_login()
        vehicle = create_vehicle(headers)
        do_full_trip(headers, vehicle["id"], "Home", "Campus")
        res = client.get("/export/trips", headers=headers)
        assert res.status_code == 200
        assert "text/csv" in res.headers["content-type"]
        assert "Home" in res.text
        assert "Campus" in res.text

    def test_export_safety_returns_csv(self):
        _, headers = register_and_login()
        vehicle = create_vehicle(headers)
        trip = do_full_trip(headers, vehicle["id"])
        client.post("/safety", json={"trip_id": trip["id"], "severity": 6}, headers=headers)
        res = client.get("/export/safety", headers=headers)
        assert res.status_code == 200
        assert "text/csv" in res.headers["content-type"]
        assert "6" in res.text

    def test_export_maintenance_returns_csv(self):
        _, headers = register_and_login()
        vehicle = create_vehicle(headers)
        client.post("/maintenance", json={
            "vehicle_id": vehicle["id"],
            "service_type": "Oil & Filter Change",
            "cost": 65.0,
        }, headers=headers)
        res = client.get("/export/maintenance", headers=headers)
        assert res.status_code == 200
        assert "text/csv" in res.headers["content-type"]
        assert "Oil" in res.text

    def test_export_empty_returns_no_data(self):
        _, headers = register_and_login()
        res = client.get("/export/trips", headers=headers)
        assert res.status_code == 200
        assert "no data" in res.text