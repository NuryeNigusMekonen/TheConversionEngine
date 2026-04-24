from agent.channels.email import email_channel
from agent.channels.sms import sms_channel
from agent.schemas.briefs import ProspectEnrichmentResponse
from agent.schemas.conversation import ConversationDecision
from agent.schemas.prospect import InboundMessageRequest
from agent.schemas.tools import ToolExecutionResult
from agent.storage.repository import ProspectRepository


class ChannelHandoffManager:
    """Centralized state machine for channel transitions and warm-lead gating."""

    def __init__(self, repository: ProspectRepository) -> None:
        self.repository = repository

    def current_state(self, prospect_id: str) -> str:
        if self.repository.has_interaction_event(prospect_id, "booking_confirmed"):
            return "booked"
        if self.repository.has_interaction_event(prospect_id, "sms_handoff_sent"):
            return "sms_handoff_active"
        if self.repository.has_interaction_event(prospect_id, "email_reply_received"):
            return "warm_lead_ready_for_sms"
        if self.repository.has_interaction_event(prospect_id, "email_sent"):
            return "email_only"
        return "new"

    def can_send_sms(self, prospect_id: str) -> bool:
        return self.repository.has_interaction_event(prospect_id, "email_reply_received")

    def prepare_warm_sms_handoff(
        self,
        snapshot: ProspectEnrichmentResponse,
        *,
        body: str | None = None,
        include_booking_link: bool = False,
    ) -> ToolExecutionResult:
        allow_warm_lead = self.can_send_sms(snapshot.prospect.prospect_id)
        if include_booking_link:
            sms_result, _ = sms_channel.send_booking_options(
                phone_number=snapshot.prospect.contact_phone,
                prospect_id=snapshot.prospect.prospect_id,
                company_name=snapshot.prospect.company_name,
                contact_name=snapshot.prospect.contact_name,
                contact_email=snapshot.prospect.contact_email,
                allow_warm_lead=allow_warm_lead,
            )
        else:
            sms_result = sms_channel.send(
                phone_number=snapshot.prospect.contact_phone,
                body=body or "Warm-lead scheduling handoff for Tenacious.",
                prospect_id=snapshot.prospect.prospect_id,
                allow_warm_lead=allow_warm_lead,
            )
        if sms_result.status in {"executed", "previewed"}:
            self.repository.record_interaction_event(
                snapshot.prospect.prospect_id,
                "sms_handoff_sent",
                channel="sms",
                provider="africastalking" if sms_channel.status().configured else "mock",
                payload={"message": sms_result.message},
            )
        return sms_result

    def route_inbound_message(
        self,
        snapshot: ProspectEnrichmentResponse,
        message: InboundMessageRequest,
    ) -> tuple[ConversationDecision, list[ToolExecutionResult]]:
        body = message.body.lower()
        risk_flags: list[str] = []
        side_effects: list[ToolExecutionResult] = []
        next_action = "send_email"
        channel = "email"
        reply = ""

        if any(token in body for token in ("stop", "unsubscribe", "unsub")):
            next_action = "handoff_human"
            channel = "human"
            risk_flags.append("opt_out")
            reply = "Understood. I will stop this thread here."
        elif any(token in body for token in ("price", "pricing", "cost", "rate", "budget")):
            risk_flags.append("pricing_guardrail")
            reply = (
                f"Hi {snapshot.prospect.contact_name or 'there'},\n\n"
                "For managed engineering capacity, Tenacious quotes public monthly bands by role and seniority. "
                "For fixed-scope AI or data work, starter projects begin at the public project floor in our pricing sheet.\n\n"
                "A specific number depends on scope and stack mix, so I should not invent one here. "
                "Open to a 15-minute scoping call with a delivery lead?\n\n"
                "Best,\nTenacious research workflow"
            )
        elif any(token in body for token in ("call", "calendar", "meet", "meeting", "next week", "tomorrow")):
            next_action = "book_meeting"
            channel = "calendar"
            email_result, reply = email_channel.send_booking_options(
                recipient=snapshot.prospect.contact_email,
                prospect_id=snapshot.prospect.prospect_id,
                company_name=snapshot.prospect.company_name,
                contact_name=snapshot.prospect.contact_name,
                contact_email=snapshot.prospect.contact_email,
            )
            side_effects.append(email_result)
            sms_result = self.prepare_warm_sms_handoff(
                snapshot,
                include_booking_link=True,
            )
            side_effects.append(sms_result)
            if email_result.status == "error":
                risk_flags.append("email_booking_send_failed")
            if sms_result.status == "skipped":
                risk_flags.append("sms_warm_lead_gate_blocked")
            if sms_result.status == "error":
                risk_flags.append("sms_handoff_failed")
        elif not snapshot.hiring_signal_brief.bench_match.sufficient:
            next_action = "handoff_human"
            channel = "human"
            risk_flags.append("bench_mismatch_route_human")
            reply = (
                "This prospect's inferred stack does not fully match visible bench capacity. "
                "Human review is required before promising staffing."
            )
        else:
            reply = (
                f"Hi {snapshot.prospect.contact_name or 'there'},\n\n"
                "Thanks for the context. The useful next step is to verify whether the public signal matches your actual constraint: "
                "recruiting velocity, a specific AI/data capability, or cost structure.\n\n"
                "Which of those is closest?\n\n"
                "Best,\nTenacious research workflow"
            )

        decision = ConversationDecision(
            next_action=next_action,
            channel=channel,
            reply_draft=reply,
            needs_human=channel == "human",
            risk_flags=risk_flags,
            trace_tags=["inbound_reply", "channel_handoff_state_machine"],
        )
        return decision, side_effects
