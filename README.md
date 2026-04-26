# The Conversion Engine

End-to-end implementation slice for the Week 10 Tenacious conversion engine challenge. This repo is organized as a FastAPI-based orchestration layer that enriches a prospect, applies policy guards, drafts channel actions, writes CRM/calendar artifacts, and records evidence for review.
# Dashboard 

See the dashboard below for a visual overview of the application's interface:

![Dashboard Screenshot](screenshoot/dashboard.png)

## What exists today

- FastAPI application entrypoint and dashboard
- Typed schemas for prospects, briefs, bench match, and conversation decisions
- SQLite-backed repository for synthetic prospect records
- JSONL trace logging for evidence-friendly development
- Integration-aware toolchain across enrichment, email, SMS, bonus-tier voice handoff, CRM, scheduling, observability, and benchmark readiness
- Confidence-aware ICP classifier with abstention
- Bench-gated commitment policy loaded from Tenacious seed materials
- Email reply handler for pricing guardrails, scheduling, SMS handoff, and opt-out
- Act I-IV evidence artifacts and a draft decision memo

## Orchestration Architecture

The system is built as a custom Python orchestration layer — no workflow framework. The runtime
stack is:

```
FastAPI entrypoints (agent/api/routes.py)
  └── Orchestrator service (agent/orchestration/service.py)
        ├── ChannelHandoffManager state machine (agent/orchestration/handoff.py)
        │     Tracks: new → email_only → warm_lead_ready_for_sms → sms_handoff_active / voice_handoff_active → booked
        ├── SQLite interaction_events (agent/storage/repository.py)
        │     Durable event log: email_sent, email_reply_received, sms_handoff_sent,
        │     voice_handoff_sent, booking_link_shared, booking_confirmed, tool_failure
        ├── JSONL trace log (agent/data/traces.jsonl)
        └── External tool adapters (email, SMS, voice, Cal.com, HubSpot, Langfuse, enrichment connectors)
```

**Key orchestration invariants:**

- `ChannelHandoffManager.can_send_sms()` gates all SMS on `email_reply_received`. SMS is never
  sent on initial outreach.
- SMS additionally requires one of: prospect asked for SMS, scheduling intent + phone on file,
  or warm lead + scheduling-focused message (see SMS eligibility policy in `handoff.py`).
- Voice handoff is bonus-tier and warm only. The current implementation prepares a
  delivery-lead / Shared Voice Rig artifact after explicit voice preference or booking confirmation.
- `calcom_client.book_preview()` is intentionally non-mutating — it generates a booking link
  artifact only. Real bookings are created exclusively from the Cal.com webhook
  (`POST /webhooks/calcom → handle_calendar_confirmation()`).
- Every `ToolExecutionResult` is inspected by `_handle_tool_result()`: errors are logged to
  the trace JSONL, written to SQLite as `tool_failure` events, and surfaced as `risk_flags`
  so the caller can route to human review.
- HubSpot and Langfuse calls are wrapped with `_with_retries()` (bounded, exponential backoff).
  Email and SMS are never retried — they are not idempotent without verified idempotency keys.
- When `handle_inbound_message` resolves `next_action="send_email"`, the reply is immediately
  sent (or captured as a draft artifact) — `reply_draft` is never left unacted upon.

## Architecture Diagram

