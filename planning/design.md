# Conversion Engine Design

This design document proposes the first architecture for building the Tenacious conversion engine in this repository.

## 1. Design Goals

- Optimize for challenge deliverables first.
- Keep evidence and traceability first-class.
- Prefer deterministic enrichment and policy guards around a smaller agent core.
- Make it easy to demo one excellent end-to-end path before expanding breadth.

## 2. System Overview

The system is a workflow-driven research and conversation engine with six major parts:

1. `Lead intake and orchestration`
2. `Signal enrichment`
3. `Brief generation`
4. `Conversation agent and policy layer`
5. `CRM and scheduling integration`
6. `Evaluation and evidence pipeline`

## 3. Proposed Architecture

```text
Synthetic Prospect / Test Harness
            |
            v
     Orchestrator API
            |
            +--------------------+
            |                    |
            v                    v
   Enrichment Pipeline     Conversation State Store
            |                    |
            v                    |
  Hiring Signal Brief            |
  Competitor Gap Brief           |
            |                    |
            +---------+----------+
                      |
                      v
              Policy-Guided Agent
                      |
          +-----------+-----------+
          |                       |
          v                       v
   Email Channel             SMS Channel
          |                       |
          +-----------+-----------+
                      |
                      v
              Cal.com Scheduler
                      |
                      v
                 HubSpot Writer
                      |
                      v
              Langfuse / Trace Log
```

## 4. Core Components

## 4.1 Orchestrator

Responsibilities:

- own lead lifecycle state
- trigger enrichment before first outreach
- route inbound email replies
- allow SMS handoff only when policy permits
- trigger booking and CRM writes

Initial implementation choice:

- a FastAPI app with explicit service modules
- background tasks only where needed

Reason:

- challenge flows are webhook-heavy
- FastAPI is simple for local dev and demoability

## 4.2 Enrichment pipeline

Responsibilities:

- normalize source data into one prospect profile
- score AI maturity
- compute ICP segment confidence
- assemble competitor gap brief
- attach evidence and confidence metadata

Recommended module split:

- `crunchbase.py`
- `funding.py`
- `jobs.py`
- `layoffs.py`
- `leadership.py`
- `ai_maturity.py`
- `competitor_gap.py`
- `bench_match.py`

Output contract:

- one normalized `ProspectProfile`
- one `HiringSignalBrief`
- one `CompetitorGapBrief`

## 4.3 Policy layer

This should sit between briefs and the LLM.

Responsibilities:

- rewrite or constrain prompts based on confidence
- block unsupported staffing commitments
- block segment-4 pitch when readiness is below threshold
- choose email versus SMS versus human handoff
- enforce safer fallback language when evidence is weak

This is where we should put most of the challenge originality later, because it is measurable and grounded.

## 4.4 Conversation agent

Responsibilities:

- generate first-touch email drafts
- respond to inbound replies
- ask clarifying questions when needed
- hand off safely when confidence is low

Design principle:

- the model should not be the source of truth for facts
- it should consume structured briefs and policy decisions

Recommended pattern:

- structured system prompt
- explicit context packet
- output schema for next action, reply draft, rationale, and trace tags

## 4.5 Channel adapters

Email adapter:

- outbound via Resend or MailerSend
- inbound reply webhook
- thread id correlation

SMS adapter:

- Africa's Talking sandbox webhook
- warm-lead scheduling only
- opt-out handling if needed for safety and demo completeness

Calendar adapter:

- retrieve available slots
- create booking
- return booking confirmation data

CRM adapter:

- create or update contact
- write enrichment metadata
- append conversation events
- store booking status

## 4.6 Storage

For the first pass, keep state simple and inspectable.

Recommended local storage:

- SQLite for thread state and prospect records
- JSON artifacts on disk for briefs and traces during development

Reason:

- enough for demo and evaluation
- easy to inspect
- low operational overhead

## 4.7 Observability

Every critical action should emit:

- trace id
- prospect id
- thread id
- channel
- model used
- tokens and estimated cost
- latency
- source references
- confidence values

This is necessary not just for debugging, but for the memo and evidence graph.

## 5. Key Data Models

## 5.1 ProspectProfile

Fields:

