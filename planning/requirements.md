# Conversion Engine Requirements

This document turns the Week 10 Tenacious challenge into an implementation-facing requirements spec for this repository.

## 1. Product Goal

Build an automated lead generation and conversion system for Tenacious Consulting and Outsourcing that:

- discovers synthetic prospects from public data,
- enriches each prospect with grounded public signals,
- composes research-led outbound email,
- handles replies and qualification,
- hands warm scheduling to SMS when appropriate,
- books a discovery call,
- writes the full interaction history to HubSpot,
- logs traces and evaluation artifacts needed for grading.

The system must prioritize grounded claims, brand safety, and evidence-backed reporting over raw outreach volume.

## 2. Challenge Constraints

## 2.1 Source of truth

- The Tenacious challenge document is the governing spec.
- The supporting scenario is reference material only.
- If they conflict, Tenacious requirements win.

## 2.2 Channel strategy

- Primary outreach channel is email.
- SMS is secondary and only for warm leads or scheduling coordination.
- Voice is not a core requirement for this build.

## 2.3 Data policy

- Use only public and challenge-provided data.
- Do not fabricate prospect facts, customer history, or bench capacity.
- Every prospect used during challenge week must be synthetic.
- Any deployment-capable outbound flow must default to a kill-switch-safe mode.

## 2.4 Cost and quality constraints

- Keep per-qualified-lead economics within challenge expectations.
- Tenacious target is under `$5` per qualified lead.
- Cost above `$8` per qualified lead creates grading risk.
- Every numeric claim in final reporting must map to traces, provided Tenacious numbers, or public sources.

## 3. Core Functional Requirements

## 3.1 Prospect research and enrichment

Before first outreach, the system must produce a grounded prospect package that includes:

- Crunchbase firmographics
- recent funding signal within the last 180 days
- job-post signal and velocity from public pages
- layoffs.fyi signal within the last 120 days
- leadership-change signal for new CTO or VP Engineering
- AI maturity score from `0-3` with per-input justification
- per-signal confidence scores
- competitor gap brief comparing the prospect to top-quartile peers

Required output artifacts:

- `hiring_signal_brief.json`
- `competitor_gap_brief.json`

## 3.2 ICP and segment logic

The agent must classify or abstain across the four Tenacious ICP segments:

- recently-funded Series A/B startups
- mid-market platforms restructuring cost
- engineering-leadership transitions
- specialized capability gaps

Requirements:

- segment confidence must be explicit
- the system must avoid hard assertions when signals are weak
- Segment 4 outreach must be gated on AI maturity `>= 2`
- post-layoff and recently-funded overlap must be handled carefully

## 3.3 Outreach generation

The system must generate outbound email that:

- is grounded in the enrichment brief
- follows Tenacious tone constraints
- avoids unsupported claims
- references competitor-gap findings carefully and non-condescendingly
- adapts phrasing to confidence level

The system should support at least two outbound variants:

- generic Tenacious pitch
- research-led competitive-gap pitch

This is required for later reply-rate comparison in the memo.

## 3.4 Reply handling and qualification

The system must:

- receive email replies by webhook
- persist thread state
- qualify against ICP and inferred need
- avoid promising capacity absent bench confirmation
- route pricing beyond public tiers to a human
- escalate ambiguous or risky cases instead of bluffing

## 3.5 Bench-aware routing

The system must check prospect need against Tenacious bench summary and:

- confirm only supported bench-to-brief matches
- never commit unavailable staffing
- hand off to a human when staffing specificity exceeds known capacity

## 3.6 SMS handoff

The system must support warm scheduling follow-up via SMS:

- only after email engagement or clear preference
- preserve thread context from email
- support scheduling coordination
- avoid treating SMS as cold outreach primary

## 3.7 Scheduling

The system must:

- offer valid Cal.com slots
- create a booking successfully
- handle timezone-sensitive scheduling across US, EU, and East Africa
- write scheduling state back to HubSpot

## 3.8 CRM and observability

The system must:

- write conversation events to HubSpot
- capture enrichment timestamps
- record trace data for enrichment, prompting, replies, handoffs, and booking
- support cost, latency, and stalled-thread analysis from trace outputs

## 4. Evaluation and Deliverable Requirements

## 4.1 Act I

Required:

- `eval/score_log.json`
- `eval/trace_log.jsonl`
- `baseline.md`

Acceptance criteria:

- retail baseline reproduced on the dev slice
- five-trial pass@1 with mean and 95% CI
- cost and latency recorded

## 4.2 Act II

Required:

- one full synthetic email-to-SMS-to-calendar journey
- populated HubSpot record
- Cal.com booking artifact
- p50 and p95 latency over at least 20 synthetic interactions

Acceptance criteria:

- one prospect can be enriched, emailed, replied to, qualified, booked, and logged end to end
- all required signals are visible in stored artifacts

## 4.3 Act III

Required:

- `probes/probe_library.md`
- `probes/failure_taxonomy.md`
- `probes/target_failure_mode.md`

Acceptance criteria:

- at least 30 structured probes
- probes cover Tenacious-specific risks, not only generic LLM failure modes
- one target failure mode selected by business-cost impact

## 4.4 Act IV

Required:

- `method.md`
- `ablation_results.json`
- `held_out_traces.jsonl`

Acceptance criteria:

- mechanism improves over Day 1 baseline
- Delta A is positive with statistical support
- comparisons against automated optimization are reported honestly

## 4.5 Act V

Required:

- `memo.pdf` exactly 2 pages
- `evidence_graph.json`
- inheritable `README.md`

Acceptance criteria:

- every number in the memo is traceable
- memo includes Tenacious-specific risk analysis
- pilot recommendation is concrete and measurable

## 5. Non-Functional Requirements

## 5.1 Trust and honesty

- No unsupported claims in outreach or replies.
- Low-confidence signals must trigger softer phrasing.
- Missing evidence must result in abstention, escalation, or a question.

## 5.2 Brand safety

- Avoid condescending competitor-gap language.
- Avoid language likely to trigger offshore-perception objections.
- Preserve Tenacious style across longer threads.

## 5.3 Reliability

- Trace every critical step.
- Persist conversation state.
- Fail closed on missing enrichment or missing bench data.

## 5.4 Maintainability

- Keep connectors modular.
- Store intermediate briefs as inspectable JSON.
- Make evaluation outputs reproducible from scripts and logged runs.

## 6. Proposed Repository Shape

The challenge expects a repo that can grow into roughly this shape:

```text
agent/
  api/
  channels/
  crm/
  scheduling/
  enrichment/
  prompts/
  policies/
  storage/
  observability/
  schemas/
eval/
probes/
docs/
README.md
baseline.md
method.md
ablation_results.json
evidence_graph.json
```

## 7. Build Priorities

Priority order for this repository:

1. Establish schemas, tracing, and deterministic enrichment outputs.
2. Build one clean end-to-end happy path for email reply handling and booking.
3. Add policy guards for honesty, bench gating, and channel switching.
4. Add evaluation, probes, and mechanism improvements.
5. Add stretch work only after core artifacts are stable.

## 8. Out of Scope for First Build Pass

- real prospect outreach
- full live crawl coverage across all public job boards
- voice workflow
- distinguished-tier market-space mapping
- automated optimization work before a reliable baseline exists
