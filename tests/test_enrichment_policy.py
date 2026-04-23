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
