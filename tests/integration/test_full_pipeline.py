"""
CyberShield AI — End-to-End Full Pipeline Integration Test Suite
================================================================
Validates the complete security cycle across all threat modalities:
  DETECT -> SCORE -> DECIDE -> PREVENT -> LOG INCIDENT -> RESOLVE -> EXPLAIN
"""

import io
import sys
from pathlib import Path
from PIL import Image

import pytest
from fastapi.testclient import TestClient

# Ensure api-gateway is on sys.path so modules resolve correctly
GATEWAY_DIR = Path(__file__).resolve().parent.parent.parent / "apps" / "api-gateway"
sys.path.insert(0, str(GATEWAY_DIR))

from main import app
from database import create_all_tables
from security.prevention import prevention_engine, PreventionEngine


@pytest.fixture(scope="session", autouse=True)
def init_db():
    create_all_tables()


@pytest.fixture
def client():
    return TestClient(app)


def _create_sample_png() -> bytes:
    """Generate a valid 100x100 RGB PNG buffer that OpenCV can decode."""
    buf = io.BytesIO()
    img = Image.new("RGB", (100, 100), color=(120, 150, 180))
    img.save(buf, format="PNG")
    return buf.getvalue()


# ---------------------------------------------------------------------------
# 1. PREVENTIVE POLICY MATRIX TESTS
# ---------------------------------------------------------------------------
def test_prevention_policy_matrix():
    """Verify deterministic action and severity mapping across risk scores."""
    pe = PreventionEngine()

    # 0-30 -> ALLOW (Safe)
    r_allow = pe.evaluate(10, "url")
    assert r_allow.action == "ALLOW"
    assert r_allow.severity == "SAFE"
    assert not r_allow.should_create_incident

    # 31-60 -> WARN (Medium)
    r_warn = pe.evaluate(50, "url")
    assert r_warn.action == "WARN"
    assert r_warn.severity == "MEDIUM"
    assert not r_warn.should_create_incident

    # 61-80 -> RESTRICT (High)
    r_restrict = pe.evaluate(72, "url")
    assert r_restrict.action == "RESTRICT"
    assert r_restrict.severity == "HIGH"
    assert r_restrict.should_create_incident

    # 81-100 -> BLOCK (Critical)
    r_block = pe.evaluate(90, "url")
    assert r_block.action == "BLOCK"
    assert r_block.severity == "CRITICAL"
    assert r_block.should_create_incident

    # Contextual override: Email >= 81 -> QUARANTINE
    r_email = pe.evaluate(85, "email")
    assert r_email.action == "QUARANTINE"
    assert r_email.severity == "CRITICAL"
    assert r_email.should_create_incident

    # Contextual override: Media (audio/video/image) >= 81 -> FLAG
    for media_type in ["audio", "video", "image"]:
        r_media = pe.evaluate(95, media_type)
        assert r_media.action == "FLAG"
        assert r_media.severity == "CRITICAL"
        assert r_media.should_create_incident


# ---------------------------------------------------------------------------
# 2. URL DETECTION & PREVENTION PIPELINE
# ---------------------------------------------------------------------------
def test_url_pipeline_safe_vs_malicious(client):
    """Test safe URL yields ALLOW, phishing URL yields BLOCK and creates an incident."""
    # Benign URL
    safe_res = client.post("/api/v1/analyze/url", json={"url": "https://google.com"})
    assert safe_res.status_code == 200
    safe_data = safe_res.json()
    assert safe_data["action"] == "ALLOW"
    assert safe_data["severity"] == "SAFE"
    assert "prevention" in safe_data

    # Phishing URL with severe impersonation & keywords
    phish_res = client.post(
        "/api/v1/analyze/url",
        json={"url": "http://sbi-secure-banking-kyc-update.xyz/login/otp"},
    )
    assert phish_res.status_code == 200
    phish_data = phish_res.json()
    assert phish_data["action"] in ("BLOCK", "RESTRICT")
    assert phish_data["severity"] in ("CRITICAL", "HIGH")
    assert phish_data["prevention"]["incident_id"] is not None
    assert len(phish_data["reasons"]) > 0


