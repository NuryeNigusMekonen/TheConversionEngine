from agent.schemas.briefs import CompetitorGapBrief, HiringSignalBrief
from agent.schemas.conversation import ConversationDecision
from agent.schemas.prospect import ProspectRecord


class PolicyService:
    def _strongest_signal(self, hiring_signal_brief: HiringSignalBrief) -> str:
        if not hiring_signal_brief.signals:
            return "I found only partial public signal for your team."
        signal = max(hiring_signal_brief.signals, key=lambda item: item.confidence)
        if signal.confidence < 0.65:
            return f"I found a partial signal worth checking: {signal.summary}"
        return signal.summary

    def draft_initial_decision(
        self,
        prospect: ProspectRecord,
        hiring_signal_brief: HiringSignalBrief,
        competitor_gap_brief: CompetitorGapBrief,
    ) -> ConversationDecision:
        risk_flags = []
        if any(signal.score < 0.5 for signal in hiring_signal_brief.confidence_by_signal):
            risk_flags.append("low_confidence_signal_present")
        if competitor_gap_brief.confidence < 0.5:
            risk_flags.append("omit_strong_competitor_gap_claims")
        if prospect.primary_segment == "abstain" or prospect.segment_confidence < 0.6:
            risk_flags.append("segment_abstention")
        if not hiring_signal_brief.bench_match.sufficient:
            risk_flags.append("bench_mismatch_route_human")
        if "Do not present development-mode estimates as verified public facts." in hiring_signal_brief.do_not_claim:
            risk_flags.append("development_mode_only")

        first_signal = self._strongest_signal(hiring_signal_brief)
        peer_note = ""
        if competitor_gap_brief.confidence >= 0.6 and prospect.primary_segment != "abstain":
            first_peer = competitor_gap_brief.peer_companies[0] if competitor_gap_brief.peer_companies else "a peer"
            first_practice = (
                competitor_gap_brief.top_quartile_practices[0]
                if competitor_gap_brief.top_quartile_practices
                else "Delivery priorities are more legible in public."
            )
            peer_note = (
                f"\n\nOne peer signal stood out: {first_peer}. {first_practice} "
                "I would treat that as a question, not a conclusion."
            )
        ask = (
            "Would it be useful if I sent the two-page research note?"
            if prospect.primary_segment == "abstain"
            else "Open to a 15-minute readout next week?"
        )
        company_for_subject = prospect.company_name
        subject = f"Context: {company_for_subject} engineering signal"
        if len(subject) > 58:
            subject = "Context: engineering signal"
        body = (
            f"Hi {prospect.contact_name or 'there'},\n\n"
            f"{first_signal}\n\n"
            "I am not assuming this means you need external capacity. "
            f"The reason I am reaching out is that this maps to Tenacious's "
            f"{hiring_signal_brief.primary_segment} lens with "
            f"{prospect.segment_confidence:.0%} confidence."
            f"{peer_note}\n\n"
            f"{ask}\n\n"
            "Best,\n"
            "Tenacious research workflow\n"
            "Tenacious Intelligence Corporation\n"
            "gettenacious.com"
        )

        return ConversationDecision(
            next_action="send_email",
            channel="email",
            reply_draft=(
                f"Subject: {subject}\n\n"
                f"{body}"
            ),
            needs_human=not hiring_signal_brief.bench_match.sufficient,
            risk_flags=risk_flags,
            trace_tags=["draft_initial_outreach", "confidence_aware_policy"],
        )


policy_service = PolicyService()
