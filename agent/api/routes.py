import json
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from urllib.parse import parse_qs

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse

from agent.api.dashboard import DASHBOARD_HTML
from agent.config import settings
from agent.observability.tracing import TraceLogger
from agent.orchestration.service import orchestrator
from agent.schemas.briefs import ProspectEnrichmentResponse
from agent.schemas.conversation import ConversationDecision
from agent.schemas.dashboard import DashboardStateResponse
from agent.schemas.prospect import InboundMessageRequest, LeadIntakeRequest, ProspectRecord
from agent.schemas.tools import ToolStatus

router = APIRouter()
trace_logger = TraceLogger()


@router.get("/", response_class=HTMLResponse)
@router.get("/dashboard", response_class=HTMLResponse)
def dashboard() -> str:
    return DASHBOARD_HTML


@router.get("/health")
def healthcheck() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/deploy/info")
def deployment_info() -> dict[str, object]:
    base = settings.app_base_url.rstrip("/")
    return {
        "app_base_url": base,
        "recommended_webhooks": {
            "resend": f"{base}/webhooks/resend",
            "africastalking": f"{base}/webhooks/africastalking",
            "calcom": f"{base}/webhooks/calcom",
            "hubspot": f"{base}/webhooks/hubspot",
        },
        "render_ready": Path("render.yaml").exists(),
    }


@router.get("/dashboard/state", response_model=DashboardStateResponse)
def dashboard_state() -> DashboardStateResponse:
    return orchestrator.dashboard_state()


@router.get("/tools/status", response_model=list[ToolStatus])
def tools_status() -> list[ToolStatus]:
    return orchestrator.tool_statuses()


@router.post("/webhooks/{provider}")
async def capture_webhook(provider: str, request: Request) -> dict[str, object]:
    provider_key = provider.lower()
    if provider_key not in {"resend", "africastalking", "calcom", "hubspot"}:
        raise HTTPException(status_code=404, detail="Unknown webhook provider")

    raw_body = await request.body()
    content_type = request.headers.get("content-type", "")
    parsed_body: object
    if "application/json" in content_type and raw_body:
        try:
            parsed_body = json.loads(raw_body.decode("utf-8"))
        except json.JSONDecodeError:
            parsed_body = {"raw": raw_body.decode("utf-8", errors="replace")}
    elif "application/x-www-form-urlencoded" in content_type and raw_body:
        parsed_body = {
            key: value if len(value) > 1 else value[0]
            for key, value in parse_qs(raw_body.decode("utf-8")).items()
        }
    else:
        parsed_body = {"raw": raw_body.decode("utf-8", errors="replace")} if raw_body else {}

    settings.webhook_dir.mkdir(parents=True, exist_ok=True)
    received_at = datetime.now(timezone.utc).isoformat()
    body_hash = sha256(raw_body).hexdigest()[:16] if raw_body else "empty"
    artifact_path = settings.webhook_dir / f"{provider_key}_{body_hash}.json"
    artifact_path.write_text(
        json.dumps(
            {
                "provider": provider_key,
                "received_at": received_at,
                "content_type": content_type,
                "headers": dict(request.headers.items()),
                "query_params": dict(request.query_params),
                "body": parsed_body,
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    trace_id = trace_logger.log(
        "webhook_received",
        {
            "provider": provider_key,
            "artifact_ref": str(artifact_path),
            "content_type": content_type,
            "body_hash": body_hash,
        },
    )
    return {
        "ok": True,
        "provider": provider_key,
        "trace_id": trace_id,
        "artifact_ref": str(artifact_path),
    }


@router.post("/prospects/enrich", response_model=ProspectEnrichmentResponse)
def enrich_prospect(payload: LeadIntakeRequest) -> ProspectEnrichmentResponse:
    return orchestrator.intake_and_enrich(payload)


@router.post("/pipeline/run", response_model=ProspectEnrichmentResponse)
def run_pipeline(payload: LeadIntakeRequest) -> ProspectEnrichmentResponse:
    return orchestrator.run_toolchain(payload)


@router.post("/conversations/reply", response_model=ConversationDecision)
def handle_reply(payload: InboundMessageRequest) -> ConversationDecision:
    return orchestrator.handle_inbound_message(payload)


@router.get("/prospects", response_model=list[ProspectRecord])
def list_prospects() -> list[ProspectRecord]:
    return orchestrator.list_prospects()


@router.get("/prospects/{prospect_id}", response_model=ProspectEnrichmentResponse)
def get_prospect(prospect_id: str) -> ProspectEnrichmentResponse:
    snapshot = orchestrator.get_snapshot(prospect_id)
    if snapshot is None:
        raise HTTPException(status_code=404, detail="Prospect snapshot not found")
    return snapshot