```mermaid
flowchart TD
    A["Lead intake\n(POST /prospects/enrich or /pipeline/run)"]
    B["Enrichment connectors\n(Crunchbase · jobs · layoffs · leadership)"]
    C["Policy layer\n(ICP classifier · bench gate · abstention)"]
    D["Initial email outreach\n(email_channel.send → email_sent event)"]
    E["SQLite interaction_events\n(durable state per prospect_id)"]
    F["Inbound reply\n(POST /conversations/reply\nor /webhooks/resend /webhooks/africastalking /webhooks/voice)"]
    G["ChannelHandoffManager\nroute_inbound_message()"]
    H{"next_action?"}
    I["send_email\n→ email_channel.send(reply_draft)\n→ reply_email_sent event"]
    J["book_meeting\n→ email_channel.send_booking_options()\n→ booking_link_shared event"]
    K["SMS eligibility check\n(warm lead + scheduling + phone)"]
    L["sms_channel.send_booking_options()\n→ sms_handoff_sent event"]
    M["handoff_human\n→ risk_flags + needs_human=True"]
    N["HubSpot CRM writeback\n(contact upsert · enrichment fields · activity note)\nwith bounded retry"]
    O["Cal.com booking preview\n(booking link artifact only — non-mutating)"]
    P["Cal.com webhook\nPOST /webhooks/calcom"]
    Q["handle_calendar_confirmation()\n→ booking_confirmed event\n→ prospect status = booked"]
    R["Langfuse mirror\n(optional, with bounded retry)"]
    S["JSONL trace log\nagent/data/traces.jsonl"]
    T["_handle_tool_result()\nlog failure → trace + SQLite tool_failure event"]

    A --> B --> C --> D --> E
    D --> N
    D --> O
    D --> R
    F --> G --> H
    H -->|send_email| I --> E
    H -->|book_meeting| J --> E
    J --> K -->|eligible| L --> E
    H -->|handoff_human| M
    I --> N
    J --> N
    L --> N
    N --> T
    O --> S
    R --> T
    P --> Q --> E
    Q --> N
    T --> S
```

### Data-flow notes

- Enrichment starts in [`agent/enrichment/`](./agent/enrichment) and produces structured briefs before outreach is drafted.
- Policy decisions live in [`agent/policies/`](./agent/policies) and sit between enrichment outputs and generation.
- The reply-drafting backbone is the conversation-generation step used by the orchestrator and inbound-reply handler in [`agent/orchestration/service.py`](./agent/orchestration/service.py).
- Channel handlers live in [`agent/channels/`](./agent/channels), CRM sync in [`agent/crm/`](./agent/crm), scheduling in [`agent/scheduling/`](./agent/scheduling), and traces in [`agent/observability/`](./agent/observability).

---

## Tenacious Seed Materials

All Tenacious-specific knowledge lives in [`docs/tenacious_sales_data/seed/`](./docs/tenacious_sales_data/seed/). The agent reads these files at startup via [`agent/seed/loader.py`](./agent/seed/loader.py) and uses them to drive every outbound decision. No real customer data is present.

### Files and what they influence

| File | Format | Influences |
|---|---|---|
| `bench_summary.json` | JSON | Bench-capacity gate. If a prospect's inferred stack shows 0 available engineers the agent routes to human review and does not pitch capacity. Updated weekly. |
| `icp_definition.md` | MD | Segment classification labels (fixed for grading), pitch language per segment and AI-readiness tier (high ≥ 2, low 0–1), subject-line prefix per segment. |
| `pricing_sheet.md` | MD | Pricing guardrail replies. Agent may cite the engagement minimum, extension cadence, and reference to public rate floors — but may not invent specific dollar amounts or commit to total-contract values. |
| `style_guide.md` | MD | Style enforcement: subject ≤ 60 chars, cold email body ≤ 120 words, banned subject prefixes (Quick/Just/Hey), banned vendor clichés (top talent/world-class/rockstar). Violations add a `style_violation:*` risk flag and set `needs_human=True`. |
| `case_studies.md` | MD | Three redacted case studies with quotable language. Agent cites only these — does not fabricate case studies or transpose outcomes to sectors not covered. Matched by segment. |
| `email_sequences/cold.md` | MD | 4-sentence cold email structure (concrete fact → bottleneck → Tenacious fit → ask). Subject prefix per segment. Max word counts per email in the three-touch sequence. |
| `email_sequences/warm.md` | MD | Warm-lead follow-up tone and structure reference. |
| `email_sequences/reengagement.md` | MD | Re-engagement sequence: no "circling back" or "following up again" language. |
| `discovery_transcripts/transcript_05_objection_heavy.md` | MD | Agent-usable phrases for offshore concern, price comparison, small-POC de-risking, and architecture boundary objections. |
| `discovery_transcripts/transcript_01–04_*.md` | MD | Discovery call patterns by segment (loaded but not yet indexed into reply routing). |

### How seed materials flow into agent behavior

