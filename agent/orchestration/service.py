import logging
import time
from collections.abc import Callable
from typing import TypeVar

from agent.channels.email import email_channel
from agent.channels.sms import sms_channel
from agent.config import settings
from agent.crm.hubspot import hubspot_client
from agent.enrichment.service import enrichment_service
from agent.enrichment.connectors import (
    crunchbase_connector,
    job_posts_connector,
    layoffs_connector,
    leadership_connector,
)
from agent.evaluation.tau2 import tau2_adapter
from agent.observability.langfuse import langfuse_client
from agent.observability.tracing import TraceLogger
from agent.orchestration.handoff import ChannelHandoffManager
from agent.policies.service import policy_service
from agent.schemas.briefs import ProspectEnrichmentResponse
from agent.schemas.conversation import ConversationDecision
from agent.schemas.dashboard import DashboardStateResponse, RecentTrace
from agent.schemas.prospect import InboundMessageRequest, LeadIntakeRequest, ProspectRecord
from agent.schemas.tools import ToolExecutionResult, ToolStatus, ToolchainReport
from agent.scheduling.calcom import calcom_client
from agent.storage.repository import ProspectRepository

logger = logging.getLogger(__name__)

_T = TypeVar("_T")


def _with_retries(
    fn: Callable[[], _T],
    *,
    max_attempts: int = 3,
    delay_secs: float = 0.5,
) -> _T:
    """Bounded exponential-backoff retry for safe idempotent tool calls.

    Use only for idempotent operations (HubSpot contact upsert, Langfuse mirror).
    Never use for email or SMS sends — those are not idempotent without verified
    idempotency keys and a retry would result in duplicate outbound messages.

    A result is considered failed when it is a ToolExecutionResult with status="error",
    or a list where any element has status="error".
    """
    last: _T | None = None
    for attempt in range(max_attempts):
        last = fn()
        failed = (
            any(r.status == "error" for r in last)  # type: ignore[union-attr]
            if isinstance(last, list)
            else (isinstance(last, ToolExecutionResult) and last.status == "error")
        )
        if not failed or attempt == max_attempts - 1:
            return last  # type: ignore[return-value]
        time.sleep(delay_secs * (2**attempt))
    return last  # type: ignore[return-value]


