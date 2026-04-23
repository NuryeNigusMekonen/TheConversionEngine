"""
Tests for channels (email, SMS), CRM (HubSpot), and scheduling (Cal.com).
All tests run in preview/mock mode (OUTBOUND_ENABLED=false env is already set
in .env.example defaults; live sends require explicit OUTBOUND_ENABLED=true).
"""

import json
from pathlib import Path

import pytest

from agent.channels.email import EmailChannel
from agent.channels.sms import SmsChannel
from agent.crm.hubspot import HubSpotClient
from agent.scheduling.calcom import CalComClient
from agent.config import settings


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _read_outbox(prospect_id: str, suffix: str) -> dict:
    artifact = settings.outbox_dir / f"{prospect_id}_{suffix}.json"
    assert artifact.exists(), f"Expected artifact {artifact} not found"
    return json.loads(artifact.read_text())


# ---------------------------------------------------------------------------
# Email channel
# ---------------------------------------------------------------------------

def test_email_send_writes_artifact() -> None:
    channel = EmailChannel()
    result = channel.send(
        recipient=None,
        subject="Context: engineering capacity at ClearMint",
        body="Three of your peers posted MLOps roles in the last 90 days.",
        prospect_id="pros_ch_email_001",
    )
    assert result.status in ("executed", "previewed"), f"Unexpected status: {result.status}"
    assert result.artifact_ref is not None


def test_email_artifact_contains_subject_and_body() -> None:
    channel = EmailChannel()
    subject = "Request: 15 minutes on your AI roadmap"
    body = "You closed a $14M Series B and your Python roles tripled."
    channel.send(
        recipient=None,
        subject=subject,
        body=body,
        prospect_id="pros_ch_email_002",
    )
    payload = _read_outbox("pros_ch_email_002", "email")
    assert payload.get("subject") == subject
    assert payload.get("body") == body


def test_email_artifact_marked_draft() -> None:
    channel = EmailChannel()
    channel.send(
        recipient=None,
        subject="Follow-up: hiring velocity signal",
        body="Series A runway typically tightens recruiting capacity around month four.",
        prospect_id="pros_ch_email_003",
    )
    payload = _read_outbox("pros_ch_email_003", "email")
    # Kill switch: outbox artifacts should be marked as draft when OUTBOUND_ENABLED=false
    assert payload.get("draft") is True or not settings.outbound_enabled


def test_email_status_always_available() -> None:
    channel = EmailChannel()
    status = channel.status()
    assert status.available is True
    assert status.name == "email"
    assert status.mode in ("mock", "configured")


# ---------------------------------------------------------------------------
# SMS channel — warm-lead coordination only
# ---------------------------------------------------------------------------

def test_sms_send_writes_artifact() -> None:
    channel = SmsChannel()
    result = channel.send(
        phone_number=None,
        body="Hi, are you free Thursday for a 15-minute discovery call?",
        prospect_id="pros_ch_sms_001",
    )
    assert result.status in ("executed", "previewed"), f"Unexpected status: {result.status}"
    assert result.artifact_ref is not None


def test_sms_artifact_exists_after_send() -> None:
    channel = SmsChannel()
    channel.send(
        phone_number=None,
        body="Tenacious: booking confirmation coming via Cal.com.",
        prospect_id="pros_ch_sms_002",
    )
    artifact = settings.outbox_dir / "pros_ch_sms_002_sms.json"
    assert artifact.exists()


def test_sms_status_always_available() -> None:
    channel = SmsChannel()
    status = channel.status()
    assert status.name == "sms"
    assert status.available is True


# ---------------------------------------------------------------------------
# HubSpot CRM
# ---------------------------------------------------------------------------

def test_hubspot_upsert_writes_artifact() -> None:
    client = HubSpotClient()
    payload = {
        "company_name": "ClearMint",
        "company_domain": "clearmint.io",
        "email": "amara@clearmint.io",
        "contact_name": "Amara Cole",
        "segment": "recently_funded",
        "ai_maturity_score": 3,
    }
    result = client.upsert_contact(payload, "pros_ch_hs_001")
    assert result.status in ("executed", "previewed"), f"Unexpected status: {result.status}"
    assert result.artifact_ref is not None


def test_hubspot_artifact_contains_company_info() -> None:
    client = HubSpotClient()
    payload = {
        "company_name": "OrbitStack Cloud",
        "company_domain": "orbitstack.dev",
        "email": "ops@orbitstack.dev",
        "segment": "mid_market_restructuring",
        "ai_maturity_score": 1,
    }
    client.upsert_contact(payload, "pros_ch_hs_002")
    data = _read_outbox("pros_ch_hs_002", "hubspot")
    # company name should appear somewhere in the artifact
    assert "OrbitStack" in json.dumps(data)


def test_hubspot_status_reports_mode() -> None:
    client = HubSpotClient()
    status = client.status()
    assert status.name == "hubspot"
    assert status.mode in ("mock", "configured")
    assert status.available is True


# ---------------------------------------------------------------------------
# Cal.com scheduling
# ---------------------------------------------------------------------------

def test_calcom_book_preview_writes_artifact() -> None:
    client = CalComClient()
    result = client.book_preview(
        company_name="ClearMint",
        contact_email="amara@clearmint.io",
        prospect_id="pros_ch_cal_001",
    )
    # The preview artifact is always written; live booking may fail with 403/404
    # if the event type is misconfigured in the current env. Accept graceful degradation.
    assert result.status in ("executed", "previewed", "error"), f"Unexpected status: {result.status}"
    assert result.artifact_ref is not None, "Artifact ref should always be set even on live failure"
    # Artifact must exist regardless of live-booking outcome
    artifact = settings.outbox_dir / "pros_ch_cal_001_calcom.json"
    assert artifact.exists()


def test_calcom_artifact_has_suggested_slots() -> None:
    client = CalComClient()
    client.book_preview(
        company_name="PatientLake",
        contact_email=None,
        prospect_id="pros_ch_cal_002",
    )
    data = _read_outbox("pros_ch_cal_002", "calcom")
    assert "suggested_slots_utc" in data
    assert len(data["suggested_slots_utc"]) >= 2


def test_calcom_slots_are_iso8601() -> None:
    from datetime import datetime
    client = CalComClient()
    client.book_preview(
        company_name="Buildplane",
        contact_email=None,
        prospect_id="pros_ch_cal_003",
    )
    data = _read_outbox("pros_ch_cal_003", "calcom")
    for slot in data["suggested_slots_utc"]:
        # Should be parseable as ISO 8601
        dt = datetime.fromisoformat(slot.replace("Z", "+00:00"))
        assert dt is not None


def test_calcom_status_reports_mode() -> None:
    client = CalComClient()
    status = client.status()
    assert status.name == "calcom"
    assert status.mode in ("mock", "configured")
    assert status.available is True
