from datetime import datetime, timezone

from agent.schemas.briefs import EvidenceRef


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def normalize_company_key(value: str | None) -> str:
    return "".join(char for char in (value or "").lower() if char.isalnum())


def build_source_ref(
    *,
    source_name: str,
    reference: str,
    note: str,
    observed_at: str | None = None,
    source_type: str | None = None,
) -> EvidenceRef:
    return EvidenceRef(
        source_name=source_name,
        reference=reference,
        note=note,
        observed_at=observed_at,
        source_type=source_type,
    )
