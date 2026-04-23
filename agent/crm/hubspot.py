import json

from agent.config import settings
from agent.schemas.tools import ToolExecutionResult, ToolStatus
from agent.utils.http import request_json


class HubSpotClient:
    def status(self) -> ToolStatus:
        configured = bool(settings.hubspot_access_token)
        return ToolStatus(
            name="hubspot",
            label="HubSpot CRM",
            mode="configured" if configured else "mock",
            configured=configured,
            available=True,
            details="Contact sync writes a local artifact unless a HubSpot token is configured.",
        )

    def _write_artifact(self, payload: dict, prospect_id: str) -> str:
        settings.outbox_dir.mkdir(parents=True, exist_ok=True)
        artifact_path = settings.outbox_dir / f"{prospect_id}_hubspot.json"
        artifact_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return str(artifact_path)

    def upsert_contact(self, payload: dict, prospect_id: str) -> ToolExecutionResult:
        artifact_ref = self._write_artifact(payload, prospect_id)
        status = self.status()
        email = payload.get("email")
        if status.configured and email:
            try:
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
                properties = {
                    "email": email,
                    "firstname": (payload.get("contact_name") or payload.get("company_name") or "").split(" ")[0],
                    "phone": payload.get("phone"),
                    "company": payload.get("company_name"),
                    "website": payload.get("company_domain"),
                    "lifecyclestage": "lead",
                }
                results = search_response.get("results", [])
                if results:
                    contact_id = results[0]["id"]
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
                    contact_id = create_response.get("id")
                return ToolExecutionResult(
                    name="hubspot",
                    mode="configured",
                    status="executed",
                    message="HubSpot contact upserted successfully.",
                    artifact_ref=artifact_ref,
                    external_id=str(contact_id),
                )
            except Exception as exc:
                return ToolExecutionResult(
                    name="hubspot",
                    mode="configured",
                    status="error",
                    message=f"HubSpot upsert failed: {exc}",
                    artifact_ref=artifact_ref,
                )
        return ToolExecutionResult(
            name="hubspot",
            mode=status.mode,
            status="executed" if status.configured else "previewed",
            message="HubSpot contact payload prepared and recorded.",
            artifact_ref=artifact_ref,
        )


hubspot_client = HubSpotClient()