- `prospect_id`
- `company_name`
- `company_domain`
- `segment_candidates`
- `primary_segment`
- `firmographics`
- `funding_signal`
- `job_signal`
- `layoff_signal`
- `leadership_signal`
- `ai_maturity`
- `bench_match`
- `source_refs`

## 5.2 HiringSignalBrief

Fields:

- `summary`
- `signals`
- `confidence_by_signal`
- `ai_maturity_score`
- `ai_maturity_justification`
- `recommended_pitch_angle`
- `do_not_claim`

## 5.3 CompetitorGapBrief

Fields:

- `peer_group_definition`
- `peer_companies`
- `top_quartile_practices`
- `prospect_missing_practices`
- `safe_gap_framing`
- `confidence`

## 5.4 ConversationDecision

Fields:

- `next_action`
- `channel`
- `reply_draft`
- `needs_human`
- `risk_flags`
- `trace_tags`

## 6. End-to-End Flow

## 6.1 First outbound flow

1. Select synthetic prospect.
2. Run enrichment pipeline.
3. Persist normalized briefs.
4. Generate outbound email using policy-guided prompt.
5. Send email and log trace.
6. Create or update HubSpot record.

## 6.2 Reply flow

1. Receive inbound email webhook.
2. Load thread state and briefs.
3. Re-evaluate ICP confidence, bench match, and handoff policy.
4. Draft response or route to human.
5. If scheduling intent is clear, fetch Cal.com slots.
6. If prospect prefers fast coordination, switch to SMS.
7. Confirm booking and write all events to HubSpot.

## 6.3 Evidence flow

1. Every run writes structured trace events.
2. Eval scripts compute score, latency, and cost summaries.
3. Memo claims are mapped to trace ids or known public references.

## 7. Initial Mechanism Direction

The strongest first mechanism candidate is a `confidence-aware policy layer` rather than a purely prompt-level trick.

Why this is a good fit:

- directly addresses signal over-claiming
- measurable in probes
- likely to improve both brand safety and pass rate
- aligns with challenge emphasis on honesty and confidence

Version 1 policy behaviors:

- if signal confidence is low, switch from assertion to question framing
- if bench match is weak, disallow staffing commitment
- if segment confidence is below threshold, use exploratory email instead of a segment pitch
- if competitor gap confidence is weak, omit the gap claim entirely

## 8. Milestone Plan

## 8.1 Milestone 1

Goal:

- establish repo skeleton, schemas, FastAPI app, local storage, and trace plumbing

Deliverables:

- runnable app shell
- JSON schemas
- basic health endpoint
- trace writer

## 8.2 Milestone 2

Goal:

- implement enrichment pipeline with mocked or file-backed public data inputs first

Deliverables:

- prospect profile generation
- hiring signal brief generation
- competitor gap brief generation

## 8.3 Milestone 3

Goal:

- implement email happy path

Deliverables:

- outbound email generation
- reply webhook handling
- stateful thread continuation
- HubSpot write stubs or integration

## 8.4 Milestone 4

Goal:

- implement scheduling and SMS handoff

Deliverables:

- slot lookup
- booking flow
- warm SMS continuation

## 8.5 Milestone 5

Goal:

- implement probes, eval harness integration, and mechanism iteration

Deliverables:

- probe library scaffold
- eval output structure
- initial ablation workflow

## 9. Risks and Mitigations

Risk:

- competitor gap logic becomes too fuzzy to trust

Mitigation:

- keep peer selection heuristic simple first
- attach evidence and confidence per claimed gap
- omit weak gaps rather than overreach

Risk:

- channel switching creates demo complexity early

Mitigation:

- complete email-only happy path before SMS handoff

Risk:

- evaluation work is delayed by product build

Mitigation:

- create trace schemas and eval output formats from day one

Risk:

- LLM output drifts from Tenacious tone

Mitigation:

- build explicit tone checks and regeneration hooks after the happy path is stable

## 10. Recommended Next Build Step

Implement the repo skeleton around this design:

- `agent/` package with FastAPI entrypoint
- `schemas/` for core models
- `storage/` for SQLite and artifact persistence
- `enrichment/` services with stubbed providers
- `observability/` trace logger
- `channels/` email and SMS adapters

That gives us the smallest credible base for both the product demo and the graded artifacts.
