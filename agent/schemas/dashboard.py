from pydantic import BaseModel, Field

from agent.schemas.briefs import ProspectEnrichmentResponse
from agent.schemas.tools import ToolStatus


class RecentTrace(BaseModel):
    trace_id: str
    event_type: str
    timestamp: str
    company_name: str | None = None
    prospect_id: str | None = None


class DashboardStateResponse(BaseModel):
    total_prospects: int = 0
    total_traces: int = 0
    tool_statuses: list[ToolStatus] = Field(default_factory=list)
    recent_snapshots: list[ProspectEnrichmentResponse] = Field(default_factory=list)
    recent_traces: list[RecentTrace] = Field(default_factory=list)
