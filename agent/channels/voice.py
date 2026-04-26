import json
from urllib.error import HTTPError

from agent.config import settings
from agent.schemas.prospect import InboundMessageRequest
from agent.schemas.tools import ToolExecutionResult, ToolStatus
from agent.utils.http import request_json


class VoiceWebhookError(RuntimeError):
    pass


class VoiceChannel:
    def status(self) -> ToolStatus:
        configured = bool(
            settings.outbound_enabled
            and settings.voice_provider.lower() == "shared_voice_rig"
            and settings.shared_voice_rig_webhook_url
            and settings.shared_voice_rig_keyword_prefix
        )
        return ToolStatus(
            name="voice",
            label="Shared Voice Rig",
            mode="configured" if configured else "mock",
            configured=configured,
            available=True,
            details=(
                "Bonus-tier voice handoff uses the Shared Voice Rig when OUTBOUND_ENABLED=true "
                "and the rig webhook plus keyword prefix are configured; otherwise a local "
                "delivery-lead handoff artifact is written."
            ),
        )

    def _write_artifact(self, payload: dict, prospect_id: str) -> str:
        settings.outbox_dir.mkdir(parents=True, exist_ok=True)
        artifact_path = settings.outbox_dir / f"{prospect_id}_voice.json"
        artifact_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return str(artifact_path)

    def prepare_handoff(
        self,
        *,
        phone_number: str | None,
        prospect_id: str,
        company_name: str,
        contact_name: str | None,
        contact_email: str | None,
        allow_warm_lead: bool = False,
        booking_link: str | None = None,
        context_brief: str | None = None,
        context_brief_artifact_ref: str | None = None,
        reason: str = "warm_lead_voice_handoff",
    ) -> ToolExecutionResult:
        payload = {
            "provider": settings.voice_provider,
            "draft": True,
            "outbound_enabled": settings.outbound_enabled,
            "phone_number": phone_number or "voice-preview",
            "company_name": company_name,
            "contact_name": contact_name,
            "contact_email": contact_email,
            "booking_link": booking_link,
            "allow_warm_lead": allow_warm_lead,
            "keyword_prefix": settings.shared_voice_rig_keyword_prefix,
            "reason": reason,
            "context_brief": context_brief,
            "context_brief_artifact_ref": context_brief_artifact_ref,
        }
        artifact_ref = self._write_artifact(payload, prospect_id)
        status = self.status()
        if not allow_warm_lead:
            return ToolExecutionResult(
                name="voice",
                mode=status.mode,
                status="skipped",
                message="Voice handoff blocked by warm-lead gate because no prior email reply is recorded.",
                artifact_ref=artifact_ref,
            )
        if status.configured and phone_number:
            try:
                _, response, _ = request_json(
                    "POST",
                    settings.shared_voice_rig_webhook_url,
                    headers={
                        **(
                            {"Authorization": f"Bearer {settings.shared_voice_rig_api_key}"}
                            if settings.shared_voice_rig_api_key
                            else {}
                        ),
                    },
                    payload={
                        "keyword_prefix": settings.shared_voice_rig_keyword_prefix,
                        "phone_number": phone_number,
                        "company_name": company_name,
                        "contact_name": contact_name,
                        "contact_email": contact_email,
                        "booking_link": booking_link,
                        "reason": reason,
                        "context_brief": context_brief,
                        "context_brief_artifact_ref": context_brief_artifact_ref,
                    },
                )
                external_id = response.get("id") or response.get("call_id") or response.get("session_id")
                return ToolExecutionResult(
                    name="voice",
                    mode="configured",
                    status="executed",
                    message="Voice handoff submitted to the Shared Voice Rig.",
                    artifact_ref=artifact_ref,
                    external_id=str(external_id) if external_id else None,
                )
            except HTTPError as exc:
                if exc.code in {401, 403}:
                    return ToolExecutionResult(
                        name="voice",
                        mode="mock",
                        status="previewed",
                        message=(
                            "Shared Voice Rig rejected the current credentials or registration; "
                            f"kept a handoff artifact instead ({exc})."
                        ),
                        artifact_ref=artifact_ref,
                    )
                return ToolExecutionResult(
                    name="voice",
                    mode="configured",
                    status="error",
                    message=f"Shared Voice Rig call failed: {exc}",
                    artifact_ref=artifact_ref,
                )
            except Exception as exc:
                return ToolExecutionResult(
                    name="voice",
                    mode="configured",
                    status="error",
                    message=f"Shared Voice Rig call failed: {exc}",
                    artifact_ref=artifact_ref,
                )
        return ToolExecutionResult(
            name="voice",
            mode=status.mode,
            status="executed" if status.configured and phone_number else "previewed",
            message=(
                "Voice handoff prepared for the delivery lead."
                if phone_number
                else "Voice handoff preview captured because no phone number was provided."
            ),
            artifact_ref=artifact_ref,
        )

    def handle_shared_voice_webhook(self, payload: dict) -> InboundMessageRequest:
        body = payload.get("body") if isinstance(payload.get("body"), dict) else payload
        data = body.get("data") if isinstance(body.get("data"), dict) else body
        sender = (
            data.get("from")
            or data.get("phone_number")
            or data.get("caller")
            or body.get("from")
            or body.get("phone_number")
        )
        transcript = (
            data.get("transcript")
            or data.get("summary")
            or data.get("message")
            or body.get("transcript")
            or body.get("summary")
            or body.get("message")
            or body.get("body")
        )
        if isinstance(sender, dict):
            sender = sender.get("phone") or sender.get("number")
        if not sender or not transcript:
            raise VoiceWebhookError(
                "Shared Voice Rig webhook is missing caller phone number or transcript body."
            )
        return InboundMessageRequest(
            contact_phone=str(sender).strip(),
            channel="voice",
            body=str(transcript).strip(),
        )


voice_channel = VoiceChannel()
