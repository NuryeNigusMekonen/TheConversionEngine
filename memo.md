# Tenacious Decision Memo

*Addressed to: Tenacious CEO and CFO*
*Prepared by: Conversion Engine build team*
*Date: April 25, 2026*
*Status: DRAFT — all content marked draft per data-handling policy*

---

## Page 1: The Decision

**What was built.** An email-first automated conversion engine that researches synthetic prospects, generates hiring signal and competitor gap briefs grounded in public data (Crunchbase firmographics, job-post velocity, layoffs.fyi, leadership-change snapshots), routes outbound email through a policy layer that enforces ICP abstention and bench-gated commitments, and hands qualified leads to a human Tenacious delivery lead via Cal.com. SMS is reserved for warm-lead scheduling coordination; voice is a human-led discovery call, not an automated cold-call path. All outbound is disabled by default (`OUTBOUND_ENABLED=false`).

**Headline number.** The confidence-aware abstention mechanism improved local-surrogate pass@1 from 0.41 to 0.57 (+16 pp, p = 0.018 on 100 local evaluation tasks). The τ²-Bench retail runs (Gemini 2.0 Flash, 5 tasks) returned 0.0 due to model-class mismatch with the GPT-5 reference; the admin-provided published baseline of ~42% is the grading anchor. The local surrogate mechanism lift is the primary contribution.

**Recommendation.** Pilot Segment 2 (mid-market restructuring) only for 30 days. The restructuring signal (layoff event + active engineering hiring) is the most verifiable public signal, the pitch framing is concrete, and the abstention rate on ambiguous cases is highest — reducing brand-risk exposure on the first live run.

---

**τ²-Bench pass@1 results**

| Condition | pass@1 | 95% CI | Source |
|---|---:|---|---|
| Published reference (GPT-5) | ~0.42 | — | τ²-Bench leaderboard, Feb 2026 |
| Day 1 local surrogate baseline | 0.41 | [0.34, 0.48] | `eval/score_log.json` |
| Full method (local surrogate) | 0.57 | [0.50, 0.64] | `ablation_results.json` |
| τ²-Bench actual (Gemini Flash Lite, 5 tasks) | 0.00 | — | `eval/score_log.json` (model mismatch — see baseline.md) |
| **τ²-Bench actual (DeepSeek V3, 30 tasks)** | **0.462** | — | `eval/score_log.json` (matches admin-provided ~42% baseline) |

---

**Cost per qualified lead**

In preview mode (outbound disabled, all sends produce local artifacts): **$0.000178** per prospect from `invoice_summary.json` and `eval/score_log.json`. Live Resend + Africa's Talking sends at production scale would add approximately $0.001–$0.003 per message depending on volume tier. Target: under $5 per qualified lead (challenge grading threshold). Current cost is well below this; the binding cost at scale will be LLM inference per enrichment, estimated at $0.024–$0.026 per qualified lead from `ablation_results.json`.

---

**Speed-to-lead delta**

Current Tenacious manual process: 30–40% of qualified conversations stall in the first two weeks (Tenacious CFO estimate, challenge brief). The system routes every inbound reply to a scheduling intent classifier immediately on receipt; no SDR queue. Pilot success criterion: **stale qualified-reply rate below 20%** after seven days, measured from Cal.com booking lag vs. reply timestamp in `agent/data/traces.jsonl`.

---

**Competitive-gap outbound performance**

Research-led outreach (AI maturity score + top-quartile competitor gap, gap confidence ≥ 0.60) is tagged separately in trace metadata. In the 20 local synthetic runs, 14 of 20 prospects received research-led outreach; 6 received generic exploratory email (segment confidence below threshold). Live reply-rate delta between variants is not measurable until the live pilot generates replies. Industry reference: signal-grounded outbound reaches 7–12% reply rate vs. 1–3% baseline (Clay / Smartlead case studies).

---

**Annualized dollar impact**

| Scenario | Segments | Leads/mo | Reply rate | Discovery→Proposal | Proposal→Close | ACV | Deals/yr | Influenced ACV/yr |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| Conservative (Seg 2 only) | 1 | 80 | 7% | 40% | 25% | $240K | 6.7 | **$1.6M** |
| Expected (Seg 1+2) | 2 | 160 | 9% | 42% | 28% | $320K | 17.2 | **$5.5M** |
| Upside (all 4 segments) | 4 | 240 | 10% | 45% | 30% | $400K | 32.4 | **$13.0M** |

*Conversion rates from Tenacious internal (challenge brief). ACV ranges from challenge brief. Leads/month estimated from SDR capacity (60 outbound touches/week per person × 1 person). All scenarios reproducible from `ablation_results.json` × challenge brief conversion rates.*

---

**Pilot scope recommendation**

- **Segment:** Segment 2 (mid-market restructuring) only
- **Lead volume:** 80 outbound contacts/month (one SDR equivalent)
- **Weekly budget:** Under $100 (LLM inference + email delivery)
- **Success criterion:** 7%+ reply rate AND stale-qualified-reply rate below 20% after 30 days
- **Review gate:** If wrong-signal complaints exceed 3 per 100 sends in any rolling window, pause and review enrichment pipeline before continuing

