import json

from agent.config import settings
from agent.schemas.tools import ToolExecutionResult, ToolStatus
from agent.utils.http import request_json


class EmailChannel:
    def status(self) -> ToolStatus:
        provider = settings.email_provider.lower()
        if provider == "resend":
            configured = bool(settings.outbound_enabled and settings.resend_api_key)
            return ToolStatus(
                name="email",
                label="Resend Email",
                mode="configured" if configured else "mock",
                configured=configured,
                available=True,
                details="Uses Resend only when OUTBOUND_ENABLED=true and API credentials are present; otherwise writes draft outbox artifacts.",
            )
        if provider == "mailersend":
            configured = bool(settings.outbound_enabled and settings.mailersend_api_key)
            return ToolStatus(
                name="email",
                label="MailerSend Email",
                mode="configured" if configured else "mock",
                configured=configured,
                available=True,
                details="Uses MailerSend only when OUTBOUND_ENABLED=true and API credentials are present; otherwise writes draft outbox artifacts.",
            )
        return ToolStatus(
            name="email",
            label="Email Draft Outbox",
            mode="mock",
            configured=False,
            available=True,
            details="No live provider selected, so outbound email is captured locally.",
        )

    def _write_artifact(self, payload: dict, prospect_id: str) -> str:
        settings.outbox_dir.mkdir(parents=True, exist_ok=True)
        artifact_path = settings.outbox_dir / f"{prospect_id}_email.json"
        artifact_path.write_text(
            json.dumps(payload, indent=2),
            encoding="utf-8",
        )
        return str(artifact_path)

    def send(self, recipient: str | None, subject: str, body: str, prospect_id: str) -> ToolExecutionResult:
        payload = {
            "provider": settings.email_provider,
            "draft": True,
            "outbound_enabled": settings.outbound_enabled,
            "recipient": recipient or settings.resend_from_email,
            "subject": subject,
            "body": body,
        }
        artifact_ref = self._write_artifact(payload, prospect_id)
        status = self.status()
        if recipient and status.configured:
            try:
                if settings.email_provider.lower() == "resend":
                    _, response, _ = request_json(
                        "POST",
                        "https://api.resend.com/emails",
                        headers={
                            "Authorization": f"Bearer {settings.resend_api_key}",
                        },
                        payload={
                            "from": settings.resend_from_email,
                            "to": [recipient],
                            "subject": subject,
                            "text": body,
                            "html": f"<pre>{body}</pre>",
                            **(
                                {"reply_to": settings.resend_reply_to}
                                if settings.resend_reply_to
                                else {}
                            ),
                        },
                    )
                    external_id = response.get("id")
                else:
                    _, _, response_headers = request_json(
                        "POST",
                        "https://api.mailersend.com/v1/email",
                        headers={
                            "Authorization": f"Bearer {settings.mailersend_api_key}",
                        },
                        payload={
                            "from": {
                                "email": settings.mailersend_from_email,
                                "name": settings.mailersend_from_name,
                            },
                            "to": [{"email": recipient}],
                            "subject": subject,
                            "text": body,
                            "html": f"<pre>{body}</pre>",
                        },
                    )
                    external_id = response_headers.get("x-message-id")
                return ToolExecutionResult(
                    name="email",
                    mode="configured",
                    status="executed",
                    message=f"Live email submitted for delivery to {recipient}.",
                    artifact_ref=artifact_ref,
                    external_id=external_id,
                )
            except Exception as exc:
                return ToolExecutionResult(
                    name="email",
                    mode="configured",
                    status="error",
                    message=f"Live email call failed: {exc}",
                    artifact_ref=artifact_ref,
                )
        return ToolExecutionResult(
            name="email",
            mode=status.mode,
            status="executed" if status.configured else "previewed",
            message=(
                f"Email payload prepared for {recipient or 'local sink'} via {status.label}."
            ),
            artifact_ref=artifact_ref,
        )


email_channel = EmailChannel()