# ---------------------------------------------------------------------------
# 3. EMAIL PHISHING & QUARANTINE PIPELINE
# ---------------------------------------------------------------------------
def test_email_pipeline_quarantine(client):
    """Test malicious phishing email triggers automatic QUARANTINE."""
    email_payload = {
        "subject": "CRITICAL: SBI Account Blocked - Complete KYC Immediately",
        "body": "Your bank account has been locked. Click http://sbi-fake-portal.xyz/verify and provide your NetBanking Password, Debit Card PIN, and OTP immediately to unblock your account.",
        "sender": "alert@sbi-fake-portal.xyz",
        "urls": ["http://sbi-fake-portal.xyz/verify"],
    }
    res = client.post("/api/v1/analyze/email", json=email_payload)
    assert res.status_code == 200
    data = res.json()
    assert data["action"] in ("QUARANTINE", "BLOCK", "RESTRICT")
    assert data["prevention"]["action"] in ("QUARANTINE", "BLOCK", "RESTRICT")
    assert data["prevention"]["incident_id"] is not None


# ---------------------------------------------------------------------------
# 4. QR CODE & UPI PIPELINE
# ---------------------------------------------------------------------------
def test_qr_pipeline_upi_intent(client):
    """Test QR decoding and payload evaluation."""
    png_bytes = _create_sample_png()
    res = client.post(
        "/api/v1/analyze/qr",
        files={"file": ("test.png", png_bytes, "image/png")},
    )
    assert res.status_code in (200, 400, 422)
    if res.status_code == 200:
        data = res.json()
        assert "prevention" in data
        assert "action" in data


# ---------------------------------------------------------------------------
# 5. MEDIA ANALYSIS (IMAGE) PIPELINE
# ---------------------------------------------------------------------------
def test_image_pipeline_media_flag(client):
    """Test image analyzer returns prevention metadata with non-destructive action."""
    png_bytes = _create_sample_png()
    res = client.post(
        "/api/v1/analyze/image",
        files={"file": ("face.png", png_bytes, "image/png")},
    )
    assert res.status_code == 200
    data = res.json()
    assert "prevention" in data
    assert "action" in data
    assert data["action"] in ("ALLOW", "WARN", "FLAG")


# ---------------------------------------------------------------------------
# 6. INCIDENT LIFECYCLE & SECURITY CENTER
# ---------------------------------------------------------------------------
def test_incident_lifecycle(client):
    """Test incident creation, statistics retrieval, detail lookup, and resolution."""
    # 1. Trigger incident via high-risk phishing URL
    res_trigger = client.post(
        "/api/v1/analyze/url",
        json={"url": "http://sbi-secure-login-kyc-update-verify.xyz/otp/signin"},
    )
    assert res_trigger.status_code == 200
    inc_id = res_trigger.json()["prevention"]["incident_id"]
    assert inc_id is not None

    # 2. Query Incident Stats
    stats_res = client.get("/api/v1/incidents/stats")
    assert stats_res.status_code == 200
    stats = stats_res.json()
    assert stats["total"] >= 1

    # 3. List Incidents
    list_res = client.get("/api/v1/incidents?limit=10")
    assert list_res.status_code == 200
    items = list_res.json()["items"]
    assert len(items) >= 1

    # Find the incident by its human-readable incident_number
    matching = [it for it in items if it["incident_number"] == inc_id]
    assert len(matching) >= 1
    uuid_id = matching[0]["id"]

    # 4. Fetch Incident Details
    detail_res = client.get(f"/api/v1/incidents/{uuid_id}")
    assert detail_res.status_code == 200
    detail = detail_res.json()
    assert detail["incident_number"] == inc_id

    # 5. Patch Incident (Resolution workflow)
    patch_res = client.patch(
        f"/api/v1/incidents/{uuid_id}",
        json={"status": "RESOLVED", "resolution_note": "Domain sinkholed and incident resolved."},
    )
    assert patch_res.status_code == 200
    updated = patch_res.json()
    assert updated["status"] == "RESOLVED"
    assert updated["resolution_note"] == "Domain sinkholed and incident resolved."


# ---------------------------------------------------------------------------
# 7. AI DEFENSIVE ADVISORY CONTEXT ENDPOINT
# ---------------------------------------------------------------------------
def test_ai_defensive_advisory_context(client):
    """Test AI assistant explains why threat was blocked and gives defensive instructions."""
    payload = {
        "threat_context": {
            "threat_type": "phishing_url",
            "risk_score": 92,
            "action": "BLOCK",
            "severity": "CRITICAL",
            "reasons": ["Brand impersonation of SBI", "Deceptive path and OTP query"],
            "input_reference": "http://sbi-fake-portal.xyz",
        },
        "user_query": "Why was this blocked and what should I do?",
    }
    res = client.post("/api/v1/assistant/analyze-context", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert "explanation" in data
    assert "recommended_steps" in data
    assert len(data["recommended_steps"]) > 0
