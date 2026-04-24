from agent.enrichment.common import build_source_ref, utc_now_iso
from agent.enrichment.connectors import crunchbase_connector


def build_crunchbase_funding_signal(
    company_name: str,
    company_domain: str | None,
    *,
    funding_window_months: int = 24,
) -> dict:
    collected_at = utc_now_iso()
    record = crunchbase_connector.lookup(company_name, company_domain)
    if not record:
        return {
            "name": "funding_event",
            "summary": "No Crunchbase ODM record matched this company, so funding is treated as unverified.",
            "confidence": 0.2,
            "observed_at": None,
            "collected_at": collected_at,
            "source_attribution": [
                build_source_ref(
                    source_name="crunchbase_odm",
                    reference=company_domain or company_name,
                    note="No Crunchbase ODM record matched the current company name or domain.",
                    source_type="snapshot_lookup",
                )
            ],
            "edge_case": "missing_crunchbase_record",
            "sector": None,
            "employee_count": 0,
            "funding_musd": 0,
            "funding_months_ago": 999,
            "matched": False,
            "funding_in_window": False,
        }

    funding_months_ago = int(record.get("funding_months_ago") or 999)
    funding_in_window = funding_months_ago <= funding_window_months
    observed_at = record.get("last_funding_announced_at")
    return {
        "name": "funding_event",
        "summary": (
            f"Crunchbase ODM shows about {int(record.get('funding_musd') or 0)}M raised "
            f"{funding_months_ago} months ago."
            if funding_in_window
            else f"Crunchbase ODM matched, but the last funding event is outside the {funding_window_months}-month filter."
        ),
        "confidence": 0.88 if funding_in_window else 0.62,
        "observed_at": observed_at,
        "collected_at": collected_at,
        "source_attribution": [
            build_source_ref(
                source_name="crunchbase_odm",
                reference=record.get("domain") or company_domain or company_name,
                note=(
                    "Matched Crunchbase ODM company record and applied funding recency filter."
                    if funding_in_window
                    else "Matched Crunchbase ODM company record, but the funding event is outside the filter window."
                ),
                observed_at=observed_at,
                source_type="snapshot_lookup",
            )
        ],
        "edge_case": None if funding_in_window else "funding_outside_window",
        "sector": record.get("sector"),
        "employee_count": int(record.get("employee_count") or 0),
        "funding_musd": int(record.get("funding_musd") or 0),
        "funding_months_ago": funding_months_ago,
        "matched": True,
        "funding_in_window": funding_in_window,
    }
