from agent.enrichment.common import build_source_ref, utc_now_iso
from agent.enrichment.connectors import crunchbase_connector, leadership_connector


def build_leadership_change_signal(
    company_name: str,
    company_domain: str | None,
    *,
    window_days: int = 120,
) -> dict:
    collected_at = utc_now_iso()
    leadership_record = leadership_connector.lookup(company_name, company_domain)
    crunchbase_record = crunchbase_connector.lookup(company_name, company_domain)

    record = leadership_record
    source_name = "leadership_snapshot"
    if not record and crunchbase_record and isinstance(crunchbase_record.get("leadership_change"), dict):
        record = crunchbase_record["leadership_change"]
        source_name = "crunchbase_odm"

    if not record:
        return {
            "name": "leadership_change",
            "summary": f"No leadership change was found in the last {window_days} days.",
            "confidence": 0.74,
            "observed_at": None,
            "collected_at": collected_at,
            "source_attribution": [
                build_source_ref(
                    source_name="press_or_crunchbase_records",
                    reference=company_domain or company_name,
                    note="No press-derived or Crunchbase-derived leadership change matched the company in the active window.",
                    source_type="snapshot_lookup",
                )
            ],
            "edge_case": "no_leadership_change_in_window",
            "role": None,
            "person": None,
            "days_ago": 999,
            "matched": False,
        }

    days_ago = int(record.get("days_ago") or 999)
    observed_at = record.get("observed_at")
    in_window = days_ago <= window_days
    return {
        "name": "leadership_change",
        "summary": (
            f"Leadership-change signal shows {record.get('role') or 'an executive'} transition "
            f"about {days_ago} days ago."
            if in_window
            else f"Leadership change data matched, but no transition falls within the last {window_days} days."
        ),
        "confidence": 0.81 if in_window else 0.58,
        "observed_at": observed_at,
        "collected_at": collected_at,
        "source_attribution": [
            build_source_ref(
                source_name=source_name,
                reference=record.get("domain") or company_domain or company_name,
                note="Matched press or Crunchbase-derived leadership change record.",
                observed_at=observed_at,
                source_type="press_or_crunchbase_record",
            )
        ],
        "edge_case": None if in_window else "leadership_change_outside_window",
        "role": record.get("role"),
        "person": record.get("person"),
        "days_ago": days_ago,
        "matched": True,
    }
