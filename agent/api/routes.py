import json
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from urllib.parse import parse_qs

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse

from agent.api.dashboard import DASHBOARD_HTML
from agent.channels.email import EmailWebhookError, email_channel
from agent.channels.sms import SmsWebhookError, sms_channel
from agent.config import settings
from agent.observability.tracing import TraceLogger
from agent.orchestration.service import orchestrator
from agent.schemas.briefs import ProspectEnrichmentResponse
from agent.schemas.conversation import ConversationDecision
from agent.schemas.dashboard import DashboardStateResponse
from agent.schemas.prospect import InboundMessageRequest, LeadIntakeRequest, ProspectRecord
from agent.schemas.tools import ToolStatus
from agent.scheduling.calcom import CalComWebhookError, calcom_client

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
            "mailersend": f"{base}/webhooks/mailersend",
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


def _parse_request_body(raw_body: bytes, content_type: str) -> object:
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
    return parsed_body


def _store_webhook_artifact(
    provider_key: str,
    request: Request,
    parsed_body: object,
    raw_body: bytes,
    content_type: str,
) -> tuple[str, str]:
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
    return str(artifact_path), trace_id


def _verify_shared_secret(request: Request, expected_secret: str, provider_label: str) -> None:
    if not expected_secret:
        return
    candidates = {
        request.headers.get("authorization", ""),
        request.headers.get("x-webhook-secret", ""),
        request.headers.get("x-cal-signature-256", ""),
    }
    if expected_secret not in candidates and f"Bearer {expected_secret}" not in candidates:
        raise HTTPException(status_code=403, detail=f"{provider_label} webhook secret validation failed")


@router.post("/webhooks/resend")
async def resend_webhook(request: Request) -> dict[str, object]:
    raw_body = await request.body()
    content_type = request.headers.get("content-type", "")
    parsed_body = _parse_request_body(raw_body, content_type)
    artifact_ref, trace_id = _store_webhook_artifact("resend", request, parsed_body, raw_body, content_type)
    _verify_shared_secret(request, settings.resend_webhook_secret, "Resend")
    try:
        inbound = email_channel.handle_resend_reply_webhook(
            {"body": parsed_body, "headers": dict(request.headers.items())}
        )
        decision = orchestrator.handle_inbound_message(inbound)
    except EmailWebhookError as exc:
        raise HTTPException(status_code=400, detail=f"Resend reply webhook parsing failed: {exc}") from exc
    return {
        "ok": True,
        "provider": "resend",
        "trace_id": trace_id,
        "artifact_ref": artifact_ref,
        "decision": decision.model_dump(mode="json"),
    }


@router.post("/webhooks/mailersend")
async def mailersend_webhook(request: Request) -> dict[str, object]:
    raw_body = await request.body()
    content_type = request.headers.get("content-type", "")
    parsed_body = _parse_request_body(raw_body, content_type)
    artifact_ref, trace_id = _store_webhook_artifact("mailersend", request, parsed_body, raw_body, content_type)
    try:
        inbound = email_channel.handle_mailersend_reply_webhook(
            {"body": parsed_body, "headers": dict(request.headers.items())}
        )
        decision = orchestrator.handle_inbound_message(inbound)
    except EmailWebhookError as exc:
        raise HTTPException(status_code=400, detail=f"MailerSend reply webhook parsing failed: {exc}") from exc
    return {
        "ok": True,
        "provider": "mailersend",
        "trace_id": trace_id,
        "artifact_ref": artifact_ref,
        "decision": decision.model_dump(mode="json"),
    }


@router.post("/webhooks/africastalking")
async def africastalking_webhook(request: Request) -> dict[str, object]:
    raw_body = await request.body()
    content_type = request.headers.get("content-type", "")
    parsed_body = _parse_request_body(raw_body, content_type)
    artifact_ref, trace_id = _store_webhook_artifact(
        "africastalking",
        request,
        parsed_body,
        raw_body,
        content_type,
    )
    try:
        inbound = sms_channel.handle_africastalking_webhook(
            {"body": parsed_body, "headers": dict(request.headers.items())}
        )
        decision = orchestrator.handle_inbound_message(inbound)
    except SmsWebhookError as exc:
        raise HTTPException(status_code=400, detail=f"Africa's Talking webhook parsing failed: {exc}") from exc
    return {
        "ok": True,
        "provider": "africastalking",
        "trace_id": trace_id,
        "artifact_ref": artifact_ref,
        "decision": decision.model_dump(mode="json"),
    }


@router.post("/webhooks/calcom")
async def calcom_webhook(request: Request) -> dict[str, object]:
    raw_body = await request.body()
    content_type = request.headers.get("content-type", "")
    parsed_body = _parse_request_body(raw_body, content_type)
    artifact_ref, trace_id = _store_webhook_artifact("calcom", request, parsed_body, raw_body, content_type)
    _verify_shared_secret(request, settings.calcom_webhook_secret, "Cal.com")
    try:
        confirmation = calcom_client.handle_confirmation_webhook(
            {"body": parsed_body, "headers": dict(request.headers.items())}
        )
        result = orchestrator.handle_calendar_confirmation(confirmation)
    except CalComWebhookError as exc:
        raise HTTPException(status_code=400, detail=f"Cal.com confirmation parsing failed: {exc}") from exc
    return {
        "ok": True,
        "provider": "calcom",
        "trace_id": trace_id,
        "artifact_ref": artifact_ref,
        "confirmation_result": result,
    }


@router.post("/webhooks/hubspot")
async def hubspot_webhook(request: Request) -> dict[str, object]:
    raw_body = await request.body()
    content_type = request.headers.get("content-type", "")
    parsed_body = _parse_request_body(raw_body, content_type)
    artifact_ref, trace_id = _store_webhook_artifact("hubspot", request, parsed_body, raw_body, content_type)
    _verify_shared_secret(request, settings.hubspot_webhook_secret, "HubSpot")
    return {
        "ok": True,
        "provider": "hubspot",
        "trace_id": trace_id,
        "artifact_ref": artifact_ref,
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
