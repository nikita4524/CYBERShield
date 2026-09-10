"""
Unit tests for Prevention Engine, Incident Management, and Security Endpoints.
"""

import pytest
from fastapi.testclient import TestClient

from main import app
from database import get_db, Base, engine, create_all_tables
from security.prevention import prevention_engine, PreventionEngine
from security.incident_service import incident_service, get_threat_type


@pytest.fixture(autouse=True)
def setup_tables():
    create_all_tables()


@pytest.fixture
def client():
    return TestClient(app)


def test_prevention_engine_policies():
    """Test policy rules: 0-30 ALLOW, 31-60 WARN, 61-80 RESTRICT, 81-100 BLOCK/QUARANTINE/FLAG"""
    pe = PreventionEngine()

    # URL / generic
    r_safe = pe.evaluate(15, "url")
    assert r_safe.action == "ALLOW"
    assert r_safe.severity == "SAFE"
    assert not r_safe.should_create_incident

    r_warn = pe.evaluate(45, "url")
    assert r_warn.action == "WARN"
    assert r_warn.severity == "MEDIUM"
    assert not r_warn.should_create_incident

    r_restrict = pe.evaluate(75, "url")
    assert r_restrict.action == "RESTRICT"
    assert r_restrict.severity == "HIGH"
    assert r_restrict.should_create_incident

    r_block = pe.evaluate(92, "url")
    assert r_block.action == "BLOCK"
    assert r_block.severity == "CRITICAL"
    assert r_block.should_create_incident

    # Email quarantine
    r_email_high = pe.evaluate(85, "email")
    assert r_email_high.action == "QUARANTINE"
    assert r_email_high.severity == "CRITICAL"
    assert r_email_high.should_create_incident

    # Audio/Video media flag (no destructive auto-block)
    r_audio_high = pe.evaluate(90, "audio")
    assert r_audio_high.action == "FLAG"
    assert r_audio_high.severity == "CRITICAL"
    assert r_audio_high.should_create_incident

    r_video_high = pe.evaluate(88, "video")
    assert r_video_high.action == "FLAG"
    assert r_video_high.severity == "CRITICAL"
    assert r_video_high.should_create_incident


def test_url_prevention_flow(client):
    """Test POST /api/v1/analyze/url produces prevention metadata and incident on malicious URL"""
    # Safe URL
    res_safe = client.post("/api/v1/analyze/url", json={"url": "https://google.com"})
    assert res_safe.status_code == 200
    data_safe = res_safe.json()
    assert "prevention" in data_safe
    assert data_safe["prevention"]["action"] == "ALLOW"
    assert data_safe["action"] == "ALLOW"

    # Malicious URL
    res_mal = client.post(
        "/api/v1/analyze/url",
        json={"url": "http://sbi-secure-login-kyc-update-verify.xyz/otp/signin"},
    )
    assert res_mal.status_code == 200
    data_mal = res_mal.json()
    assert "prevention" in data_mal
    assert data_mal["action"] in ("BLOCK", "RESTRICT")
    assert data_mal["prevention"]["incident_id"] is not None


def test_email_quarantine_flow(client):
    """Test POST /api/v1/analyze/email with phishing signals produces QUARANTINE action"""
    res = client.post(
        "/api/v1/analyze/email",
        json={
            "subject": "URGENT: Your bank account will be blocked within 24 hours",
            "body": "Dear customer, your SBI netbanking is suspended. Click http://sbi-fake-kyc.xyz/verify to submit your OTP, PIN and password immediately or face permanent closure.",
            "sender": "security-alert@sbi-fake-kyc.xyz",
            "urls": ["http://sbi-fake-kyc.xyz/verify"],
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["action"] in ("QUARANTINE", "BLOCK", "RESTRICT")
    assert data["prevention"]["incident_id"] is not None


def test_incident_api_endpoints(client):
    """Test GET /api/v1/incidents, /stats, and PATCH status update"""
    # Trigger an incident first
    client.post(
        "/api/v1/analyze/url",
        json={"url": "http://hdfc-bank-unusual-activity-kyc-restore.xyz/account/login"},
    )

    # Get stats
    res_stats = client.get("/api/v1/incidents/stats")
    assert res_stats.status_code == 200
    stats = res_stats.json()
    assert stats["total"] >= 1

    # List incidents
    res_list = client.get("/api/v1/incidents")
    assert res_list.status_code == 200
    items = res_list.json()["items"]
    assert len(items) >= 1

    incident = items[0]
    inc_id = incident["id"]

    # Get single incident
    res_single = client.get(f"/api/v1/incidents/{inc_id}")
    assert res_single.status_code == 200
    assert res_single.json()["incident_number"] == incident["incident_number"]

    # Update status to RESOLVED
    res_patch = client.patch(
        f"/api/v1/incidents/{inc_id}",
        json={"status": "RESOLVED", "resolution_note": "Verified by security analyst"},
    )
    assert res_patch.status_code == 200
    assert res_patch.json()["status"] == "RESOLVED"
    assert res_patch.json()["resolution_note"] == "Verified by security analyst"


def test_threat_explanation_context_endpoint(client):
    """Test POST /api/v1/assistant/analyze-context"""
    payload = {
        "threat_context": {
            "threat_type": "phishing_url",
            "risk_score": 94,
            "action": "BLOCK",
            "severity": "CRITICAL",
            "reasons": ["Suspicious domain", "Credential harvesting pattern"],
            "input_reference": "http://sbi-fake.xyz/otp",
        },
        "user_query": "Why was this blocked and what should I do?",
    }
    res = client.post("/api/v1/assistant/analyze-context", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert "explanation" in data
    assert data["action"] == "BLOCK"
    assert data["severity"] == "CRITICAL"
    assert len(data["recommended_steps"]) > 0
    assert len(data["things_to_avoid"]) > 0
    assert len(data["reporting_channels"]) > 0
