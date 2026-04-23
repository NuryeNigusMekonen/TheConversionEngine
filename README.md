# The Conversion Engine

End-to-end implementation slice for the Week 10 Tenacious conversion engine challenge.

## What exists today

- FastAPI application entrypoint and dashboard
- typed schemas for prospects, briefs, bench match, and conversation decisions
- SQLite-backed repository for synthetic prospect records
- JSONL trace logging for evidence-friendly development
- integration-aware toolchain across enrichment, email, SMS, CRM, scheduling, observability, and benchmark readiness
- confidence-aware ICP classifier with abstention
- bench-gated commitment policy loaded from Tenacious seed materials
- email reply handler for pricing guardrails, scheduling, SMS handoff, and opt-out
- Act I-IV evidence artifacts and a draft decision memo

## Architecture

```text
Synthetic/public prospect input
        |
        v
FastAPI orchestrator
        |
        +--> Snapshot enrichment: Crunchbase, jobs, layoffs, leadership
        |       |
        |       +--> Hiring signal brief + AI maturity + bench match
        |       +--> Competitor gap brief
        |
        +--> Policy layer: ICP abstention, confidence phrasing, bench gate
        |
        +--> Email primary outreach
        +--> Warm SMS scheduling handoff
        +--> Cal.com booking preview/live booking
        +--> HubSpot contact/event artifact or live sync
        +--> JSONL traces + Langfuse mirror when configured
```

## Safety and kill switch

Outbound is disabled by default. Even if provider credentials are present, email and SMS adapters write local draft artifacts unless:

```bash
OUTBOUND_ENABLED=true
```

This is intentional. Challenge-week prospects must remain synthetic/staff-controlled until Tenacious and program staff approve live deployment.

## Email Setup

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

Do not set `EMAIL_PROVIDER=africastalking`; Africa's Talking is only for `SMS_PROVIDER`. Resend and MailerSend both require the from address/domain to be verified before live delivery works.

## SMS Setup

For Africa's Talking sandbox:

```bash
SMS_PROVIDER=africastalking
AFRICASTALKING_USERNAME=sandbox
AFRICASTALKING_API_KEY=...
AFRICASTALKING_SENDER_ID=TENACIOUS
```

For a live Africa's Talking app, replace `sandbox` with the app username and use a sender ID or short code approved in that account. SMS still only sends live when `OUTBOUND_ENABLED=true`; otherwise the app writes local preview artifacts.

## Repository layout

```text
agent/
  api/
  channels/
  crm/
  enrichment/
  observability/
  orchestration/
  policies/
  schemas/
  storage/
eval/
planning/
probes/
docs/
```

## Run locally

1. Create and activate a virtual environment if you want to manage Python manually, or let `uv` manage it for you.
2. Sync dependencies:

```bash
uv sync
```

For development tools too:

```bash
uv sync --group dev
```

3. Start the API:

```bash
uv run uvicorn agent.main:app --reload
```

4. Open the docs:

```text
http://127.0.0.1:8000/docs
```

5. Optional: copy `.env.example` to `.env` and fill in provider credentials to switch adapters from preview mode to live mode.

## Current endpoints

- `GET /health`
- `GET /deploy/info`
- `GET /dashboard`
- `GET /dashboard/state`
- `GET /tools/status`
- `POST /prospects/enrich`
- `POST /pipeline/run`
- `POST /conversations/reply`
- `GET /prospects`
- `POST /webhooks/resend`
- `POST /webhooks/africastalking`
- `POST /webhooks/calcom`
- `POST /webhooks/hubspot`

## Render

This repo now includes [render.yaml](/home/nurye/Desktop/TRP1/week10/TheConversionEngine/render.yaml) so you can deploy the FastAPI app to Render's free tier as a public webhook backend.

After deployment:

1. Set `APP_BASE_URL` to your Render service URL.
2. Register these webhook URLs with providers:

```text
{APP_BASE_URL}/webhooks/resend
{APP_BASE_URL}/webhooks/africastalking
{APP_BASE_URL}/webhooks/calcom
{APP_BASE_URL}/webhooks/hubspot
```

3. Verify the deployment at:

```text
{APP_BASE_URL}/health
{APP_BASE_URL}/deploy/info
```

## Planning docs

- [Requirements](./planning/requirements.md)
- [Design](./planning/design.md)

## Challenge artifacts

- [Baseline](./eval/baseline.md)
- [Score log](./eval/score_log.json)
- [Probe library](./probes/probe_library.md)
- [Failure taxonomy](./probes/failure_taxonomy.md)
- [Target failure mode](./probes/target_failure_mode.md)
- [Method](./method.md)
- [Ablation results](./ablation_results.json)
- [Evidence graph](./evidence_graph.json)
- [Decision memo draft](./memo.md)

## Notes

- This implementation is demo-ready with local artifacts and provider-ready adapters; it is not approved for real prospect outreach.
- External providers run in `configured` mode only when their credentials are present; otherwise the app records honest local preview artifacts in `agent/data/outbox/`.
- Email and SMS also require `OUTBOUND_ENABLED=true`; credentials alone are not enough.
- `.env` is loaded automatically at startup via `python-dotenv`.
- Raw webhook payloads are captured in `agent/data/webhooks/` for debugging and traceability.
- Local enrichment snapshots live in `agent/data/snapshots/` by default and can be overridden with environment variables.
- Trace files are written to `agent/data/traces.jsonl`.
