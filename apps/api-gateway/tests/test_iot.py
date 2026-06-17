"""
IoT module tests — devices, telemetry rules, scoring, alerts.
"""

import os
import uuid

import pytest
from fastapi.testclient import TestClient

os.environ["TESTING"] = "true"
os.environ["MQTT_ENABLED"] = "false"

from database import Base, get_db
from main import app
from services.auth_service import auth_service
from services.iot_service import process_telemetry, seed_demo_devices
from services.iot_scoring_service import iot_scoring_service
from services.iot_rules import evaluate_telemetry_rules


@pytest.fixture(scope="function")
def client(db_session, override_get_db):
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def auth_user(db_session):
    user = auth_service.register_with_password(
        db_session,
        email=f"iot-{uuid.uuid4().hex[:8]}@test.com",
        password="TestPass123!",
        display_name="IoT Tester",
    )
    db_session.commit()
    return user


@pytest.fixture
def auth_headers(client, auth_user, db_session):
    _, token, _ = auth_service._create_token_pair(db_session, auth_user)
    db_session.commit()
    return {"Authorization": f"Bearer {token}"}


class TestIoTScoring:
    def test_no_rules_is_safe(self):
        out = iot_scoring_service.compute([])
        assert out.risk_score == 0
        assert out.risk_label == "safe"

    def test_high_rules_are_dangerous(self):
        out = iot_scoring_service.compute(["unknown_device_alert", "suspicious_dns"])
        assert out.risk_score >= 70
        assert out.risk_label == "dangerous"


class TestIoTRules:
    def test_suspicious_dns(self):
        matches = evaluate_telemetry_rules(
            "traffic",
            {"dns_query": "malware-c2.xyz"},
            device_known=True,
        )
        assert any(m.rule_id == "suspicious_dns" for m in matches)

    def test_brute_force(self):
        matches = evaluate_telemetry_rules(
            "connection",
            {"failed_logins": 10},
            device_known=True,
        )
        assert any(m.rule_id == "brute_force_attempt" for m in matches)

    def test_unknown_device(self):
        matches = evaluate_telemetry_rules(
            "connection",
            {},
            device_known=False,
            mac_address="FF:EE:DD:CC:BB:AA",
        )
        assert any(m.rule_id == "unknown_device_alert" for m in matches)


class TestIoTAPI:
    def test_register_and_list_devices(self, client, auth_headers):
        res = client.post(
            "/api/v1/iot/devices/register",
            json={
                "name": "Test Camera",
                "type": "camera",
                "location": "Hall",
                "mac_address": "AA:BB:CC:DD:EE:FF",
            },
            headers=auth_headers,
        )
        assert res.status_code == 201
        device_id = res.json()["id"]

        listing = client.get("/api/v1/iot/devices", headers=auth_headers)
        assert listing.status_code == 200
        assert listing.json()["total"] == 1

        deleted = client.delete(
            f"/api/v1/iot/devices/{device_id}",
            headers=auth_headers,
        )
        assert deleted.status_code == 204

    def test_telemetry_creates_alert(self, db_session, auth_user):
        devices = seed_demo_devices(db_session, auth_user)
        router = next(d for d in devices if d.type == "router")

        process_telemetry(
            db_session,
            {
                "device_id": str(router.id),
                "event_type": "traffic",
                "data": {"dns_query": "malware-c2.xyz"},
                "user_id": str(auth_user.id),
            },
        )

        from models.iot import IoTAlert

        alerts = (
            db_session.query(IoTAlert)
            .filter(IoTAlert.user_id == auth_user.id, IoTAlert.is_resolved.is_(False))
            .all()
        )
        assert any(a.rule_triggered == "suspicious_dns" for a in alerts)

    def test_list_alerts(self, client, auth_headers, db_session, auth_user):
        seed_demo_devices(db_session, auth_user)
        process_telemetry(
            db_session,
            {
                "user_id": str(auth_user.id),
                "mac_address": "FF:EE:DD:CC:BB:99",
                "event_type": "connection",
                "data": {},
            },
        )

        res = client.get("/api/v1/iot/alerts", headers=auth_headers)
        assert res.status_code == 200
        assert res.json()["total"] >= 1

    def test_requires_auth(self, client):
        res = client.get("/api/v1/iot/devices")
        assert res.status_code == 401
