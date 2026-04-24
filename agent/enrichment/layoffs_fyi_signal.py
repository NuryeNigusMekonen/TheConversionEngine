import csv

from agent.enrichment.common import build_source_ref, utc_now_iso
from agent.enrichment.connectors import layoffs_connector


def parse_layoffs_fyi_csv(raw_csv: str) -> list[dict]:
    rows: list[dict] = []
    reader = csv.DictReader(raw_csv.splitlines())
    for row in reader:
        rows.append(
            {
                "company_name": row.get("company") or row.get("Company"),
                "domain": row.get("domain") or "",
                "days_ago": row.get("days_ago") or row.get("daysAgo") or "",
                "percent": row.get("percentage") or row.get("percent") or "",
                "affected_employees": row.get("laid_off") or row.get("affected_employees") or "",
            }
        )
    return rows


def build_layoff_signal(company_name: str, company_domain: str | None) -> dict:
    collected_at = utc_now_iso()
    record = layoffs_connector.lookup(company_name, company_domain)
    if not record:
        return {
            "name": "layoff_signal",
            "summary": "No layoffs.fyi history matched this company in the current source window.",
            "confidence": 0.78,
            "observed_at": None,
            "collected_at": collected_at,
            "source_attribution": [
                build_source_ref(
                    source_name="layoffs_fyi",
                    reference=company_domain or company_name,
                    note="No layoffs.fyi history matched the company, so the source is treated as a clean no-history result.",
                    source_type="csv_or_snapshot",
                )
            ],
            "edge_case": "no_layoff_history",
            "days_ago": 999,
            "percent": 0,
            "affected_employees": 0,
            "matched": False,
        }

    observed_at = record.get("observed_at")
    return {
        "name": "layoff_signal",
        "summary": (
            f"layoffs.fyi shows about {int(record.get('percent') or 0)}% workforce reduction "
            f"roughly {int(record.get('days_ago') or 0)} days ago."
        ),
        "confidence": 0.83,
        "observed_at": observed_at,
        "collected_at": collected_at,
        "source_attribution": [
            build_source_ref(
                source_name="layoffs_fyi",
                reference=record.get("domain") or company_domain or company_name,
                note="Matched layoffs.fyi snapshot or CSV-derived company row.",
                observed_at=observed_at,
                source_type="csv_or_snapshot",
            )
        ],
        "edge_case": None,
        "days_ago": int(record.get("days_ago") or 999),
        "percent": int(record.get("percent") or 0),
        "affected_employees": int(record.get("affected_employees") or 0),
        "matched": True,
    }
