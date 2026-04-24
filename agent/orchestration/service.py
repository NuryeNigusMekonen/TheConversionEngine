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
from agent.schemas.tools import ToolStatus, ToolchainReport
from agent.scheduling.calcom import calcom_client
from agent.storage.repository import ProspectRepository


class Orchestrator:
    def __init__(self) -> None:
        self.repository = ProspectRepository()
        self.trace_logger = TraceLogger()
        self.handoff_manager = ChannelHandoffManager(self.repository)

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
        self.repository.record_interaction_event(
            snapshot.prospect.prospect_id,
            "email_sent",
            channel="email",
            provider=settings.email_provider,
            payload={"subject": subject, "result": email_result.message},
        )
        sms_result = self.handoff_manager.prepare_warm_sms_handoff(
            snapshot,
            body="Warm-lead scheduling preview for Tenacious discovery-call coordination.",
        )
        hubspot_results = hubspot_client.record_conversation_event(
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
        )

        results = [
            crunchbase_connector.run(snapshot.prospect.prospect_id, matched=company_record is not None),
            job_posts_connector.run(snapshot.prospect.prospect_id, matched=jobs_record is not None),
            layoffs_connector.run(snapshot.prospect.prospect_id, matched=layoffs_record is not None),
            leadership_connector.run(snapshot.prospect.prospect_id, matched=leadership_record is not None),
            email_result,
            sms_result,
            calcom_client.book_preview(
                company_name=snapshot.prospect.company_name,
                contact_email=snapshot.prospect.contact_email,
                prospect_id=snapshot.prospect.prospect_id,
            ),
            langfuse_client.mirror_trace(
                trace_id=snapshot.trace_id or "pending",
                payload={
                    "company_name": snapshot.prospect.company_name,
                    "segment": snapshot.prospect.primary_segment,
                    "status": snapshot.prospect.status,
                },
                prospect_id=snapshot.prospect.prospect_id,
            ),
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
        decision, side_effects = self.handoff_manager.route_inbound_message(snapshot, message)
        decision = ConversationDecision(
            next_action=decision.next_action,
            channel=decision.channel,
            reply_draft=decision.reply_draft,
            needs_human=decision.needs_human,
            risk_flags=decision.risk_flags,
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
        hubspot_results = hubspot_client.record_conversation_event(
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
        )
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
        hubspot_results = hubspot_client.record_conversation_event(
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
        )
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
