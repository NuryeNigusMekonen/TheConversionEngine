# Act I Baseline

This repository records a tau2-retail-style local surrogate baseline because the pinned program harness is not present at `eval/tau2-bench` yet. The scoring contract mirrors the required fields: pass@1, 95% confidence interval, cost per run, and p50/p95 latency, with raw events in `eval/trace_log.jsonl`.

The Day 1 baseline is 0.41 pass@1 on 30 local tasks over five trials, with a 95% CI of 0.34 to 0.48. The small reproduction check is 0.43 pass@1 on three smoke tasks, with wider uncertainty because it is only a readiness check. Median latency is 1.84s and p95 is 4.21s.

Unexpected behavior: the highest-cost failures were not generic wrong answers. They were dual-control hesitation and unsupported claims when the agent tried to answer faster than the brief allowed. That is why the implemented mechanism focuses on confidence-aware phrasing, ICP abstention, and bench-gated commitments.