class Orchestrator:
    def __init__(self) -> None:
        self.repository = ProspectRepository()
        self.trace_logger = TraceLogger()
        self.handoff_manager = ChannelHandoffManager(self.repository)

    # ------------------------------------------------------------------
    # Tool failure handling
    # ------------------------------------------------------------------

    def _handle_tool_result(
        self,
        result: ToolExecutionResult | list[ToolExecutionResult],
        prospect_id: str,
        context: str,
        *,
        critical: bool = False,
    ) -> bool:
        """Inspect result(s), log failures to trace JSONL and SQLite.

        Returns True when all results are healthy (executed/previewed/skipped).
        Returns False when any result has status="error".

        critical=True signals that a failure should route to human review upstream.
        """
        results = result if isinstance(result, list) else [result]
        all_ok = True
        for r in results:
            if r.status == "error":
                all_ok = False
                logger.error(
                    "Tool failure: tool=%s context=%s prospect=%s message=%s critical=%s",
                    r.name,
                    context,
                    prospect_id,
                    r.message,
                    critical,
                )
                self.trace_logger.log(
                    "tool_failure",
                    {
                        "prospect_id": prospect_id,
                        "tool": r.name,
                        "context": context,
                        "message": r.message,
                        "artifact_ref": r.artifact_ref,
                        "critical": critical,
                    },
                )
                self.repository.record_interaction_event(
                    prospect_id,
                    "tool_failure",
                    channel=r.name,
                    provider=r.name,
                    payload={
                        "context": context,
                        "message": r.message,
                        "critical": critical,
                    },
                )
        return all_ok

    # ------------------------------------------------------------------
    # Core pipeline
    # ------------------------------------------------------------------

    def intake_and_enrich(self, intake: LeadIntakeRequest) -> ProspectEnrichmentResponse:
        prospect, hiring_signal_brief, competitor_gap_brief = enrichment_service.enrich(intake)
        decision = policy_service.draft_initial_decision(
            prospect=prospect,
            hiring_signal_brief=hiring_signal_brief,
            competitor_gap_brief=competitor_gap_brief,
        )

        trace_id = self.trace_logger.log(
            "prospect_enriched",
            {
                "prospect_id": prospect.prospect_id,
                "company_name": prospect.company_name,
                "primary_segment": prospect.primary_segment,
                "ai_maturity_score": prospect.ai_maturity_score,
                "risk_flags": decision.risk_flags,
            },
        )

        return self.repository.save_snapshot(
            prospect=prospect,
            hiring_signal_brief=hiring_signal_brief,
            competitor_gap_brief=competitor_gap_brief,
            initial_decision=decision,
            trace_id=trace_id,
        )

    def run_toolchain(self, intake: LeadIntakeRequest) -> ProspectEnrichmentResponse:
        snapshot = self.intake_and_enrich(intake)
        decision = snapshot.initial_decision
        subject, body = self._extract_email_payload(decision.reply_draft if decision else "")
        company_record = crunchbase_connector.lookup(intake.company_name, intake.company_domain)
        jobs_record = job_posts_connector.lookup(intake.company_name, intake.company_domain)
        layoffs_record = layoffs_connector.lookup(intake.company_name, intake.company_domain)
        leadership_record = leadership_connector.lookup(intake.company_name, intake.company_domain)

        email_result = email_channel.send(
            recipient=snapshot.prospect.contact_email,
            subject=subject,
            body=body,
            prospect_id=snapshot.prospect.prospect_id,
        )
        self._handle_tool_result(email_result, snapshot.prospect.prospect_id, "initial_email_send", critical=True)
        self.repository.record_interaction_event(
            snapshot.prospect.prospect_id,
            "email_sent",
            channel="email",
            provider=settings.email_provider,
            payload={"subject": subject, "result": email_result.message},
        )

        # SMS is gated by can_send_sms() which requires email_reply_received.
        # On initial outreach this always returns "skipped" — that is correct behaviour.
        sms_result = self.handoff_manager.prepare_warm_sms_handoff(
            snapshot,
            body="Warm-lead scheduling preview for Tenacious discovery-call coordination.",
        )
        self._handle_tool_result(sms_result, snapshot.prospect.prospect_id, "initial_sms_preview")

        calcom_result = calcom_client.book_preview(
            company_name=snapshot.prospect.company_name,
            contact_email=snapshot.prospect.contact_email,
            prospect_id=snapshot.prospect.prospect_id,
        )
        self._handle_tool_result(calcom_result, snapshot.prospect.prospect_id, "scheduling_preview")

        # Langfuse mirror — idempotent, safe to retry.
        langfuse_result = _with_retries(
            lambda: langfuse_client.mirror_trace(
                trace_id=snapshot.trace_id or "pending",
                payload={
                    "company_name": snapshot.prospect.company_name,
                    "segment": snapshot.prospect.primary_segment,
                    "status": snapshot.prospect.status,
                },
                prospect_id=snapshot.prospect.prospect_id,
            ),
            max_attempts=3,
        )
        self._handle_tool_result(langfuse_result, snapshot.prospect.prospect_id, "langfuse_mirror")

        # HubSpot contact upsert + enrichment write — idempotent, safe to retry.
        # Note: record_conversation_event also creates an activity note, which is not
        # idempotent; a retry may produce a duplicate note in HubSpot but that is
        # preferable to silently dropping the CRM sync on a transient error.
        hubspot_results = _with_retries(
            lambda: hubspot_client.record_conversation_event(
                {
                    "company_name": snapshot.prospect.company_name,
                    "company_domain": snapshot.prospect.company_domain,
                    "email": snapshot.prospect.contact_email,
                    "contact_name": snapshot.prospect.contact_name,
                    "phone": snapshot.prospect.contact_phone,
                    "segment": snapshot.prospect.primary_segment_label,
                    "segment_confidence": snapshot.prospect.segment_confidence,
                    "ai_maturity_score": snapshot.prospect.ai_maturity_score,
                    "bench_match": snapshot.hiring_signal_brief.bench_match.model_dump(mode="json"),
                    "trace_id": snapshot.trace_id,
                },
                snapshot.prospect.prospect_id,
                activity_type="initial_outreach_prepared",
                activity_summary="Initial email outreach prepared from enrichment and policy output.",
                metadata={"channel_state": self.handoff_manager.current_state(snapshot.prospect.prospect_id)},
            ),
            max_attempts=2,  # bounded to 2 to limit duplicate activity notes
        )
        self._handle_tool_result(hubspot_results, snapshot.prospect.prospect_id, "hubspot_crm_sync")

        results = [
            crunchbase_connector.run(snapshot.prospect.prospect_id, matched=company_record is not None),
            job_posts_connector.run(snapshot.prospect.prospect_id, matched=jobs_record is not None),
            layoffs_connector.run(snapshot.prospect.prospect_id, matched=layoffs_record is not None),
            leadership_connector.run(snapshot.prospect.prospect_id, matched=leadership_record is not None),
            email_result,
            sms_result,
            calcom_result,
            langfuse_result,
            tau2_adapter.readiness_check(),
        ]
        results.extend(hubspot_results)
        toolchain_report = ToolchainReport(
            statuses=self.tool_statuses(),
            results=results,
        )

        trace_id = self.trace_logger.log(
            "toolchain_run",
            {
                "prospect_id": snapshot.prospect.prospect_id,
                "company_name": snapshot.prospect.company_name,
                "results": [result.model_dump(mode="json") for result in results],
            },
        )

        return self.repository.save_snapshot(
            prospect=snapshot.prospect,
            hiring_signal_brief=snapshot.hiring_signal_brief,
            competitor_gap_brief=snapshot.competitor_gap_brief,
            initial_decision=snapshot.initial_decision,
            trace_id=trace_id,
            toolchain_report=toolchain_report,
        )

    def handle_inbound_message(self, message: InboundMessageRequest) -> ConversationDecision:
        snapshot = None
        if message.prospect_id:
            snapshot = self.repository.get_snapshot(message.prospect_id)
        if snapshot is None:
            snapshot = self.repository.find_snapshot_by_contact(
                contact_email=message.contact_email,
                contact_phone=message.contact_phone,
            )
        if snapshot is None:
            decision = ConversationDecision(
                next_action="handoff_human",
                channel="human",
                reply_draft=(
                    "I could not match this reply to a saved prospect thread. "
                    "Route to a human before sending a response."
                ),
                needs_human=True,
                risk_flags=["unknown_thread"],
                trace_tags=["inbound_reply", "handoff"],
            )
            self.trace_logger.log("inbound_reply_unmatched", message.model_dump(mode="json"))
            return decision

        body = message.body.lower()
        event_type = "email_reply_received" if message.channel == "email" else "sms_reply_received"
        self.repository.record_interaction_event(
            snapshot.prospect.prospect_id,
            event_type,
            channel=message.channel,
            provider=message.channel,
            payload={"body": body},
        )

        raw_decision, side_effects = self.handoff_manager.route_inbound_message(snapshot, message)

        # ------------------------------------------------------------------
        # Reply-send gap fix: when the handoff manager returns next_action="send_email",
        # the reply_draft must be sent — not just returned to the caller as a string.
        # If the send fails we flag it but still return the decision so the caller
        # can route to human review via the risk_flags list.
        # ------------------------------------------------------------------
        additional_risk_flags: list[str] = []
        if raw_decision.next_action == "send_email" and raw_decision.reply_draft:
            subject, reply_body = self._extract_email_payload(raw_decision.reply_draft)
            reply_subject = f"Re: {subject}" if not subject.lower().startswith("re:") else subject
            reply_email_result = email_channel.send(
                recipient=snapshot.prospect.contact_email,
                subject=reply_subject,
                body=reply_body,
                prospect_id=snapshot.prospect.prospect_id,
            )
            ok = self._handle_tool_result(
                reply_email_result,
                snapshot.prospect.prospect_id,
                "inbound_reply_email_send",
                critical=True,
            )
            if not ok:
                additional_risk_flags.append("reply_email_send_failed")
            else:
                self.repository.record_interaction_event(
                    snapshot.prospect.prospect_id,
                    "reply_email_sent",
                    channel="email",
                    provider=settings.email_provider,
                    payload={"subject": reply_subject, "result": reply_email_result.message},
                )

        decision = ConversationDecision(
            next_action=raw_decision.next_action,
            channel=raw_decision.channel,
            reply_draft=raw_decision.reply_draft,
            needs_human=raw_decision.needs_human or bool(additional_risk_flags),
            risk_flags=raw_decision.risk_flags + additional_risk_flags,
            trace_tags=["inbound_reply", "policy_guarded", "central_handoff_manager"],
        )

        self.trace_logger.log(
            "inbound_reply_handled",
            {
                "prospect_id": snapshot.prospect.prospect_id,
                "company_name": snapshot.prospect.company_name,
                "channel": message.channel,
                "next_action": decision.next_action,
                "risk_flags": decision.risk_flags,
            },
        )
        if decision.next_action == "book_meeting":
            self.repository.record_interaction_event(
                snapshot.prospect.prospect_id,
                "booking_link_shared",
                channel="calendar",
                provider="calcom",
                payload={"source_channel": message.channel},
            )

        # HubSpot sync — idempotent contact upsert + enrichment write. Bounded retry.
        hubspot_results = _with_retries(
            lambda: hubspot_client.record_conversation_event(
                {
                    "company_name": snapshot.prospect.company_name,
                    "company_domain": snapshot.prospect.company_domain,
                    "email": snapshot.prospect.contact_email,
                    "contact_name": snapshot.prospect.contact_name,
                    "phone": snapshot.prospect.contact_phone,
                    "segment": snapshot.prospect.primary_segment_label,
                    "segment_confidence": snapshot.prospect.segment_confidence,
                    "ai_maturity_score": snapshot.prospect.ai_maturity_score,
                    "bench_match": snapshot.hiring_signal_brief.bench_match.model_dump(mode="json"),
                    "last_inbound_channel": message.channel,
                    "last_reply_next_action": decision.next_action,
                    "trace_id": snapshot.trace_id,
                    "booking_status": "pending_confirmation" if decision.next_action == "book_meeting" else None,
                },
                snapshot.prospect.prospect_id,
                activity_type=f"{message.channel}_reply_received",
                activity_summary=f"Inbound {message.channel} reply processed with next action {decision.next_action}.",
                metadata={
                    "risk_flags": decision.risk_flags,
                    "side_effects": [effect.model_dump(mode="json") for effect in side_effects],
                    "channel_state": self.handoff_manager.current_state(snapshot.prospect.prospect_id),
                },
            ),
            max_attempts=2,
        )
        self._handle_tool_result(hubspot_results, snapshot.prospect.prospect_id, "hubspot_inbound_sync")

        return decision

    def handle_calendar_confirmation(self, confirmation: dict[str, str]) -> dict[str, object]:
        snapshot = self.repository.find_snapshot_by_contact(contact_email=confirmation["contact_email"])
        if snapshot is None:
            self.trace_logger.log("calendar_confirmation_unmatched", confirmation)
            return {"ok": False, "matched": False, "reason": "No prospect matched the booking confirmation."}

        self.repository.record_interaction_event(
            snapshot.prospect.prospect_id,
            "booking_confirmed",
            channel="calendar",
            provider="calcom",
            payload=confirmation,
        )
        self.repository.update_status(snapshot.prospect.prospect_id, "booked")
        hubspot_results = _with_retries(
            lambda: hubspot_client.record_conversation_event(
                {
                    "company_name": snapshot.prospect.company_name,
                    "company_domain": snapshot.prospect.company_domain,
                    "email": snapshot.prospect.contact_email,
                    "contact_name": snapshot.prospect.contact_name,
                    "phone": snapshot.prospect.contact_phone,
                    "segment": snapshot.prospect.primary_segment_label,
                    "segment_confidence": snapshot.prospect.segment_confidence,
                    "ai_maturity_score": snapshot.prospect.ai_maturity_score,
                    "bench_match": snapshot.hiring_signal_brief.bench_match.model_dump(mode="json"),
                    "trace_id": snapshot.trace_id,
                    "booking_status": confirmation["booking_status"],
                },
                snapshot.prospect.prospect_id,
                activity_type="calendar_booking_confirmed",
                activity_summary="Cal.com booking confirmation received and prospect marked as booked.",
                metadata=confirmation,
            ),
            max_attempts=2,
        )
        self._handle_tool_result(hubspot_results, snapshot.prospect.prospect_id, "hubspot_booking_confirmed_sync")
        trace_id = self.trace_logger.log(
            "calendar_booking_confirmed",
            {
                "prospect_id": snapshot.prospect.prospect_id,
                "company_name": snapshot.prospect.company_name,
                "booking_external_id": confirmation["booking_external_id"],
                "booking_status": confirmation["booking_status"],
                "hubspot_results": [result.model_dump(mode="json") for result in hubspot_results],
            },
        )
        return {
            "ok": True,
            "matched": True,
            "prospect_id": snapshot.prospect.prospect_id,
            "trace_id": trace_id,
        }

    def list_prospects(self) -> list[ProspectRecord]:
        return self.repository.list_all()

    def get_snapshot(self, prospect_id: str) -> ProspectEnrichmentResponse | None:
        return self.repository.get_snapshot(prospect_id)

    def dashboard_state(self, limit: int = 6) -> DashboardStateResponse:
        traces = [
            RecentTrace(
                trace_id=entry["trace_id"],
                event_type=entry["event_type"],
                timestamp=entry["timestamp"],
                company_name=entry["payload"].get("company_name"),
                prospect_id=entry["payload"].get("prospect_id"),
            )
            for entry in self.trace_logger.recent(limit=limit)
        ]
        return DashboardStateResponse(
            total_prospects=self.repository.count(),
            total_traces=self.trace_logger.count(),
            tool_statuses=self.tool_statuses(),
            recent_snapshots=self.repository.list_recent_snapshots(limit=limit),
            recent_traces=traces,
        )

    def tool_statuses(self) -> list[ToolStatus]:
        return [
            crunchbase_connector.status(),
            job_posts_connector.status(),
            layoffs_connector.status(),
            leadership_connector.status(),
            email_channel.status(),
            sms_channel.status(),
            hubspot_client.status(),
            calcom_client.status(),
            langfuse_client.status(),
            tau2_adapter.status(),
        ]

    def _extract_email_payload(self, draft: str) -> tuple[str, str]:
        lines = [line for line in draft.splitlines() if line.strip()]
        if lines and lines[0].lower().startswith("subject:"):
            subject = lines[0].split(":", 1)[1].strip() or "Tenacious research note"
            body = "\n".join(lines[1:]).strip()
            return subject, body
        return "Tenacious research note", draft


orchestrator = Orchestrator()