```
seed_materials (singleton, loaded at startup)
  ├── bench_capacity          → enrichment_service._load_bench_capacity()
  │                             → BenchMatch.sufficient
  │                             → policy_service (bench_mismatch_route_human flag)
  │                             → handoff._bench_mismatch_reply() (does not promise capacity)
  ├── icp_pitch               → policy_service._build_body_and_signature()
  │                             get_pitch_language(segment, ai_maturity_score)
  ├── email_sequence          → policy_service._build_subject()  (prefix per segment)
  │                             get_bottleneck_sentence(segment)
  ├── style (constraints)     → policy_service._validate_style()
  │                             validate_email_style(subject, body)
  │                             → style_violation:* risk flags + needs_human=True
  ├── pricing                 → handoff._pricing_reply()
  │                             (quotes engagement minimum + floor reference, no invented $)
  ├── objection_patterns      → handoff._offshore_concern_reply()
  │                             (transcript_05 agent-usable phrases only)
  └── case_studies            → handoff._general_followup_reply()
                                find_case_study(segment)
                                (only cites if approved case study matches segment)
```

### Invariants

- **No real customer data.** All seed files use sector-descriptor labels ("Global AdTech platform", "North American loyalty program") with client names and specific metrics redacted.
- **Branded outputs are draft by default.** Every email artifact has `"draft": True` in its JSON payload. `ToolExecutionResult.status` is `"previewed"` unless `OUTBOUND_ENABLED=true` and provider credentials are present.
- **Bench capacity comes from `bench_summary.json`.** The agent does not hallucinate available engineers. Stack counts are read from file each startup. A stack with 0 available engineers cannot be pitched.
- **Case studies are never invented.** The agent cites only the three approved quotable blocks from `case_studies.md`. If a prospect asks for a reference in an uncovered sector, the reply routes to a human.
- **Pricing numbers are never invented.** The pricing reply cites the structure from `pricing_sheet.md` (engagement minimum, extension cadence, public floor reference) and routes deeper pricing to a discovery call with the delivery lead.

## Safety And Kill Switch

Outbound is disabled by default. Even if provider credentials are present, email and SMS adapters write local draft artifacts unless:

```bash
OUTBOUND_ENABLED=true
```

This is intentional. Challenge-week prospects must remain synthetic or staff-controlled until Tenacious and program staff approve live deployment.

## Local Setup

### Environment prerequisites

| Requirement | Version | Why it is needed |
|---|---:|---|
| Python | 3.12 | The project requires Python 3.12+ and the checked-in virtualenv/cache artifacts were produced on Python 3.12. |
| `uv` | Current stable | Dependency sync and `uv run` are the supported local bootstrap path in this repo. |
| SQLite | Bundled with Python | Prospect snapshots and thread state are persisted locally through the standard Python SQLite module. |
| Git | Current stable | Needed to clone the repo and, if you want eval parity, manage the `eval/tau2-bench` submodule checkout. |

### Pinned dependency versions

The supported dependency set is the lockfile-backed set in [`uv.lock`](./uv.lock). The project metadata in [`pyproject.toml`](./pyproject.toml) is pinned to the same versions:

| Package | Version |
|---|---:|
| `fastapi` | `0.115.12` |
| `uvicorn[standard]` | `0.34.2` |
| `pydantic` | `2.11.4` |
| `httpx` | `0.28.1` |
| `langfuse` | `4.5.0` |
| `python-dotenv` | `1.2.2` |
| `pytest` | `9.0.3` |
| `ruff` | `0.15.11` |

### Explicit local bootstrap order

1. Create a Python 3.12 environment, or let `uv` manage it for you.
2. Copy the sample environment file:

```bash
cp .env.example .env
```

3. Review `.env` and keep `OUTBOUND_ENABLED=false` for local preview work.
4. Sync the exact locked dependencies:

```bash
uv sync --frozen --group dev
```

5. Start the API:

```bash
uv run uvicorn agent.main:app --reload
```

6. Open the FastAPI docs at `http://127.0.0.1:8000/docs`.
7. Run the local test suite:

```bash
uv run pytest -q
```

8. Only after the preview path works, add provider credentials if you want live integrations. Email and SMS still remain non-live until `OUTBOUND_ENABLED=true`.
9. Optional for benchmark work only: initialize or repair the `eval/tau2-bench` checkout before running eval scripts. See the handoff notes below, because the checked-in `.gitmodules` entry still uses a placeholder URL.

### Provider setup notes

Use one email provider at a time.

For Resend:

