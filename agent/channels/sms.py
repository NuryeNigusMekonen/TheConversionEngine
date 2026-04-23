import json

from agent.config import settings
from agent.schemas.tools import ToolExecutionResult, ToolStatus
from agent.utils.http import request_form


class SmsChannel:
    def status(self) -> ToolStatus:
        configured = bool(
            settings.outbound_enabled
            and settings.sms_provider.lower() == "africastalking"
            and settings.africas_talking_username
            and settings.africas_talking_api_key
        )
        return ToolStatus(
            name="sms",
            label="Africa's Talking SMS",
            mode="configured" if configured else "mock",
            configured=configured,
            available=True,
            details="Warm-lead SMS handoff uses Africa's Talking only when OUTBOUND_ENABLED=true and credentials are present; otherwise a local preview artifact.",
        )

    def _write_artifact(self, payload: dict, prospect_id: str) -> str:
        settings.outbox_dir.mkdir(parents=True, exist_ok=True)
        artifact_path = settings.outbox_dir / f"{prospect_id}_sms.json"
        artifact_path.write_text(
            json.dumps(payload, indent=2),
            encoding="utf-8",
        )
        return str(artifact_path)

    def send(self, phone_number: str | None, body: str, prospect_id: str) -> ToolExecutionResult:
        payload = {
            "provider": settings.sms_provider,
            "draft": True,
            "outbound_enabled": settings.outbound_enabled,
            "phone_number": phone_number or "warm-lead-preview",
            "body": body,
        }
        artifact_ref = self._write_artifact(payload, prospect_id)
        status = self.status()
        if status.configured and phone_number:
            try:
                _, response_text, _ = request_form(
                    "POST",
                    "https://api.africastalking.com/version1/messaging",
                    headers={
                        "apiKey": settings.africas_talking_api_key,
                        "Accept": "application/json",
                    },
                    payload={
                        "username": settings.africas_talking_username,
                        "to": phone_number,
                        "message": body,
                        "from": settings.africas_talking_sender_id,
                    },
                )
                return ToolExecutionResult(
                    name="sms",
                    mode="configured",
                    status="executed",
                    message="Live SMS request submitted to Africa's Talking.",
                    artifact_ref=artifact_ref,
                    external_id=response_text[:120],
                )
            except Exception as exc:
                return ToolExecutionResult(
                    name="sms",
                    mode="configured",
                    status="error",
                    message=f"Live SMS call failed: {exc}",
                    artifact_ref=artifact_ref,
                )
        return ToolExecutionResult(
            name="sms",
            mode=status.mode,
            status="executed" if status.configured and phone_number else "previewed",
            message=(
                "SMS handoff prepared for a warm lead."
                if phone_number
                else "SMS handoff preview captured because no phone number was provided."
            ),
            artifact_ref=artifact_ref,
        )


sms_channel = SmsChannel()
