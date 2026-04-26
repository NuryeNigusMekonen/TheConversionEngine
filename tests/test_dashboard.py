from fastapi.testclient import TestClient

from agent.main import app
from agent.orchestration.service import orchestrator
from agent.schemas.prospect import InboundMessageRequest, LeadIntakeRequest


def test_dashboard_state_exposes_latest_flow_events_and_artifacts() -> None:
    snapshot = orchestrator.run_toolchain(
        LeadIntakeRequest(
            company_name="Dashboard Voice Labs",
            company_domain="dashboardvoice.ai",
            contact_name="Riley",
            contact_email="riley.dashboard@example.com",
            contact_phone="+254700123999",
        )
    )
    orchestrator.handle_inbound_message(
        InboundMessageRequest(
            prospect_id=snapshot.prospect.prospect_id,
            contact_email="riley.dashboard@example.com",
            channel="email",
            body="Can we meet next week? Please call me.",
        )
    )
    orchestrator.handle_calendar_confirmation(
        {
            "contact_email": "riley.dashboard@example.com",
            "booking_external_id": "dashboard-booking-001",
            "booking_status": "confirmed",
            "company_name": "Dashboard Voice Labs",
        }
    )

    state = orchestrator.dashboard_state()

    assert state.latest_flow is not None
    assert state.latest_flow.prospect_id == snapshot.prospect.prospect_id
    assert state.latest_flow.voice_handoff_ready is True
    assert any(event.event_type == "voice_handoff_sent" for event in state.latest_interaction_events)
    assert any(artifact.name == "context_brief" for artifact in state.latest_artifacts)


def test_artifact_route_returns_context_brief() -> None:
    snapshot = orchestrator.run_toolchain(
        LeadIntakeRequest(
            company_name="Dashboard Artifact Labs",
            company_domain="artifactlabs.ai",
            contact_name="Nia",
            contact_email="nia.dashboard@example.com",
            contact_phone="+254700124000",
        )
    )
    orchestrator.handle_inbound_message(
        InboundMessageRequest(
            prospect_id=snapshot.prospect.prospect_id,
            contact_email="nia.dashboard@example.com",
            channel="email",
            body="Can we meet next week? Please call me.",
        )
    )
    orchestrator.handle_calendar_confirmation(
        {
            "contact_email": "nia.dashboard@example.com",
            "booking_external_id": "dashboard-booking-002",
            "booking_status": "confirmed",
            "company_name": "Dashboard Artifact Labs",
        }
    )

    client = TestClient(app)
    response = client.get(f"/artifacts/{snapshot.prospect.prospect_id}/context_brief")

    assert response.status_code == 200
    assert "Discovery Call Context Brief" in response.text
    assert "## 1. Segment and confidence" in response.text