```bash
EMAIL_PROVIDER=resend
RESEND_API_KEY=...
RESEND_FROM_EMAIL=you@your-verified-domain.com
RESEND_REPLY_TO=you@your-verified-domain.com
```

For MailerSend:

```bash
EMAIL_PROVIDER=mailersend
MAILERSEND_API_KEY=...
MAILERSEND_FROM_EMAIL=you@your-verified-domain.com
MAILERSEND_FROM_NAME=Tenacious
```

For Africa's Talking sandbox:

```bash
SMS_PROVIDER=africastalking
AFRICASTALKING_USERNAME=sandbox
AFRICASTALKING_API_KEY=...
AFRICASTALKING_SENDER_ID=TENACIOUS
```

Do not set `EMAIL_PROVIDER=africastalking`; Africa's Talking is only for `SMS_PROVIDER`. Resend and MailerSend both require a verified from address or domain before live delivery works. For a live Africa's Talking app, replace `sandbox` with the real app username and use a sender ID or short code approved in that account.

For the Shared Voice Rig bonus tier:

```bash
VOICE_PROVIDER=shared_voice_rig
SHARED_VOICE_RIG_WEBHOOK_URL=...
SHARED_VOICE_RIG_API_KEY=...
SHARED_VOICE_RIG_KEYWORD_PREFIX=YOUR_PREFIX
VOICE_WEBHOOK_SECRET=...
```

## Configuration Reference

The repo ships with an [`.env.example`](./.env.example) file. The table below explains every configuration variable used by the app and eval wrappers.

### Core app and model settings

| Variable | Required for | Purpose |
|---|---|---|
| `APP_BASE_URL` | Local and deployed app | Base URL used for deployment info and recommended webhook URLs. |
| `OUTBOUND_ENABLED` | Live sends only | Global kill switch. When `false`, email and SMS providers write preview artifacts instead of sending. |
| `OPENROUTER_API_KEY` | Eval or any OpenRouter-backed model workflow | API key for model access in benchmark or evaluation tooling. |
| `OPENROUTER_MODEL` | Eval or model-backed runs | Default model identifier for eval wrappers that use OpenRouter. |

### Email settings

| Variable | Required for | Purpose |
|---|---|---|
| `EMAIL_PROVIDER` | Any email action | Selects `mock`, `resend`, or `mailersend`. |
| `RESEND_API_KEY` | Resend live/configured mode | API credential for Resend. |
| `RESEND_FROM_EMAIL` | Resend | Sender address for outbound email drafts or live sends. |
| `RESEND_REPLY_TO` | Resend optional | Reply-to address for Resend messages. |
| `RESEND_WEBHOOK_SECRET` | Resend webhook verification | Shared secret for inbound Resend webhook validation or future hardening. |
| `MAILERSEND_API_KEY` | MailerSend live/configured mode | API credential for MailerSend. |
| `MAILERSEND_FROM_EMAIL` | MailerSend | Sender address for MailerSend. |
| `MAILERSEND_FROM_NAME` | MailerSend | Display name for MailerSend outbound messages. |

### SMS settings

| Variable | Required for | Purpose |
|---|---|---|
| `SMS_PROVIDER` | Any SMS action | Selects `mock` or `africastalking`. |
| `AFRICASTALKING_USERNAME` | Africa's Talking configured/live mode | Sandbox or production username for SMS delivery. |
| `AFRICASTALKING_API_KEY` | Africa's Talking configured/live mode | API credential for SMS delivery. |
| `AFRICASTALKING_SENDER_ID` | Africa's Talking | Sender ID or shortcode label for outbound SMS. |

### Voice settings

| Variable | Required for | Purpose |
|---|---|---|
| `VOICE_PROVIDER` | Any voice action | Selects `mock` or `shared_voice_rig`. |
| `SHARED_VOICE_RIG_WEBHOOK_URL` | Shared Voice Rig configured/live mode | Target webhook URL for delivery-lead voice handoff registration. |
| `SHARED_VOICE_RIG_API_KEY` | Shared Voice Rig optional auth | Bearer credential for the rig if required. |
| `SHARED_VOICE_RIG_KEYWORD_PREFIX` | Shared Voice Rig configured/live mode | Per-trainee keyword prefix used by the bonus-tier rig. |
| `VOICE_WEBHOOK_SECRET` | Voice webhook verification | Shared secret placeholder for inbound voice webhook hardening. |

