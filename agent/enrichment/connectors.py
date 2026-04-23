import csv
import json
from pathlib import Path
from urllib.request import urlopen

from agent.config import settings
from agent.schemas.tools import ToolExecutionResult, ToolStatus


def _normalize(value: str | None) -> str:
    return "".join(char for char in (value or "").lower() if char.isalnum())


class BaseEnrichmentConnector:
    name = "connector"
    label = "Connector"
    snapshot_path: Path | None = None
    live_url: str = ""
    details = "Connector not configured."

    def status(self) -> ToolStatus:
        has_snapshot = bool(self.snapshot_path and self.snapshot_path.exists())
        has_live = bool(self.live_url)
        configured = has_snapshot or has_live
        if has_live:
            details = f"Uses live source {self.live_url} with snapshot fallback when available."
        elif has_snapshot:
            details = f"Uses local snapshot at {self.snapshot_path}."
        else:
            details = self.details
        return ToolStatus(
            name=self.name,
            label=self.label,
            mode="configured" if configured else "mock",
            configured=configured,
            available=True,
            details=details,
        )

    def _load_records(self) -> list[dict]:
        if self.snapshot_path and self.snapshot_path.exists():
            with open(self.snapshot_path, encoding="utf-8") as handle:
                return json.load(handle)
        if self.live_url:
            with urlopen(self.live_url, timeout=20) as response:
                raw = response.read().decode("utf-8")
                return self._parse_live_payload(raw)
        return []

    def _parse_live_payload(self, raw: str) -> list[dict]:
        return json.loads(raw)

    def lookup(self, company_name: str, company_domain: str | None) -> dict | None:
        records = self._load_records()
        normalized_domain = _normalize(company_domain)
        normalized_name = _normalize(company_name)
        for record in records:
            if normalized_domain and _normalize(record.get("domain")) == normalized_domain:
                return record
        for record in records:
            if _normalize(record.get("company_name")) == normalized_name:
                return record
        return None

    def run(self, prospect_id: str, matched: bool) -> ToolExecutionResult:
        status = self.status()
        return ToolExecutionResult(
            name=self.name,
            mode=status.mode,
            status="executed" if matched and status.configured else "previewed",
            message=(
                f"{self.label} contributed a matched source record."
                if matched and status.configured
                else f"{self.label} has no direct match for this prospect yet."
            ),
            artifact_ref=f"prospect:{prospect_id}",
        )


class CrunchbaseConnector(BaseEnrichmentConnector):
    name = "crunchbase"
    label = "Crunchbase ODM"
    snapshot_path = settings.crunchbase_snapshot_path
    details = "Set CRUNCHBASE_SNAPSHOT_PATH to a JSON snapshot of company records."


class LayoffsConnector(BaseEnrichmentConnector):
    name = "layoffs_fyi"
    label = "layoffs.fyi"
    snapshot_path = settings.layoffs_snapshot_path
    live_url = settings.layoffs_csv_url
    details = "Set LAYOFFS_SNAPSHOT_PATH or LAYOFFS_CSV_URL to use real layoff data."

    def _parse_live_payload(self, raw: str) -> list[dict]:
        rows = []
        reader = csv.DictReader(raw.splitlines())
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


class JobPostsConnector(BaseEnrichmentConnector):
    name = "job_posts"
    label = "Public Job Posts"
    snapshot_path = settings.job_posts_snapshot_path
    details = "Set JOB_POSTS_SNAPSHOT_PATH to a JSON snapshot of public job-post signals."


class LeadershipConnector(BaseEnrichmentConnector):
    name = "leadership"
    label = "Leadership Signal"
    snapshot_path = settings.leadership_snapshot_path
    details = "Set LEADERSHIP_SNAPSHOT_PATH to a JSON snapshot of leadership changes."


crunchbase_connector = CrunchbaseConnector()
layoffs_connector = LayoffsConnector()
job_posts_connector = JobPostsConnector()
leadership_connector = LeadershipConnector()
