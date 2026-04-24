import json
from datetime import datetime, timezone

from agent.config import settings
from agent.schemas.tools import ToolExecutionResult, ToolStatus
from agent.utils.http import request_json


class HubSpotMCPClient:
    def status(self) -> ToolStatus:
        configured = bool(settings.hubspot_access_token)
        return ToolStatus(
            name="hubspot",
            label="HubSpot MCP CRM",
            mode="configured" if configured else "mock",
            configured=configured,
            available=True,
            details=(
                "HubSpot MCP integration covers contact upsert, enrichment field writes, "
                "and activity logging. Local artifacts are written unless a HubSpot token is configured."
            ),
        )

    def _write_artifact(self, payload: dict, prospect_id: str) -> str:
        settings.outbox_dir.mkdir(parents=True, exist_ok=True)
        artifact_path = settings.outbox_dir / f"{prospect_id}_hubspot.json"
        artifact_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return str(artifact_path)

    def _contact_properties(self, payload: dict) -> dict[str, object]:
        return {
            "email": payload.get("email"),
            "firstname": (payload.get("contact_name") or payload.get("company_name") or "").split(" ")[0],
            "phone": payload.get("phone"),
            "company": payload.get("company_name"),
            "website": payload.get("company_domain"),
            "lifecyclestage": "lead",
        }

    def _enrichment_properties(self, payload: dict) -> dict[str, object]:
        return {
            "tenacious_segment": payload.get("segment"),
            "tenacious_segment_confidence": payload.get("segment_confidence"),
            "tenacious_ai_maturity_score": payload.get("ai_maturity_score"),
            "tenacious_bench_match": json.dumps(payload.get("bench_match", {})),
            "tenacious_last_inbound_channel": payload.get("last_inbound_channel"),
            "tenacious_last_reply_next_action": payload.get("last_reply_next_action"),
            "tenacious_trace_id": payload.get("trace_id"),
            "tenacious_booking_status": payload.get("booking_status"),
        }

    def _find_contact(self, email: str) -> str | None:
        _, search_response, _ = request_json(
            "POST",
            f"{settings.hubspot_base_url}/crm/v3/objects/contacts/search",
            headers={
                "Authorization": f"Bearer {settings.hubspot_access_token}",
            },
            payload={
                "filterGroups": [
                    {
                        "filters": [
                            {
                                "propertyName": "email",
                                "operator": "EQ",
                                "value": email,
                            }
                        ]
                    }
                ],
                "limit": 1,
            },
        )
        results = search_response.get("results", [])
        return str(results[0]["id"]) if results else None

    def sync_contact_profile(self, payload: dict, prospect_id: str) -> ToolExecutionResult:
        artifact_payload = {
            "action": "sync_contact_profile",
            "payload": payload,
            "transport": "hubspot_mcp",
        }
        artifact_ref = self._write_artifact(artifact_payload, prospect_id)
        status = self.status()
        email = payload.get("email")
        if status.configured and email:
            try:
                contact_id = self._find_contact(str(email))
                properties = self._contact_properties(payload)
                if contact_id:
                    request_json(
                        "PATCH",
                        f"{settings.hubspot_base_url}/crm/v3/objects/contacts/{contact_id}",
                        headers={
                            "Authorization": f"Bearer {settings.hubspot_access_token}",
                        },
                        payload={"properties": properties},
                    )
                else:
                    _, create_response, _ = request_json(
                        "POST",
                        f"{settings.hubspot_base_url}/crm/v3/objects/contacts",
                        headers={
                            "Authorization": f"Bearer {settings.hubspot_access_token}",
                        },
                        payload={"properties": properties},
                    )
                    contact_id = str(create_response.get("id"))
                return ToolExecutionResult(
                    name="hubspot",
                    mode="configured",
                    status="executed",
                    message="HubSpot MCP contact profile synced successfully.",
                    artifact_ref=artifact_ref,
                    external_id=contact_id,
                )
            except Exception as exc:
                return ToolExecutionResult(
                    name="hubspot",
                    mode="configured",
                    status="error",
                    message=f"HubSpot MCP contact sync failed: {exc}",
                    artifact_ref=artifact_ref,
                )
        return ToolExecutionResult(
            name="hubspot",
            mode=status.mode,
            status="previewed",
            message="HubSpot MCP contact payload prepared and recorded.",
            artifact_ref=artifact_ref,
        )

    def write_enrichment_fields(
        self,
        contact_id: str | None,
        enrichment_fields: dict,
        prospect_id: str,
    ) -> ToolExecutionResult:
        artifact_payload = {
            "action": "write_enrichment_fields",
            "contact_id": contact_id,
            "enrichment_fields": enrichment_fields,
            "transport": "hubspot_mcp",
        }
        artifact_ref = self._write_artifact(artifact_payload, prospect_id)
        status = self.status()
        if status.configured and contact_id:
            try:
                request_json(
                    "PATCH",
                    f"{settings.hubspot_base_url}/crm/v3/objects/contacts/{contact_id}",
                    headers={
                        "Authorization": f"Bearer {settings.hubspot_access_token}",
                    },
                    payload={"properties": enrichment_fields},
                )
                return ToolExecutionResult(
                    name="hubspot",
                    mode="configured",
                    status="executed",
                    message="HubSpot MCP enrichment fields written successfully.",
                    artifact_ref=artifact_ref,
                    external_id=contact_id,
                )
            except Exception as exc:
                return ToolExecutionResult(
                    name="hubspot",
                    mode="configured",
                    status="error",
                    message=f"HubSpot MCP enrichment write failed: {exc}",
                    artifact_ref=artifact_ref,
                )
        return ToolExecutionResult(
            name="hubspot",
            mode=status.mode,
            status="previewed",
            message="HubSpot MCP enrichment write recorded locally.",
            artifact_ref=artifact_ref,
            external_id=contact_id,
        )

    def log_activity(
        self,
        contact_id: str | None,
        *,
        activity_type: str,
        activity_summary: str,
        prospect_id: str,
        metadata: dict | None = None,
    ) -> ToolExecutionResult:
        artifact_payload = {
            "action": "log_activity",
            "contact_id": contact_id,
            "activity_type": activity_type,
            "activity_summary": activity_summary,
            "metadata": metadata or {},
            "logged_at": datetime.now(timezone.utc).isoformat(),
            "transport": "hubspot_mcp",
        }
        artifact_ref = self._write_artifact(artifact_payload, prospect_id)
        status = self.status()
        if status.configured and contact_id:
            try:
                request_json(
                    "POST",
                    f"{settings.hubspot_base_url}/crm/v3/objects/notes",
                    headers={
                        "Authorization": f"Bearer {settings.hubspot_access_token}",
                    },
                    payload={
                        "properties": {
                            "hs_note_body": (
                                f"[{activity_type}] {activity_summary}\n\n"
                                f"metadata={json.dumps(metadata or {}, sort_keys=True)}"
                            ),
                        },
                        "associations": [
                            {
                                "to": {"id": contact_id},
                                "types": [
                                    {
                                        "associationCategory": "HUBSPOT_DEFINED",
                                        "associationTypeId": 202,
                                    }
                                ],
                            }
                        ],
                    },
                )
                return ToolExecutionResult(
                    name="hubspot",
                    mode="configured",
                    status="executed",
                    message="HubSpot MCP activity logged successfully.",
                    artifact_ref=artifact_ref,
                    external_id=contact_id,
                )
            except Exception as exc:
                return ToolExecutionResult(
                    name="hubspot",
                    mode="configured",
                    status="error",
                    message=f"HubSpot MCP activity log failed: {exc}",
                    artifact_ref=artifact_ref,
                )
        return ToolExecutionResult(
            name="hubspot",
            mode=status.mode,
            status="previewed",
            message="HubSpot MCP activity log recorded locally.",
            artifact_ref=artifact_ref,
            external_id=contact_id,
        )

    def record_conversation_event(
        self,
        payload: dict,
        prospect_id: str,
        *,
        activity_type: str,
        activity_summary: str,
        metadata: dict | None = None,
    ) -> list[ToolExecutionResult]:
        contact_result = self.sync_contact_profile(payload, prospect_id)
        contact_id = contact_result.external_id
        enrichment_result = self.write_enrichment_fields(
            contact_id,
            self._enrichment_properties(payload),
            prospect_id,
        )
        activity_result = self.log_activity(
            contact_id,
            activity_type=activity_type,
            activity_summary=activity_summary,
            prospect_id=prospect_id,
            metadata=metadata,
        )
        return [contact_result, enrichment_result, activity_result]

    def upsert_contact(self, payload: dict, prospect_id: str) -> ToolExecutionResult:
        return self.sync_contact_profile(payload, prospect_id)


HubSpotClient = HubSpotMCPClient
hubspot_client = HubSpotMCPClient()
