from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field

SegmentName = Literal[
    "recently_funded_startup",
    "mid_market_restructuring",
    "engineering_leadership_transition",
    "specialized_capability_gap",
    "abstain",
]

SEGMENT_DISPLAY_NAMES: dict[str, str] = {
    "recently_funded_startup": "Recently-funded Series A/B startups",
    "mid_market_restructuring": "Mid-market platforms restructuring cost",
    "engineering_leadership_transition": "Engineering-leadership transitions",
    "specialized_capability_gap": "Specialized capability gaps",
    "abstain": "Abstain - exploratory outreach only",
}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class LeadIntakeRequest(BaseModel):
    company_name: str = Field(..., min_length=1)
    company_domain: str | None = None
    contact_name: str | None = None
    contact_email: str | None = None
    contact_phone: str | None = None
    source: str = "synthetic_seed"


class InboundMessageRequest(BaseModel):
    prospect_id: str | None = None
    contact_email: str | None = None
    contact_phone: str | None = None
    channel: Literal["email", "sms"] = "email"
    body: str = Field(..., min_length=1)
    timezone: str | None = None


class SignalConfidence(BaseModel):
    signal_name: str
    score: float = Field(..., ge=0.0, le=1.0)
    rationale: str


class ProspectRecord(BaseModel):
    prospect_id: str = Field(default_factory=lambda: f"pros_{uuid4().hex[:12]}")
    company_name: str
    company_domain: str | None = None
    contact_name: str | None = None
    contact_email: str | None = None
    contact_phone: str | None = None
    source: str = "synthetic_seed"
    primary_segment: SegmentName | None = None
    primary_segment_label: str | None = None
    segment_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    ai_maturity_score: int = Field(default=0, ge=0, le=3)
    status: str = "enriched"
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
