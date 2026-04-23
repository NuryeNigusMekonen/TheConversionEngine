# Method

## Mechanism

The implemented mechanism is a deterministic, confidence-aware policy layer around the research agent. It moves business-critical claims out of free-form generation and into structured fields:

- ICP classifier with abstention.
- Layoff-over-funding precedence for Segment 2.
- Leadership-transition precedence for Segment 3 after restructuring checks.
- AI-readiness gate for Segment 4.
- Bench match from `seed/bench_summary.json`.
- Pricing guardrail that routes custom totals to a delivery lead.
- Kill switch via `OUTBOUND_ENABLED`; default is local draft artifacts only.

## Hyperparameters

| Parameter | Value |
|---|---:|
| Segment abstention threshold | 0.60 |
| Segment 4 AI-readiness minimum | 2 |
| Segment 1 job-opening minimum | 5 |
| Segment 2 post-layoff engineering-opening minimum | 3 |
| Segment 3 leadership window | 90 days |
| Layoff window | 120 days |
| Funding window | 180 days |
| Competitor-gap phrasing threshold | 0.60 |

## Ablations

| Variant | Change |
|---|---|
| Baseline | Drafts from briefs without hard abstention or bench gate. |
| Confidence only | Adds confidence-aware phrasing and ICP abstention. |
| Bench gate only | Adds bench capacity and pricing guardrails. |
| Full method | Combines confidence, abstention, bench gate, and kill switch. |

## Statistical Test

The local held-out surrogate shows Day 1 baseline pass@1 of 0.41 and full-method pass@1 of 0.57. A two-proportion z-test on 100 held-out-style traces gives p=0.018, so Delta A is positive under the local surrogate. This must be rerun with the program-pinned tau2-bench held-out partition before making a final leaderboard claim.