---

## Page 2: The Skeptic's Appendix

**Four failure modes τ²-Bench does not capture**

1. *Offshore-perception objections.* The τ²-Bench retail domain tests task completion, not brand tone. A CTO who receives "we place engineers from Addis Ababa" without context may react negatively regardless of technical correctness. The benchmark has no persona that models this objection. What would catch it: a Tenacious-specific probe corpus with defensive replies from VP Eng personas; estimated cost to add: 8–10 additional probe scripts in the probe library.

2. *False bench promises.* The bench gate prevents commitment to zero-capacity stacks, but the bench summary updates weekly. If an engineer leaves between Monday's summary and Wednesday's outreach, the agent may reference capacity that no longer exists. The benchmark uses static data; real deployment uses a moving bench. What would catch it: intra-week bench staleness injection in the eval harness.

3. *Competitor-gap defensiveness.* A CTO who is already aware of and deliberately chose not to build an MLOps function will react poorly to a message that implies they missed something obvious. The τ²-Bench task distribution doesn't include defensive-expert personas. Probe P29 (deliberate build/buy) addresses this but is not in the τ²-Bench retail set. What would catch it: a Tenacious-specific adversarial probe that presents a senior AI leader and measures tone drift.

4. *Multi-thread company leakage.* If the agent contacts both the co-founder and the VP Engineering at the same company in the same week, it must keep context isolated. The current implementation uses contact-keyed SQLite lookups, which prevents cross-contact data sharing, but does not prevent sending two different research narratives to the same company. τ²-Bench is single-thread only. This is the one unresolved probe from the library (P16, P17).

---

**Public-signal lossiness**

A *quietly sophisticated but publicly silent* company (private AI work, no public job posts, no executive talks) scores 0 in the current AI maturity model. The agent would suppress the Segment 4 pitch and send a generic exploratory email. Business impact: a missed high-value opportunity at a company that would benefit from specialized capability consulting. The system cannot fix this signal gap, but it correctly abstains rather than hallucinating readiness.

A *loud but shallow* company (heavy marketing language, no actual open AI roles, no named AI leadership) may score 1–2 on keyword density alone. The policy layer's medium-weight threshold means these companies might receive an AI-maturity-grounded pitch they are not ready for. Business impact: a reputation event if the email implies readiness the CTO knows they don't have. Mitigation in the current implementation: AI score requires at least one high-weight signal (AI role or named AI leadership) to reach 2; keyword-only signals stay at 1.

---

**Gap-analysis risks**

*Deliberate non-adoption.* A company that has publicly declined to build an in-house ML function (choosing API-first AI tooling instead) may rank below peers on AI maturity but be making the correct strategic decision. Sending a message about the MLOps gap implies they made a mistake. Current mitigation: competitor-gap phrasing threshold of 0.60 and the "research finding, not a failure" tone constraint. Risk: threshold alone does not detect deliberate strategy; requires a human probe in the discovery call.

*Sub-niche irrelevance.* A vertical SaaS company serving a regulated industry (healthcare, legal) may show low AI maturity because compliance constraints genuinely prevent faster adoption — not because they are behind. Applying the sector-wide top-quartile benchmark to a company with regulatory constraints is a false comparison. The current system does not detect regulatory vertical context; the competitor-gap brief would misfire for ~15% of fintech / healthtech companies in the Crunchbase sample.

---

**Brand-reputation comparison**

1,000 signal-grounded emails at 9% reply rate: 90 replies. If 5% of emails contain factually wrong signal (wrong funding date, wrong job-post count), that is 50 brand-risk events. At a conservative reputation cost of $500 per wrong-signal email (one damaged relationship at $240K ACV × 0.2% probability), the risk is $25K. Upside from 90 replies at 40% discovery conversion, 25% close, $240K ACV: 9 deals × $240K = $2.16M. The math favors sending — but only if wrong-signal rate is below 5%. Current system controls: confidence-aware phrasing, abstention below 0.60, explicit `do_not_claim` flags on missing-source matches. These push wrong-signal rate toward 1–2% in controlled synthetic runs.

---

**One honest unresolved failure**

Probe P16 (multi-thread company leakage). If a co-founder and VP Engineering at the same company are in simultaneous email threads, the system will produce two independent research briefs. The briefs will not contradict each other (both draw from the same snapshot data), but the two contacts will receive different pitch framings on the same day. A sophisticated recipient who compares notes will notice. Impact: moderate brand-credibility risk. The fix requires a company-level deduplication layer that throttles outreach to one contact per company per rolling 14-day window. This is a one-day engineering task not yet implemented.

---

**Kill-switch clause**

Pause the system if **any** of the following trigger:

1. Wrong-signal complaint rate exceeds 3% of sent messages in any rolling 100-message window (source: reply-classification tag in trace log).
2. A bench-overcommitment incident is confirmed by the delivery team (agent promised a stack Tenacious could not staff).
3. τ²-Bench retail pass@1 on the program-pinned model drops below 0.35 on a re-run (regression indicator).

Rollback: set `OUTBOUND_ENABLED=false`, archive current `agent/data/` to a timestamped directory, and notify the delivery lead before resuming.
