from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from agent.config import settings
from agent.observability.langfuse import langfuse_client
from agent.schemas.briefs import ProspectEnrichmentResponse


@dataclass(frozen=True)
class DiscoveryCallContextBrief:
    markdown: str
    artifact_ref: str


class DiscoveryCallContextBriefGenerator:
    def _brief_path(self, prospect_id: str) -> Path:
        settings.outbox_dir.mkdir(parents=True, exist_ok=True)
        return settings.outbox_dir / f"{prospect_id}_context_brief.md"

    def _langfuse_reference(self, snapshot: ProspectEnrichmentResponse) -> str:
        if not snapshot.trace_id:
            return "No trace recorded yet."
        if settings.langfuse_export_enabled and settings.langfuse_public_key and settings.langfuse_secret_key:
            return langfuse_client.trace_url_for(snapshot.trace_id) or (
                f"Live export enabled, internal trace id {snapshot.trace_id}"
            )
        return f"Preview mode: internal trace id {snapshot.trace_id}"

    def _signal_line(self, snapshot: ProspectEnrichmentResponse, signal_name: str) -> str:
        for signal in snapshot.hiring_signal_brief.signals:
            if signal.name == signal_name:
                return signal.summary
        return "No verified signal captured."

    def _thread_summary(self, events: list[dict]) -> list[str]:
        bullets: list[str] = []
        for event in events:
            payload = event.get("payload", {}) or {}
            event_type = event.get("event_type", "unknown_event")
            if event_type in {"email_reply_received", "sms_reply_received", "voice_reply_received"}:
                body = str(payload.get("body", "")).strip()
                if body:
                    bullets.append(f"{event_type}: {body[:180]}")
            elif event_type == "email_sent":
                subject = payload.get("subject")
                if subject:
                    bullets.append(f"Initial outreach subject: {subject}")
            elif event_type == "booking_link_shared":
                bullets.append("Booking link was shared after explicit scheduling intent.")
            elif event_type == "booking_confirmed":
                bullets.append("Prospect confirmed the booking via Cal.com.")
        return bullets[:5] or ["No substantive thread history captured yet."]

    def _objection_rows(self, events: list[dict]) -> list[tuple[str, str, str]]:
        rows: list[tuple[str, str, str]] = []
        for event in events:
            if event.get("event_type") not in {"email_reply_received", "sms_reply_received", "voice_reply_received"}:
                continue
            body = str((event.get("payload", {}) or {}).get("body", "")).lower()
            if any(token in body for token in ("price", "pricing", "cost", "budget")):
                rows.append(
                    (
                        "Pricing pressure or quote request",
                        "Stayed within public pricing bands and routed specifics to discovery.",
                        "Clarify scope before discussing exact commercial structure.",
                    )
                )
            if any(token in body for token in ("offshore", "vendor", "india", "timezone", "time zone")):
                rows.append(
                    (
                        "Offshore/vendor quality concern",
                        "Matched the objection with overlap, stability, and delivery-mechanism language.",
                        "Go deeper on named-engineer stability and overlap expectations.",
                    )
                )
        if not rows:
            rows.append(
                (
                    "No explicit objection yet",
                    "The thread is still mostly scheduling and qualification.",
                    "Confirm the main buying constraint early in the call.",
                )
            )
        return rows[:2]

    def _quoted_bands(self, events: list[dict]) -> str:
        for event in reversed(events):
            if event.get("event_type") != "reply_email_sent":
                continue
            subject = (event.get("payload", {}) or {}).get("subject", "")
            if "pricing" in subject.lower() or "re:" in subject.lower():
                return "Public pricing bands or minimums may already have been referenced in email."
        return "None explicitly quoted in-thread."

    def build(
        self,
        snapshot: ProspectEnrichmentResponse,
        *,
        events: list[dict],
        reason: str,
        booking_link: str | None = None,
        booking_status: str | None = None,
    ) -> DiscoveryCallContextBrief:
        prospect = snapshot.prospect
        brief = snapshot.hiring_signal_brief
        competitor_gap = snapshot.competitor_gap_brief
        thread_summary = self._thread_summary(events[-8:])
        objection_rows = self._objection_rows(events[-8:])
        confident_facts = [
            self._signal_line(snapshot, "funding_event"),
            self._signal_line(snapshot, "job_post_velocity"),
            brief.bench_match.recommendation,
        ]
        uncertain_facts = [
            item for item in (
                competitor_gap.sparse_sector_note,
                "Specific implementation timeline is still unconfirmed." if not booking_status else None,
                "Decision-maker map beyond the current contact is still unclear.",
            )
            if item
        ]
        missing_facts = [
            item for item in (
                "Procurement / legal process has not been discussed yet.",
                "No confirmed success metric from the prospect yet.",
                None if prospect.contact_phone else "No direct phone-based fallback beyond the booked contact record.",
            )
            if item
        ]
        original_subject = "Unknown subject"
        for event in events:
            if event.get("event_type") == "email_sent":
                original_subject = str((event.get("payload", {}) or {}).get("subject", original_subject))
                break

        suggested_opening = (
            "Start by confirming the prospect's current constraint and the public signal that opened the thread."
        )
        suggested_qualifying = (
            "Ask whether the real pressure is hiring velocity, cost discipline, leadership transition, or a specific capability gap."
        )
        suggested_capability = competitor_gap.safe_gap_framing
        suggested_commercial = (
            "Keep pricing directional unless the prospect asks for concrete structure after scoping the work."
        )
        suggested_next_step = (
            "Agree the next written artifact: proposal, scoped follow-up, or technical validation with the right stakeholder."
        )
        now_utc = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        scheduled_line = booking_status or "Pending manual confirmation"
        rows_md = "\n".join(
            f"| {objection} | {response} | {next_step} |"
            for objection, response, next_step in objection_rows
        )
        thread_md = "\n".join(
            f"{index}. {item}"
            for index, item in enumerate(thread_summary, start=1)
        )
        unknowns_md = "\n".join(f"- {item}" for item in missing_facts)
        uncertain_md = "\n".join(f"- {item}" for item in uncertain_facts)
        confident_md = "\n".join(f"- {item}" for item in confident_facts if item)
        markdown = f"""# Discovery Call Context Brief

**Prospect:** {prospect.contact_name or "Unknown contact"} at {prospect.company_name}
**Scheduled:** {scheduled_line}
**Delivery lead assigned:** Tenacious delivery lead
**Call length booked:** 30 minutes
**Thread origin:** {prospect.created_at.isoformat()} — Email subject: "{original_subject}"
**Full thread:** {self._langfuse_reference(snapshot)}

---

## 1. Segment and confidence

- **Primary segment match:** {prospect.primary_segment_label or prospect.primary_segment}
- **Confidence:** {round((prospect.segment_confidence or 0) * 100)}%
- **Why this segment:** {brief.recommended_pitch_angle}
- **Abstention risk:** {"Yes" if prospect.primary_segment == "abstain" else "No — the current brief is source-backed enough to use carefully."}

## 2. Key signals (from hiring_signal_brief.json)

- **Funding event:** {self._signal_line(snapshot, "funding_event")}
- **Hiring velocity:** {self._signal_line(snapshot, "job_post_velocity")}
- **Layoff event:** {self._signal_line(snapshot, "layoff_signal")}
- **Leadership change:** {self._signal_line(snapshot, "leadership_change")}
- **AI maturity score:** {brief.ai_maturity_score} / 3 ({brief.ai_maturity_justification})

## 3. Competitor gap findings (from competitor_gap_brief.json)

High-confidence findings the delivery lead should be ready to discuss:

- {competitor_gap.safe_gap_framing}
- Top-quartile practices visible in the sector: {", ".join(competitor_gap.top_quartile_practices[:3]) or "No durable top-quartile practice extracted."}

Findings to avoid in the call (low confidence or likely to land wrong):

- {competitor_gap.sparse_sector_note or "Avoid overstating competitor comparisons beyond the public evidence already in the brief."}

## 4. Bench-to-brief match

- **Stacks the prospect will likely need:** {", ".join(brief.bench_match.required_stacks) or "No required stacks inferred yet."}
- **Available engineers per stack (from bench_summary.json):** {brief.bench_match.available_capacity or {}}
- **Gaps:** {", ".join(stack for stack in brief.bench_match.required_stacks if brief.bench_match.available_capacity.get(stack, 0) == 0) or "No hard bench gap currently flagged."}
- **Honest flag:** {brief.bench_match.recommendation}

## 5. Conversation history summary

{thread_md}

## 6. Objections already raised (and the agent's responses)

| Objection | Agent response | Delivery lead should be ready to |
|---|---|---|
{rows_md}

## 7. Commercial signals

- **Price bands already quoted:** {self._quoted_bands(events)}
- **Has the prospect asked for a specific total contract value?** {"Yes" if any("total" in str((event.get("payload", {}) or {}).get("body", "")).lower() for event in events) else "No"}
- **Is the prospect comparing vendors?** {"Yes" if any("vendor" in str((event.get("payload", {}) or {}).get("body", "")).lower() for event in events) else "No explicit vendor comparison yet"}
- **Urgency signals:** {reason.replace("_", " ")}{"; booking link ready" if booking_link else ""}

## 8. Suggested call structure

- **Minutes 0–2:** {suggested_opening}
- **Minutes 2–10:** {suggested_qualifying}
- **Minutes 10–20:** {suggested_capability}
- **Minutes 20–25:** {suggested_commercial}
- **Minutes 25–30:** {suggested_next_step}

## 9. What NOT to do on this call

- Do not over-claim beyond the public signals or imply bench capacity that the brief does not support.
- Do not turn the first five minutes into a generic vendor pitch; anchor on the specific signal that earned the reply.

## 10. Agent confidence and unknowns

- **Things the agent is confident about:**
{confident_md}
- **Things the agent is uncertain about:**
{uncertain_md}
- **Things the agent could not find:**
{unknowns_md}
- **Overall agent confidence in this brief:** {competitor_gap.confidence:.2f}

---

*This brief was generated by the TRP1 Week 10 Conversion Engine. Trace ID: {snapshot.trace_id or "pending"}. Generated at {now_utc}.*
"""
        path = self._brief_path(prospect.prospect_id)
        path.write_text(markdown, encoding="utf-8")
        return DiscoveryCallContextBrief(markdown=markdown, artifact_ref=str(path))


context_brief_generator = DiscoveryCallContextBriefGenerator()
