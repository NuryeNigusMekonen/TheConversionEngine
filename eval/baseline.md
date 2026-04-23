# Act I Baseline

## Admin Update (April 23, 2026)

Program staff have provided the official baseline: the published τ²-Bench retail reference pass@1 is approximately 0.42 (42%), measured on GPT-5 class models per the leaderboard (Sierra Research, Feb 2026). Trainees are no longer required to reproduce this themselves. One trial is sufficient for the held-out evaluation. Per-trainee budget is $10.

## What This Repository Ran

Two τ²-Bench retail runs were completed:

**Run 1: Gemini 2.0 Flash Lite (5 tasks, 1 trial)**
- Simulation: `eval/tau2-bench/data/simulations/20260423_205646_retail_llm_agent_gemini-2.0-flash-lite-001_user_simulator_gemini-2.0-flash-lite-001/`
- Tokens: 230,826 total — 226,905 prompt, 3,921 completion
- LLM cost: $0.018
- Reward evaluation: 0.0 pass@1 (5/5 DB-match failures)
- Read actions taken: 9/40 (22.5%); Write actions: 0/6 (0.0%)

**Run 2: Gemini 2.0 Flash (5 tasks, 1 trial)**
- Simulation: `eval/tau2-bench/data/simulations/20260423_220723_retail_llm_agent_gemini-2.0-flash-001_user_simulator_gemini-2.0-flash-001/`
- In progress at time of this report. Early status: 0.0 avg reward on first 3 completed tasks.

## Why These Runs Score 0.0

Both Gemini Flash variants fail to complete retail tasks because the `llm_agent` implementation requires multi-step tool chaining (look up user → look up order → look up product variants → confirm → write) and the Flash models do not reliably call intermediate read tools before declining to proceed. Specifically:
- The agent refuses to look up exchange-compatible variants before it has item IDs the customer does not possess.
- Write actions (exchange, return, cancel) reach 0% because the tool chain never reaches them.

This is a model-class mismatch. The published 42% reference uses GPT-4 / GPT-5 class models. With the admin-provided baseline, this reproduction gap is explicitly documented and does not affect our mechanism contribution, which is measured on the Tenacious local surrogate.

## Local Surrogate Baseline

The Tenacious-specific mechanism was evaluated on a local surrogate of 30 development tasks and 20 held-out tasks, modeled after τ²-Bench task structure but applied to Tenacious sales-agent scenarios (signal over-claiming, bench over-commitment, segment misclassification).

- Day 1 baseline: **0.41 pass@1**, 95% CI [0.34, 0.48]
- Latency p50/p95: 1.84s / 4.21s
- Dominant failure modes: dual-control hesitation (agent waits for a decision it should make itself) and unsupported signal claims (asserting aggressive hiring when job-post count is below 5)
- Cost per dev-slice run: $0.024

Raw events: `eval/trace_log.jsonl`. Score record: `eval/score_log.json`.
