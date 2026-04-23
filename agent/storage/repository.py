import json
from datetime import datetime, timezone

from agent.schemas.briefs import (
    CompetitorGapBrief,
    HiringSignalBrief,
    ProspectEnrichmentResponse,
)
from agent.schemas.conversation import ConversationDecision
from agent.schemas.prospect import ProspectRecord
from agent.schemas.tools import ToolchainReport
from agent.storage.database import get_connection, initialize_database


class ProspectRepository:
    def __init__(self) -> None:
        initialize_database()

    def save(self, prospect: ProspectRecord) -> ProspectRecord:
        with get_connection() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO prospects (
                    prospect_id,
                    company_name,
                    company_domain,
                    contact_name,
                    contact_email,
                    contact_phone,
                    source,
                    primary_segment,
                    primary_segment_label,
                    segment_confidence,
                    ai_maturity_score,
                    status,
                    created_at,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    prospect.prospect_id,
                    prospect.company_name,
                    prospect.company_domain,
                    prospect.contact_name,
                    prospect.contact_email,
                    prospect.contact_phone,
                    prospect.source,
                    prospect.primary_segment,
                    prospect.primary_segment_label,
                    prospect.segment_confidence,
                    prospect.ai_maturity_score,
                    prospect.status,
                    prospect.created_at.isoformat(),
                    prospect.updated_at.isoformat(),
                ),
            )
        return prospect

    def list_all(self) -> list[ProspectRecord]:
        with get_connection() as connection:
            rows = connection.execute(
                """
                SELECT
                    prospect_id,
                    company_name,
                    company_domain,
                    contact_name,
                    contact_email,
                    contact_phone,
                    source,
                    primary_segment,
                    primary_segment_label,
                    segment_confidence,
                    ai_maturity_score,
                    status,
                    created_at,
                    updated_at
                FROM prospects
                ORDER BY created_at DESC
                """
            ).fetchall()

        return [ProspectRecord.model_validate(dict(row)) for row in rows]

    def count(self) -> int:
        with get_connection() as connection:
            row = connection.execute("SELECT COUNT(*) AS count FROM prospects").fetchone()
        return int(row["count"])

    def save_snapshot(
        self,
        prospect: ProspectRecord,
        hiring_signal_brief: HiringSignalBrief,
        competitor_gap_brief: CompetitorGapBrief,
        initial_decision: ConversationDecision,
        trace_id: str,
        toolchain_report: ToolchainReport | None = None,
    ) -> ProspectEnrichmentResponse:
        self.save(prospect)
        updated_at = datetime.now(timezone.utc).isoformat()
        with get_connection() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO prospect_briefs (
                    prospect_id,
                    hiring_signal_brief_json,
                    competitor_gap_brief_json,
                    initial_decision_json,
                    trace_id,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    prospect.prospect_id,
                    json.dumps(hiring_signal_brief.model_dump(mode="json")),
                    json.dumps(competitor_gap_brief.model_dump(mode="json")),
                    json.dumps(initial_decision.model_dump(mode="json")),
                    trace_id,
                    updated_at,
                ),
            )
            if toolchain_report is not None:
                connection.execute(
                    """
                    INSERT OR REPLACE INTO prospect_tool_runs (
                        prospect_id,
                        toolchain_report_json,
                        updated_at
                    ) VALUES (?, ?, ?)
                    """,
                    (
                        prospect.prospect_id,
                        json.dumps(toolchain_report.model_dump(mode="json")),
                        updated_at,
                    ),
                )

        return ProspectEnrichmentResponse(
            prospect=prospect,
            hiring_signal_brief=hiring_signal_brief,
            competitor_gap_brief=competitor_gap_brief,
            initial_decision=initial_decision,
            trace_id=trace_id,
            toolchain_report=toolchain_report,
        )

    def get_snapshot(self, prospect_id: str) -> ProspectEnrichmentResponse | None:
        with get_connection() as connection:
            row = connection.execute(
                """
                SELECT
                    p.prospect_id,
                    p.company_name,
                    p.company_domain,
                    p.contact_name,
                    p.contact_email,
                    p.contact_phone,
                    p.source,
                    p.primary_segment,
                    p.primary_segment_label,
                    p.segment_confidence,
                    p.ai_maturity_score,
                    p.status,
                    p.created_at,
                    p.updated_at,
                    b.hiring_signal_brief_json,
                    b.competitor_gap_brief_json,
                    b.initial_decision_json,
                    b.trace_id,
                    tr.toolchain_report_json
                FROM prospects p
                JOIN prospect_briefs b ON b.prospect_id = p.prospect_id
                LEFT JOIN prospect_tool_runs tr ON tr.prospect_id = p.prospect_id
                WHERE p.prospect_id = ?
                """,
                (prospect_id,),
            ).fetchone()

        if row is None:
            return None
        return self._snapshot_from_row(row)

    def find_snapshot_by_contact(
        self,
        *,
        contact_email: str | None = None,
        contact_phone: str | None = None,
    ) -> ProspectEnrichmentResponse | None:
        if not contact_email and not contact_phone:
            return None
        where_clause = "p.contact_email = ?" if contact_email else "p.contact_phone = ?"
        value = contact_email or contact_phone
        with get_connection() as connection:
            row = connection.execute(
                f"""
                SELECT
                    p.prospect_id,
                    p.company_name,
                    p.company_domain,
                    p.contact_name,
                    p.contact_email,
                    p.contact_phone,
                    p.source,
                    p.primary_segment,
                    p.primary_segment_label,
                    p.segment_confidence,
                    p.ai_maturity_score,
                    p.status,
                    p.created_at,
                    p.updated_at,
                    b.hiring_signal_brief_json,
                    b.competitor_gap_brief_json,
                    b.initial_decision_json,
                    b.trace_id,
                    tr.toolchain_report_json
                FROM prospects p
                JOIN prospect_briefs b ON b.prospect_id = p.prospect_id
                LEFT JOIN prospect_tool_runs tr ON tr.prospect_id = p.prospect_id
                WHERE {where_clause}
                ORDER BY b.updated_at DESC
                LIMIT 1
                """,
                (value,),
            ).fetchone()
        return self._snapshot_from_row(row) if row else None

    def list_recent_snapshots(self, limit: int = 6) -> list[ProspectEnrichmentResponse]:
        with get_connection() as connection:
            rows = connection.execute(
                """
                SELECT
                    p.prospect_id,
                    p.company_name,
                    p.company_domain,
                    p.contact_name,
                    p.contact_email,
                    p.contact_phone,
                    p.source,
                    p.primary_segment,
                    p.primary_segment_label,
                    p.segment_confidence,
                    p.ai_maturity_score,
                    p.status,
                    p.created_at,
                    p.updated_at,
                    b.hiring_signal_brief_json,
                    b.competitor_gap_brief_json,
                    b.initial_decision_json,
                    b.trace_id,
                    tr.toolchain_report_json
                FROM prospect_briefs b
                JOIN prospects p ON p.prospect_id = b.prospect_id
                LEFT JOIN prospect_tool_runs tr ON tr.prospect_id = p.prospect_id
                ORDER BY b.updated_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()

        return [self._snapshot_from_row(row) for row in rows]

    def _snapshot_from_row(self, row) -> ProspectEnrichmentResponse:
        hiring_signal_payload = json.loads(row["hiring_signal_brief_json"])
        hiring_signal_payload.setdefault(
            "primary_segment",
            row["primary_segment_label"] or row["primary_segment"] or "Unknown",
        )
        hiring_signal_payload.setdefault(
            "segment_confidence",
            float(row["segment_confidence"] or 0),
        )
        hiring_signal_payload.setdefault(
            "bench_match",
            {
                "required_stacks": [],
                "available_capacity": {},
                "sufficient": True,
                "recommendation": "Legacy brief created before bench-match fields were added.",
            },
        )
        prospect = ProspectRecord.model_validate(
            {
                "prospect_id": row["prospect_id"],
                "company_name": row["company_name"],
                "company_domain": row["company_domain"],
                "contact_name": row["contact_name"],
                "contact_email": row["contact_email"],
                "contact_phone": row["contact_phone"],
                "source": row["source"],
                "primary_segment": row["primary_segment"],
                "primary_segment_label": row["primary_segment_label"],
                "segment_confidence": row["segment_confidence"],
                "ai_maturity_score": row["ai_maturity_score"],
                "status": row["status"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
            }
        )
        return ProspectEnrichmentResponse(
            prospect=prospect,
            hiring_signal_brief=HiringSignalBrief.model_validate(hiring_signal_payload),
            competitor_gap_brief=CompetitorGapBrief.model_validate(
                json.loads(row["competitor_gap_brief_json"])
            ),
            initial_decision=ConversationDecision.model_validate(
                json.loads(row["initial_decision_json"])
            ),
            trace_id=row["trace_id"],
            toolchain_report=(
                ToolchainReport.model_validate(json.loads(row["toolchain_report_json"]))
                if row["toolchain_report_json"]
                else None
            ),
        )
