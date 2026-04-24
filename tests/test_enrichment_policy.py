from agent.channels.email import email_channel
from agent.channels.sms import sms_channel
from agent.enrichment.service import enrichment_service
from agent.orchestration.service import orchestrator
from agent.schemas.prospect import InboundMessageRequest, LeadIntakeRequest


def test_layoff_plus_funding_routes_to_restructuring() -> None:
    prospect, brief, _ = enrichment_service.enrich(
        LeadIntakeRequest(
            company_name="OrbitStack Cloud",
            company_domain="orbitstack.dev",
        )
    )

    assert prospect.primary_segment == "mid_market_restructuring"
    assert brief.primary_segment == "Mid-market platforms restructuring cost"
    assert prospect.segment_confidence >= 0.8


def test_unknown_prospect_abstains() -> None:
    prospect, brief, _ = enrichment_service.enrich(
        LeadIntakeRequest(company_name="Unknown Co", company_domain="unknown.example")
    )

    assert prospect.primary_segment == "abstain"
    assert "segment-specific pitch" in " ".join(brief.do_not_claim)


def test_inbound_pricing_reply_does_not_invent_total() -> None:
    snapshot = orchestrator.run_toolchain(
        LeadIntakeRequest(
            company_name="ClearMint",
            company_domain="clearmint.io",
            contact_name="Amara",
            contact_email="amara@clearmint.io",
        )
    )
    decision = orchestrator.handle_inbound_message(
        InboundMessageRequest(
            prospect_id=snapshot.prospect.prospect_id,
            channel="email",
            body="What would this cost for a team?",
        )
    )

    assert decision.next_action == "send_email"
    assert "specific number depends on scope" in decision.reply_draft
    assert "pricing_guardrail" in decision.risk_flags


def test_sms_handoff_requires_prior_email_reply() -> None:
    snapshot = orchestrator.run_toolchain(
        LeadIntakeRequest(
            company_name="ClearMint",
            company_domain="clearmint.io",
            contact_name="Amara",
            contact_email="amara@clearmint.io",
            contact_phone="+254700000000",
        )
    )
    result = orchestrator.handoff_manager.prepare_warm_sms_handoff(
        snapshot,
        body="Following up with scheduling options.",
    )
    assert result.status == "skipped"
    assert "warm-lead gate" in result.message


def test_email_reply_opens_sms_handoff_gate_for_meeting_requests() -> None:
    snapshot = orchestrator.run_toolchain(
        LeadIntakeRequest(
            company_name="ClearMint",
            company_domain="clearmint.io",
            contact_name="Amara",
            contact_email="amara@clearmint.io",
            contact_phone="+254700000000",
        )
    )
    decision = orchestrator.handle_inbound_message(
        InboundMessageRequest(
            prospect_id=snapshot.prospect.prospect_id,
            contact_email="amara@clearmint.io",
            channel="email",
            body="Can we meet next week?",
        )
    )
    assert decision.next_action == "book_meeting"
    assert orchestrator.repository.has_interaction_event(
        snapshot.prospect.prospect_id,
        "email_reply_received",
    )


def test_provider_webhook_parsers_build_inbound_messages() -> None:
    resend_inbound = email_channel.handle_resend_reply_webhook(
        {
            "body": {
                "data": {
                    "from": {"email": "reply@example.com"},
                    "text": "Can we book time?",
                }
            }
        }
    )
    sms_inbound = sms_channel.handle_africastalking_webhook(
        {
            "body": {
                "from": "+254700000000",
                "text": "Thursday works for me",
            }
        }
    )
    assert resend_inbound.channel == "email"
    assert resend_inbound.contact_email == "reply@example.com"
    assert sms_inbound.channel == "sms"
    assert sms_inbound.contact_phone == "+254700000000"