### CRM settings

| Variable | Required for | Purpose |
|---|---|---|
| `HUBSPOT_ACCESS_TOKEN` | Live CRM sync | Private app token for HubSpot contact/event upserts. |
| `HUBSPOT_BASE_URL` | HubSpot integration | Base API URL for HubSpot requests. |
| `HUBSPOT_WEBHOOK_SECRET` | HubSpot webhook verification | Shared secret placeholder for webhook hardening. |

### Calendar settings

| Variable | Required for | Purpose |
|---|---|---|
| `CALCOM_API_KEY` | Live calendar booking | API key for Cal.com. |
| `CALCOM_API_BASE` | Cal.com integration | Base API URL for Cal.com requests. |
| `CALCOM_API_VERSION` | Cal.com integration | Version header value expected by the current adapter. |
| `CALCOM_EVENT_TYPE_ID` | Live booking | Target event type ID used for booking creation. |
| `CALCOM_USERNAME` | Cal.com optional | Username used for scheduling context or downstream linking. |
| `CALCOM_EVENT_TYPE_SLUG` | Preview and live booking | Human-readable slug for the event type. |
| `CALCOM_DEFAULT_TIMEZONE` | Scheduling | Default timezone when the prospect timezone is unknown. |
| `CALCOM_WEBHOOK_SECRET` | Cal.com webhook verification | Shared secret placeholder for webhook hardening. |

### Observability settings

| Variable | Required for | Purpose |
|---|---|---|
| `LANGFUSE_PUBLIC_KEY` | Langfuse export | Public key for Langfuse. |
| `LANGFUSE_SECRET_KEY` | Langfuse export | Secret key for Langfuse. |
| `LANGFUSE_HOST` | Langfuse export | Target Langfuse host, defaulting to the cloud endpoint. |
| `LANGFUSE_EXPORT_ENABLED` | Live Langfuse export | Gate that enables remote export instead of local mirror-only behavior. |

### Data and evaluation paths

| Variable | Required for | Purpose |
|---|---|---|
| `CRUNCHBASE_SNAPSHOT_PATH` | Enrichment | Path to the Crunchbase-style company snapshot JSON. |
| `JOB_POSTS_SNAPSHOT_PATH` | Enrichment | Path to the job-post snapshot JSON. |
| `LAYOFFS_SNAPSHOT_PATH` | Enrichment | Path to the layoffs snapshot JSON. |
| `LEADERSHIP_SNAPSHOT_PATH` | Enrichment | Path to the leadership-change snapshot JSON. |
| `BENCH_SUMMARY_PATH` | Bench gating | Path to the Tenacious bench-capacity seed file. |
| `LAYOFFS_CSV_URL` | Optional enrichment refresh work | Optional remote CSV source for future layoffs refresh logic. |
| `TAU2_BENCH_PATH` | Evaluation | Filesystem path to the tau2 benchmark checkout used by eval scripts. |

## Directory Index

Every top-level folder currently present at the repo root is mapped below.

- `.git/`: Git metadata for the repository. A successor usually does not edit this directly, but it matters for submodules and branch state.
- `.pytest_cache/`: Local pytest cache from previous runs. Safe to delete; not part of the product surface.
- `.ruff_cache/`: Local Ruff cache from previous lint runs. Safe to delete; not part of the product surface.
- `.venv/`: Local virtual environment generated during development. Useful for this checkout, but a fresh inheritor can recreate it with `uv sync`.
- `agent/`: Main application package. It contains the API routes, orchestration logic, enrichment services, policy layer, channel adapters, CRM/calendar integrations, observability, schemas, storage layer, and local data artifacts.
- `docs/`: Reference material and reporting docs. This includes supporting challenge materials, interim client-facing reports, and Tenacious seed data.
- `eval/`: Evaluation assets and wrappers. This is where local score artifacts, baseline notes, the tau2 wrapper script, and the benchmark checkout live.
- `planning/`: Build-planning documents. These files explain the implementation requirements and early design choices behind the system.
- `probes/`: Probe and failure-analysis material. Use this folder to understand the targeted failure modes and challenge-specific evaluation probes.
- `tests/`: Unit-style regression coverage for enrichment/policy behavior and for channel/CRM/scheduling adapter behavior.

