# Tenacious Decision Memo

## Page 1: The Decision

We built an email-first conversion engine that researches synthetic prospects, generates hiring signal and competitor gap briefs, routes replies, prepares HubSpot/Cal.com artifacts, and keeps outbound disabled unless `OUTBOUND_ENABLED=true`. The local surrogate evaluation improved from 0.41 to 0.57 pass@1 after adding ICP abstention, signal-confidence phrasing, and bench-gated commitments. Recommendation: pilot only Segment 2 for 30 days because the restructuring signal is concrete, high urgency, and easiest to police for over-claiming.

Baseline: local tau2-retail-style surrogate is 0.41 pass@1 with 95% CI 0.34-0.48. Full method is 0.57 with 95% CI 0.50-0.64. Published tau2 retail reference should be cited only after the pinned harness is run; this repo records readiness, not a public leaderboard claim.

Cost per qualified lead in preview mode is $0.22 from `invoice_summary.json`. Live email/SMS costs are zero in this run because the kill switch defaults to local draft artifacts.

Manual Tenacious stalled-thread rate is 30-40% from the challenge brief. The system's local scheduling path records every inbound reply and routes scheduling intent immediately to Cal.com preview or live booking, so the pilot success criterion should be under 20% stale qualified replies after seven days.

Competitive-gap outbound should be the default only when gap confidence is at least 0.60. For lower-confidence records, use exploratory outreach. In the local traces, research-led variants are tagged separately so reply-rate delta can be computed once live replies exist.

Annualized impact should be modeled conservatively: one Segment 2 pilot, 80 leads/month, 7% reply rate, 40% discovery-to-proposal, 25% proposal-to-close, and $240K low-end ACV gives roughly 6.7 deals/year or $1.6M low-case influenced ACV. Two segments doubles lead volume with higher uncertainty. All four segments should wait until false-signal rate is measured.

Pilot: Segment 2 only, 80 synthetic-reviewed outbound leads/month, weekly budget under $100, success criterion of 7%+ reply rate with under 3% wrong-signal complaints.

## Page 2: The Skeptic's Appendix

Four deployment risks tau2 does not capture: offshore-perception objections from CTOs, false bench promises, competitor-gap defensiveness, and public-signal lossiness. The benchmark can test conversation mechanics, but it does not know whether "offshore" language damages the Tenacious brand or whether a staffing promise is operationally true.

Quietly sophisticated companies will score too low because private AI work leaves little public signal. Loud but shallow companies may score too high because marketing language can mimic maturity. The current policy softens both by asking rather than asserting unless job, leadership, or stack evidence is visible.

Gap analysis is risky when a peer practice is irrelevant to the prospect's sub-niche or when the prospect deliberately chose not to follow the sector. The safe framing is "public signal we saw in peers" rather than "you are behind."

If 1,000 signal-grounded emails get a 9% reply rate but 5% contain wrong signal data, the upside is 90 replies and the downside is 50 brand-risk events. At an assumed $500 reputation cost per wrong-signal email, the risk is $25K; at 40% proposal conversion and 25% close on $240K ACV, 90 replies can still clear that threshold, but only if wrong-signal rate stays below 3%.

Unresolved failure: multi-thread leakage across two contacts at the same company is not fully solved beyond contact-keyed lookup. Kill switch: pause the system if wrong-signal complaints exceed 3% of sent messages in any rolling 100-message window or if any bench-overcommitment incident occurs.
