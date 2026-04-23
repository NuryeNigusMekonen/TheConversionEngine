from pydantic import BaseModel, Field

from agent.schemas.conversation import ConversationDecision
from agent.schemas.prospect import ProspectRecord, SignalConfidence
from agent.schemas.tools import ToolchainReport


class EvidenceRef(BaseModel):
    source_name: str
    reference: str
    note: str


class HiringSignal(BaseModel):
    name: str
    summary: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    evidence: list[EvidenceRef] = Field(default_factory=list)


class BenchMatch(BaseModel):
    required_stacks: list[str] = Field(default_factory=list)
    available_capacity: dict[str, int] = Field(default_factory=dict)
    sufficient: bool = True
    recommendation: str


class HiringSignalBrief(BaseModel):
    summary: str
    primary_segment: str
    segment_confidence: float = Field(..., ge=0.0, le=1.0)
    recommended_pitch_angle: str
    ai_maturity_score: int = Field(..., ge=0, le=3)
    ai_maturity_justification: str
    bench_match: BenchMatch
    confidence_by_signal: list[SignalConfidence] = Field(default_factory=list)
    signals: list[HiringSignal] = Field(default_factory=list)
    do_not_claim: list[str] = Field(default_factory=list)


class CompetitorGapBrief(BaseModel):
    peer_group_definition: str
    peer_companies: list[str] = Field(default_factory=list)
    top_quartile_practices: list[str] = Field(default_factory=list)
    prospect_missing_practices: list[str] = Field(default_factory=list)
    safe_gap_framing: str
    confidence: float = Field(..., ge=0.0, le=1.0)


class ProspectEnrichmentResponse(BaseModel):
    prospect: ProspectRecord
    hiring_signal_brief: HiringSignalBrief
    competitor_gap_brief: CompetitorGapBrief
    initial_decision: ConversationDecision | None = None
    trace_id: str | None = None
    toolchain_report: ToolchainReport | None = None