## Current Endpoints

- `GET /health`
- `GET /deploy/info`
- `GET /dashboard`
- `GET /dashboard/state`
- `GET /tools/status`
- `POST /prospects/enrich`
- `POST /pipeline/run`
- `POST /conversations/reply`
- `GET /prospects`
- `GET /prospects/{prospect_id}`
- `POST /webhooks/resend`
- `POST /webhooks/africastalking`
- `POST /webhooks/voice`
- `POST /webhooks/calcom`
- `POST /webhooks/hubspot`

## Render

This repo includes [render.yaml](/home/nurye/Desktop/TRP1/week10/TheConversionEngine/render.yaml) so you can deploy the FastAPI app to Render's free tier as a public webhook backend.

After deployment:

1. Set `APP_BASE_URL` to your Render service URL.
2. Register these webhook URLs with providers:

```text
{APP_BASE_URL}/webhooks/resend
{APP_BASE_URL}/webhooks/africastalking
{APP_BASE_URL}/webhooks/voice
{APP_BASE_URL}/webhooks/calcom
{APP_BASE_URL}/webhooks/hubspot
```

3. Verify the deployment at:

```text
{APP_BASE_URL}/health
{APP_BASE_URL}/deploy/info
```

## Planning Docs

- [Requirements](./planning/requirements.md)
- [Design](./planning/design.md)

## Challenge Artifacts

- [Baseline](./eval/baseline.md)
- [Score log](./eval/score_log.json)
- [Eval README](./eval/README.md)
- [Probe library](./probes/probe_library.md)
- [Failure taxonomy](./probes/failure_taxonomy.md)
- [Target failure mode](./probes/target_failure_mode.md)
- [Method](./method.md)
- [Ablation results](./ablation_results.json)
- [Evidence graph](./evidence_graph.json)
- [Decision memo draft](./memo.md)

## Known Limitations And Successor Next Steps

- Live provider verification is still incomplete from this shell environment. The orchestration path and local artifacts exist, but HubSpot, Cal.com, and some outbound requests previously failed with name-resolution errors; see [docs/interim_client_progress_report.md](./docs/interim_client_progress_report.md).
- The benchmark submodule metadata is not fresh-clone ready yet. [`.gitmodules`](./.gitmodules) still points `eval/tau2-bench` at `https://github.com/YOUR_GITHUB_USERNAME/tau2-bench.git`, so a successor should repair that URL or vendor the benchmark another way before relying on `git submodule update --init --recursive`.
- Company-level deduplication is not implemented. [memo.md](./memo.md) calls out the concrete risk: two contacts from the same company can receive different pitch framings on the same day.
- Voice is implemented as a bonus-tier warm handoff path, not as cold automated calling. The repo prepares a delivery-lead / Shared Voice Rig artifact after explicit voice preference or booking confirmation, while keeping the challenge's email-first channel hierarchy intact.
- The repo contains local-generated state in `agent/data/`, `.venv/`, `.pytest_cache/`, and `.ruff_cache/`. A successor should decide whether to keep those artifacts for evidence review or clean them before packaging the repo.

### Recommended first tasks for a successor

1. Keep the app in preview mode, run `uv sync --frozen --group dev`, and verify the local happy path through `/pipeline/run`.
2. Repair the `eval/tau2-bench` submodule source before trying to reproduce the benchmark flow from a clean clone.
3. Re-run `uv run pytest -q` and the eval wrappers in a clean, network-enabled environment before making stronger live-integration claims.
4. Implement company-level dedupe or throttling before any real multi-contact outreach workflow is considered.

## Notes

- This implementation is demo-ready with local artifacts and provider-ready adapters; it is not approved for real prospect outreach.
- External providers run in configured mode only when their credentials are present; otherwise the app records honest local preview artifacts in `agent/data/outbox/`.
- Email and SMS also require `OUTBOUND_ENABLED=true`; credentials alone are not enough.
- `.env` is loaded automatically at startup via `python-dotenv`.
- Raw webhook payloads are captured in `agent/data/webhooks/` for debugging and traceability.
- Local enrichment snapshots live in `agent/data/snapshots/` by default and can be overridden with environment variables.
- Trace files are written to `agent/data/traces.jsonl`.
