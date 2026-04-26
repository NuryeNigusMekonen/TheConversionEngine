from pydantic import BaseModel, Field

from agent.schemas.briefs import ProspectEnrichmentResponse
from agent.schemas.tools import ToolStatus


class RecentTrace(BaseModel):
    trace_id: str
    event_type: str
    timestamp: str
    company_name: str | None = None
    prospect_id: str | None = None


class DashboardInteractionEvent(BaseModel):
    event_type: str
    channel: str | None = None
    provider: str | None = None
    created_at: str
    payload_summary: str | None = None


class DashboardArtifact(BaseModel):
    name: str
    path: str
    exists: bool = True
    preview: str | None = None
    content_type: str = "text/plain"
    route: str | None = None


class DashboardFlowSummary(BaseModel):
    prospect_id: str | None = None
    company_name: str | None = None
    status: str | None = None
    current_state: str | None = None
    latest_event: str | None = None
    booking_status: str | None = None
    voice_handoff_ready: bool = False
    crm_logged: bool = False


class DashboardStateResponse(BaseModel):
    total_prospects: int = 0
    total_traces: int = 0
    tool_statuses: list[ToolStatus] = Field(default_factory=list)
    recent_snapshots: list[ProspectEnrichmentResponse] = Field(default_factory=list)
    recent_traces: list[RecentTrace] = Field(default_factory=list)
    latest_flow: DashboardFlowSummary | None = None
    latest_interaction_events: list[DashboardInteractionEvent] = Field(default_factory=list)
    latest_artifacts: list[DashboardArtifact] = Field(default_factory=list)
