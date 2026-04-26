from agent.channels.email import email_channel
from agent.channels.sms import sms_channel
from agent.channels.voice import voice_channel
from agent.generation.service import generation_service
from agent.schemas.briefs import ProspectEnrichmentResponse
from agent.schemas.conversation import ConversationDecision
from agent.schemas.prospect import InboundMessageRequest
from agent.schemas.tools import ToolExecutionResult
from agent.seed.loader import seed_materials
from agent.scheduling.calcom import calcom_client
from agent.scheduling.context_brief import context_brief_generator
from agent.storage.repository import ProspectRepository

# ---------------------------------------------------------------------------
# SMS eligibility policy
# ---------------------------------------------------------------------------
# SMS is only used when AT LEAST ONE of the following conditions is true:
#   1. The prospect explicitly asks to be contacted via SMS/text/WhatsApp/phone.
#   2. The prospect requests fast scheduling AND a phone number is on file.
#   3. The conversation is already warm (email_reply_received recorded) AND
#      the current message is scheduling-focused.
#
# SMS is never sent on initial outreach (no email_reply_received → can_send_sms=False).
# SMS is never sent just because an email reply exists; scheduling intent is required.
# ---------------------------------------------------------------------------

_SMS_OPT_IN_TOKENS = ("sms", "text me", "whatsapp", "call me", "phone me")
_VOICE_OPT_IN_TOKENS = ("voice", "phone call", "give me a call", "ring me", "call me", "phone me")
_SCHEDULING_TOKENS = ("call", "calendar", "meet", "meeting", "schedule", "next week", "tomorrow", "book")

# ---------------------------------------------------------------------------
# Pricing objection tokens — match before checking for scheduling intent
# ---------------------------------------------------------------------------
_PRICING_TOKENS = ("price", "pricing", "cost", "rate", "budget", "how much", "cheaper", "expensive")

# ---------------------------------------------------------------------------
# Offshore concern tokens — triggers transcript-grounded response
# ---------------------------------------------------------------------------
_OFFSHORE_CONCERN_TOKENS = (
    "offshore", "outsource", "india", "eastern europe", "quality concerns",
    "rotation", "vendor", "timezone", "time zone",
)


