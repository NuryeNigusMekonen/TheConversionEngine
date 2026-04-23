import json
from datetime import datetime, timedelta, timezone

from agent.config import settings
from agent.schemas.tools import ToolExecutionResult, ToolStatus
from agent.utils.http import request_json


class CalComClient:
    def status(self) -> ToolStatus:
        configured = bool(settings.calcom_api_key and settings.calcom_event_type_id)
        return ToolStatus(
            name="calcom",
            label="Cal.com Scheduling",
            mode="configured" if configured else "mock",
            configured=configured,
            available=True,
            details="Booking flow creates live bookings when CALCOM_API_KEY and CALCOM_EVENT_TYPE_ID are configured.",
        )

    def _write_artifact(self, payload: dict, prospect_id: str) -> str:
        settings.outbox_dir.mkdir(parents=True, exist_ok=True)
        slot_a = datetime.now(timezone.utc).replace(microsecond=0) + timedelta(days=1, hours=14)
        slot_b = slot_a + timedelta(hours=2)
        artifact_path = settings.outbox_dir / f"{prospect_id}_calcom.json"
        payload.setdefault("suggested_slots_utc", [slot_a.isoformat(), slot_b.isoformat()])
        artifact_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return str(artifact_path)

    def book_preview(self, company_name: str, contact_email: str | None, prospect_id: str) -> ToolExecutionResult:
        artifact_ref = self._write_artifact(
            {
                "event_type_slug": settings.calcom_event_type_slug,
                "company_name": company_name,
                "contact_email": contact_email,
            },
            prospect_id,
        )
        status = self.status()
        if status.configured and contact_email:
            try:
                start_window = datetime.now(timezone.utc).replace(microsecond=0) + timedelta(days=1)
                end_window = start_window + timedelta(days=7)
                slots_url = (
                    f"{settings.calcom_api_base}/v1/slots"
                    f"?apiKey={settings.calcom_api_key}"
                    f"&eventTypeId={settings.calcom_event_type_id}"
                    f"&startTime={start_window.isoformat()}"
                    f"&endTime={end_window.isoformat()}"
                    f"&timeZone={settings.calcom_default_timezone}"
                )
                _, slots_response, _ = request_json("GET", slots_url)
                slots = slots_response.get("slots", {})
                first_slot = None
                for day_slots in slots.values():
                    if day_slots:
                        first_slot = day_slots[0].get("time")
                        break
                if not first_slot:
                    return ToolExecutionResult(
                        name="calcom",
                        mode="configured",
                        status="skipped",
                        message="No available Cal.com slots were returned for the configured event type.",
                        artifact_ref=artifact_ref,
                    )
                _, booking_response, _ = request_json(
                    "POST",
                    f"{settings.calcom_api_base}/v2/bookings",
                    headers={
                        "Authorization": f"Bearer {settings.calcom_api_key}",
                        "cal-api-version": settings.calcom_api_version,
                    },
                    payload={
                        "start": first_slot,
                        "eventTypeId": int(settings.calcom_event_type_id),
                        "attendee": {
                            "name": company_name,
                            "email": contact_email,
                            "timeZone": settings.calcom_default_timezone,
                            "language": "en",
                        },
                        "metadata": {
                            "source": "conversion-engine",
                            "company_name": company_name,
                        },
                    },
                )
                booking_data = booking_response.get("data", {})
                return ToolExecutionResult(
                    name="calcom",
                    mode="configured",
                    status="executed",
                    message="Cal.com booking created successfully.",
                    artifact_ref=artifact_ref,
                    external_id=str(booking_data.get("uid") or booking_data.get("id")),
                )
            except Exception as exc:
                return ToolExecutionResult(
                    name="calcom",
                    mode="configured",
                    status="error",
                    message=f"Cal.com booking failed: {exc}",
                    artifact_ref=artifact_ref,
                )
        return ToolExecutionResult(
            name="calcom",
            mode=status.mode,
            status="executed" if status.configured else "previewed",
            message="Scheduling preview generated with two candidate discovery-call slots.",
            artifact_ref=artifact_ref,
        )


calcom_client = CalComClient()
