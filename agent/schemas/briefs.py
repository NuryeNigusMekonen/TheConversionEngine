from pydantic import BaseModel, Field

from agent.schemas.conversation import ConversationDecision
from agent.schemas.prospect import ProspectRecord, SignalConfidence
from agent.schemas.tools import ToolchainReport


class EvidenceRef(BaseModel):
    source_name: str
    reference: str
    note: str
    observed_at: str | None = None
    source_type: str | None = None


class HiringSignal(BaseModel):
    name: str
    summary: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    evidence: list[EvidenceRef] = Field(default_factory=list)
    source_attribution: list[EvidenceRef] = Field(default_factory=list)
    observed_at: str | None = None
    collected_at: str | None = None
    edge_case: str | None = None


class AIMaturitySignalInput(BaseModel):
    name: str
    tier: str
    weight: int
    observed: bool
    value: str
    justification: str


class AIMaturityAssessment(BaseModel):
    score: int = Field(..., ge=0, le=3)
    confidence: float = Field(..., ge=0.0, le=1.0)
    summary: str
    silent_company: bool = False
    inputs: list[AIMaturitySignalInput] = Field(default_factory=list)


class SectorDistributionPosition(BaseModel):
    rank: int
    total_companies: int
    percentile: float = Field(..., ge=0.0, le=100.0)
    quartile: str
    target_score: int = Field(..., ge=0, le=3)
    top_quartile_cutoff_score: int = Field(..., ge=0, le=3)


class GapPractice(BaseModel):
    practice_name: str
    description: str
    observed_by_peer_count: int = 0
    evidence: list[EvidenceRef] = Field(default_factory=list)


class CompetitorComparable(BaseModel):
    company_name: str
    company_domain: str | None = None
    sector: str
    rank_score: float
    ai_maturity_score: int = Field(..., ge=0, le=3)
    ai_maturity_confidence: float = Field(..., ge=0.0, le=1.0)
    employee_count: int = Field(default=0, ge=0)
    funding_musd: int = Field(default=0, ge=0)


class BenchMatch(BaseModel):
    required_stacks: list[str] = Field(default_factory=list)
    available_capacity: dict[str, int] = Field(default_factory=dict)
    sufficient: bool = True
    recommendation: str


class HiringSignalBrief(BaseModel):
    summary: str
    generated_at: str | None = None
    primary_segment: str
    segment_confidence: float = Field(..., ge=0.0, le=1.0)
    recommended_pitch_angle: str
    ai_maturity_score: int = Field(..., ge=0, le=3)
    ai_maturity_assessment: AIMaturityAssessment | None = None
    ai_maturity_justification: str
    bench_match: BenchMatch
    confidence_by_signal: list[SignalConfidence] = Field(default_factory=list)
    signals: list[HiringSignal] = Field(default_factory=list)
    do_not_claim: list[str] = Field(default_factory=list)


class CompetitorGapBrief(BaseModel):
    selection_criteria: str | None = None
    peer_group_definition: str
    peer_companies: list[str] = Field(default_factory=list)
    top_quartile_companies: list[str] = Field(default_factory=list)
    comparables: list[CompetitorComparable] = Field(default_factory=list)
    sector_distribution: SectorDistributionPosition | None = None
    top_quartile_practices: list[str] = Field(default_factory=list)
    gap_practices: list[GapPractice] = Field(default_factory=list)
    prospect_missing_practices: list[str] = Field(default_factory=list)
    sparse_sector: bool = False
    sparse_sector_note: str | None = None
    safe_gap_framing: str
    confidence: float = Field(..., ge=0.0, le=1.0)


class ProspectEnrichmentResponse(BaseModel):
    prospect: ProspectRecord
    hiring_signal_brief: HiringSignalBrief
    competitor_gap_brief: CompetitorGapBrief
    initial_decision: ConversationDecision | None = None
    trace_id: str | None = None
    toolchain_report: ToolchainReport | None = None