class ChannelHandoffManager:
    """Centralized state machine for channel transitions and warm-lead gating."""

    def __init__(self, repository: ProspectRepository) -> None:
        self.repository = repository

    def current_state(self, prospect_id: str) -> str:
        if self.repository.has_interaction_event(prospect_id, "booking_confirmed"):
            return "booked"
        if self.repository.has_interaction_event(prospect_id, "voice_handoff_sent"):
            return "voice_handoff_active"
        if self.repository.has_interaction_event(prospect_id, "sms_handoff_sent"):
            return "sms_handoff_active"
        if self.repository.has_interaction_event(prospect_id, "email_reply_received"):
            return "warm_lead_ready_for_sms"
        if self.repository.has_interaction_event(prospect_id, "email_sent"):
            return "email_only"
        return "new"

    def can_send_sms(self, prospect_id: str) -> bool:
        """Base gate: returns True only if the prospect has already replied via email."""
        return self.repository.has_interaction_event(prospect_id, "email_reply_received")

    def _sms_eligible(
        self,
        prospect_id: str,
        message_body: str,
        *,
        has_phone: bool,
        scheduling_intent: bool,
    ) -> tuple[bool, str]:
        """Full eligibility check for outbound SMS per the SMS eligibility policy above.

        Returns (eligible: bool, reason: str).
        """
        if any(token in message_body for token in _SMS_OPT_IN_TOKENS):
            return True, "prospect_asked_for_sms"
        if scheduling_intent and has_phone:
            return True, "scheduling_intent_with_phone_on_file"
        if self.can_send_sms(prospect_id) and scheduling_intent:
            return True, "warm_lead_scheduling_focused"
        return False, "sms_gate_not_met"

    # ------------------------------------------------------------------
    # Reply builders (seed-grounded)
    # ------------------------------------------------------------------

    def _pricing_reply(self, contact_name: str | None) -> tuple[str, str]:
        """Build a pricing objection reply grounded in pricing_sheet.md.

        Quotes the engagement minimum and starter floor from the seed file.
        Routes deeper pricing to a human. Does NOT invent specific total-contract values.
        Per pricing_sheet.md: 'Do not negotiate, do not offer discounts, do not commit
        to specific total contract values.'
        """
        p = seed_materials.pricing
        name = contact_name or "there"
        return (
            "Tenacious pricing ranges",
            f"Hi {name},\n\n"
            f"{p.quotable_talent_floor}\n\n"
            f"For fixed-scope project work: {p.quotable_project_floor}\n\n"
            f"{p.engagement_minimum} {p.extension_cadence}\n\n"
            "A more specific number depends on scope and stack mix — "
            "I should not commit to one without a scoping conversation. "
            "I can book 15 minutes with a delivery lead who can walk you through the right package.\n\n"
            "Best,\nTenacious research workflow\nTenacious Intelligence Corporation\ngettenacious.com"
        )

    def _offshore_concern_reply(self, contact_name: str | None) -> tuple[str, str]:
        """Build an offshore-concern objection reply grounded in transcript_05.

        Uses agent-usable phrases from the objection-heavy discovery transcript.
        Does NOT use banned phrases: 'We're not like other offshore vendors',
        'Guaranteed 40% cost savings', 'We can handle any stack'.
        """
        op = seed_materials.objection_patterns
        name = contact_name or "there"
        return (
            "Tenacious delivery model",
            f"Hi {name},\n\n"
            f"{op.offshore_concern}\n\n"
            "Named-engineer stability (not a rotating pool), direct technical access "
            "without management layers, and a three-to-five hour overlap window with "
            "US time zones are the practical mechanisms.\n\n"
            f"{op.architecture_boundary}\n\n"
            "Worth 15 minutes to test whether the model fits your team's working style?\n\n"
            "Best,\nTenacious research workflow\nTenacious Intelligence Corporation\ngettenacious.com"
        )

    def _general_followup_reply(self, snapshot: ProspectEnrichmentResponse) -> tuple[str, str]:
        """Build a follow-up reply grounded in discovery transcript patterns.

        Asks a clarifying question rather than asserting a conclusion.
        Optionally references an approved case study if one matches the segment.
        """
        name = snapshot.prospect.contact_name or "there"
        segment = snapshot.prospect.primary_segment

        # Only cite a case study if one exists in the approved seed materials
        case_note = ""
        matched_case = seed_materials.find_case_study(segment)
        if matched_case:
            case_note = (
                f"\n\nFor context: {matched_case.quotable} "
                "Happy to share more detail on the discovery call."
            )

        return (
            "Tenacious research follow-up",
            f"Hi {name},\n\n"
            "Thanks for the context. The useful next step is to verify whether the "
            "public signal I found matches your actual constraint — recruiting velocity, "
            "a specific AI/data capability, or cost structure.\n\n"
            f"Which of those is closest?{case_note}\n\n"
            "Best,\nTenacious research workflow\nTenacious Intelligence Corporation\ngettenacious.com"
        )

    def _bench_mismatch_reply(self, snapshot: ProspectEnrichmentResponse) -> tuple[str, str]:
        """Build a bench-mismatch reply. Does not over-promise capacity.

        Per bench_summary.json honesty constraint: 'If a prospect's stated need
        exceeds the available_engineers count for the required stack, the agent must
        flag the mismatch and route to a human.'
        """
        name = snapshot.prospect.contact_name or "there"
        # Identify which required stacks caused the mismatch, if readable
        required = snapshot.hiring_signal_brief.bench_match.required_stacks
        available = snapshot.hiring_signal_brief.bench_match.available_capacity
        gap_stacks = [s for s in required if available.get(s, 0) == 0]

        if gap_stacks:
            gap_note = (
                f"The public signal suggests a need for {', '.join(gap_stacks)} capacity. "
                "Our delivery lead can confirm whether current bench availability fits "
                "before I make any commitment."
            )
        else:
            gap_note = (
                "The delivery lead will verify current bench availability "
                "before any capacity is committed."
            )

        return (
            "Tenacious capacity review",
            f"Hi {name},\n\n"
            f"{gap_note}\n\n"
            "I want to route this to a human review rather than committing to capacity "
            "the bench may not currently show. Expect a follow-up from the delivery lead.\n\n"
            "Best,\nTenacious research workflow\nTenacious Intelligence Corporation\ngettenacious.com"
        )

    def _booking_reply(
        self,
        snapshot: ProspectEnrichmentResponse,
        booking_link: str,
    ) -> tuple[str, str]:
        return (
            f"Booking options for {snapshot.prospect.company_name}",
            (
                f"Hi {snapshot.prospect.contact_name or 'there'},\n\n"
                "I set aside two discovery-call options for the delivery lead. "
                f"You can confirm the best slot here: {booking_link}\n\n"
                "If you prefer, reply with two windows and I will line it up manually.\n\n"
                "Best,\nTenacious research workflow\nTenacious Intelligence Corporation\ngettenacious.com"
            ),
        )

    def _rewrite_email_draft(
        self,
        *,
        snapshot: ProspectEnrichmentResponse,
        scenario: str,
        fallback_subject: str,
        fallback_body: str,
        extra_context: dict[str, object],
    ) -> str:
        draft = generation_service.draft_email_from_scaffold(
            trace_id=snapshot.trace_id,
            prospect_id=snapshot.prospect.prospect_id,
            scenario=scenario,
            company_name=snapshot.prospect.company_name,
            contact_name=snapshot.prospect.contact_name,
            fallback_subject=fallback_subject,
            fallback_body=fallback_body,
            context={
                "primary_segment": snapshot.prospect.primary_segment_label,
                "ai_maturity_score": snapshot.prospect.ai_maturity_score,
                "signals": [signal.summary for signal in snapshot.hiring_signal_brief.signals[:4]],
                "safe_gap_framing": snapshot.competitor_gap_brief.safe_gap_framing,
                "do_not_claim": snapshot.hiring_signal_brief.do_not_claim,
                **extra_context,
            },
        )
        return draft.as_reply_draft

    # ------------------------------------------------------------------
    # Warm SMS handoff
    # ------------------------------------------------------------------

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

    def prepare_voice_handoff(
        self,
        snapshot: ProspectEnrichmentResponse,
        *,
        reason: str,
        booking_link: str | None = None,
        booking_status: str | None = None,
        force_allow: bool = False,
    ) -> ToolExecutionResult:
        allow_warm_lead = force_allow or self.can_send_sms(snapshot.prospect.prospect_id)
        events = self.repository.list_interaction_events(snapshot.prospect.prospect_id)
        context_brief = context_brief_generator.build(
            snapshot,
            events=events,
            reason=reason,
            booking_link=booking_link,
            booking_status=booking_status,
        )
        voice_result = voice_channel.prepare_handoff(
            phone_number=snapshot.prospect.contact_phone,
            prospect_id=snapshot.prospect.prospect_id,
            company_name=snapshot.prospect.company_name,
            contact_name=snapshot.prospect.contact_name,
            contact_email=snapshot.prospect.contact_email,
            allow_warm_lead=allow_warm_lead,
            booking_link=booking_link,
            context_brief=context_brief.markdown,
            context_brief_artifact_ref=context_brief.artifact_ref,
            reason=reason,
        )
        if voice_result.status in {"executed", "previewed"}:
            self.repository.record_interaction_event(
                snapshot.prospect.prospect_id,
                "voice_handoff_sent",
                channel="voice",
                provider="shared_voice_rig" if voice_channel.status().configured else "mock",
                payload={"message": voice_result.message, "reason": reason},
            )
        return voice_result

    # ------------------------------------------------------------------
    # Main routing
    # ------------------------------------------------------------------

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

        # ---- Opt-out ------------------------------------------------
        if any(token in body for token in ("stop", "unsubscribe", "unsub")):
            next_action = "handoff_human"
            channel = "human"
            risk_flags.append("opt_out")
            reply = "Understood. I will stop this thread here."

        # ---- Pricing objection (seed-grounded, no invented numbers) --
        elif any(token in body for token in _PRICING_TOKENS):
            risk_flags.append("pricing_guardrail")
            subject, fallback_body = self._pricing_reply(snapshot.prospect.contact_name)
            reply = self._rewrite_email_draft(
                snapshot=snapshot,
                scenario="pricing_reply",
                fallback_subject=subject,
                fallback_body=fallback_body,
                extra_context={
                    "inbound_message": message.body,
                    "pricing_guardrail": True,
                },
            )

        # ---- Offshore concern (transcript-grounded) -------------------
        elif any(token in body for token in _OFFSHORE_CONCERN_TOKENS):
            risk_flags.append("offshore_concern")
            subject, fallback_body = self._offshore_concern_reply(snapshot.prospect.contact_name)
            reply = self._rewrite_email_draft(
                snapshot=snapshot,
                scenario="offshore_reply",
                fallback_subject=subject,
                fallback_body=fallback_body,
                extra_context={
                    "inbound_message": message.body,
                    "objection_pattern": "offshore_concern",
                },
            )

        # ---- Scheduling intent (book_meeting) ------------------------
        elif any(token in body for token in _SCHEDULING_TOKENS):
            next_action = "book_meeting"
            channel = "calendar"
            booking_link, _ = calcom_client.generate_booking_link(
                company_name=snapshot.prospect.company_name,
                contact_email=snapshot.prospect.contact_email,
                prospect_id=snapshot.prospect.prospect_id,
                source_channel="email",
            )
            subject, fallback_body = self._booking_reply(snapshot, booking_link)
            reply = self._rewrite_email_draft(
                snapshot=snapshot,
                scenario="booking_options",
                fallback_subject=subject,
                fallback_body=fallback_body,
                extra_context={
                    "inbound_message": message.body,
                    "booking_link": booking_link,
                    "requested_voice": any(token in body for token in _VOICE_OPT_IN_TOKENS),
                },
            )
            draft_subject = reply.splitlines()[0].split(":", 1)[1].strip() if reply.lower().startswith("subject:") else subject
            draft_body = "\n".join(reply.splitlines()[1:]).strip() if reply.lower().startswith("subject:") else fallback_body
            email_result = email_channel.send(
                recipient=snapshot.prospect.contact_email,
                subject=draft_subject,
                body=draft_body,
                prospect_id=snapshot.prospect.prospect_id,
            )
            side_effects.append(email_result)
            if email_result.status == "error":
                risk_flags.append("email_booking_send_failed")

            # SMS is only sent when eligibility criteria are met (see policy at top of file).
            sms_eligible, sms_reason = self._sms_eligible(
                snapshot.prospect.prospect_id,
                body,
                has_phone=bool(snapshot.prospect.contact_phone),
                scheduling_intent=True,
            )
            if sms_eligible:
                sms_result = self.prepare_warm_sms_handoff(snapshot, include_booking_link=True)
                side_effects.append(sms_result)
                if sms_result.status == "skipped":
                    risk_flags.append("sms_warm_lead_gate_blocked")
                elif sms_result.status == "error":
                    risk_flags.append("sms_handoff_failed")
            else:
                risk_flags.append(f"sms_skipped:{sms_reason}")

            if any(token in body for token in _VOICE_OPT_IN_TOKENS):
                voice_result = self.prepare_voice_handoff(
                    snapshot,
                    reason="prospect_requested_voice",
                )
                side_effects.append(voice_result)
                if voice_result.status == "skipped":
                    risk_flags.append("voice_warm_lead_gate_blocked")
                elif voice_result.status == "error":
                    risk_flags.append("voice_handoff_failed")

        # ---- Bench mismatch → human review (bench_summary.json gate) -
        elif not snapshot.hiring_signal_brief.bench_match.sufficient:
            next_action = "handoff_human"
            channel = "human"
            risk_flags.append("bench_mismatch_route_human")
            subject, fallback_body = self._bench_mismatch_reply(snapshot)
            reply = self._rewrite_email_draft(
                snapshot=snapshot,
                scenario="bench_mismatch_reply",
                fallback_subject=subject,
                fallback_body=fallback_body,
                extra_context={
                    "inbound_message": message.body,
                    "bench_match": snapshot.hiring_signal_brief.bench_match.model_dump(mode="json"),
                },
            )

        # ---- General follow-up (case study if approved, else generic) -
        else:
            subject, fallback_body = self._general_followup_reply(snapshot)
            reply = self._rewrite_email_draft(
                snapshot=snapshot,
                scenario="general_followup",
                fallback_subject=subject,
                fallback_body=fallback_body,
                extra_context={
                    "inbound_message": message.body,
                    "current_state": self.current_state(snapshot.prospect.prospect_id),
                },
            )

        decision = ConversationDecision(
            next_action=next_action,
            channel=channel,
            reply_draft=reply,
            needs_human=channel == "human",
            risk_flags=risk_flags,
            trace_tags=["inbound_reply", "channel_handoff_state_machine", "seed_grounded"],
        )
        return decision, side_effects
