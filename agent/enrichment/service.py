import hashlib
import json
import re

from agent.config import settings
from agent.enrichment.connectors import (
    crunchbase_connector,
    job_posts_connector,
    layoffs_connector,
    leadership_connector,
)
from agent.schemas.briefs import (
    CompetitorGapBrief,
    EvidenceRef,
    BenchMatch,
    HiringSignal,
    HiringSignalBrief,
)
from agent.schemas.prospect import (
    SEGMENT_DISPLAY_NAMES,
    LeadIntakeRequest,
    ProspectRecord,
    SignalConfidence,
)


class EnrichmentService:
    """Hybrid enrichment flow backed by local snapshots with heuristic fallback."""

    SECTOR_KEYWORDS = {
        "fintech": {"pay", "fin", "bank", "credit", "lending", "treasury"},
        "healthtech": {"health", "care", "clinic", "med", "patient"},
        "commerce": {"shop", "retail", "market", "commerce", "cart"},
        "devtools": {"dev", "cloud", "infra", "platform", "data", "stack"},
    }

    PEER_COMPANIES = {
        "fintech": ["LedgerPeak", "Northbank OS", "ClearMint", "Arc Treasury"],
        "healthtech": ["CareGrid", "SignalRx", "ClinicFlow", "PatientLake"],
        "commerce": ["CartPilot", "ModeMarket", "RetailGraph", "LoopSupply"],
        "devtools": ["Buildplane", "OrbitStack", "TensorDock", "Lakebase"],
        "general_b2b": ["Northstar Labs", "RelayCore", "Axiom Works", "Fieldcraft"],
    }

    def _stable_int(self, key: str, start: int, end: int) -> int:
        digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
        span = end - start + 1
        return start + (int(digest[:8], 16) % span)

    def _tokens(self, *parts: str | None) -> set[str]:
        text = " ".join(part or "" for part in parts).lower()
        return set(re.findall(r"[a-z0-9]+", text))

    def _infer_sector(self, tokens: set[str]) -> str:
        for sector, keywords in self.SECTOR_KEYWORDS.items():
            if tokens & keywords:
                return sector
        return "general_b2b"

    def _infer_ai_maturity(
        self,
        tokens: set[str],
        job_openings: int,
        ai_roles: int,
    ) -> tuple[int, str, float]:
        ai_keywords = {"ai", "ml", "llm", "agent", "model", "inference", "data"}
        ai_hits = len(tokens & ai_keywords) + ai_roles
        if ai_hits >= 4 and job_openings >= 8:
            return 3, "Open roles and company-language suggest an active AI function.", 0.82
        if ai_hits >= 2 or ai_roles >= 1:
            return 2, "Some AI or data-platform evidence is visible in the source records.", 0.71
        if job_openings >= 4:
            return 1, "Engineering growth is visible, but AI-specific signals are still limited.", 0.54
        return 0, "No reliable AI-specific evidence was found in the matched records.", 0.41

    def _load_bench_capacity(self) -> dict[str, int]:
        if not settings.bench_summary_path.exists():
            return {}
        with open(settings.bench_summary_path, encoding="utf-8") as handle:
            bench = json.load(handle)
        return {
            stack_name: int(stack.get("available_engineers", 0))
            for stack_name, stack in bench.get("stacks", {}).items()
        }

    def _infer_required_stacks(self, tokens: set[str], ai_roles: int, sector: str) -> list[str]:
        required: set[str] = set()
        if tokens & {"python", "django", "fastapi", "flask"}:
            required.add("python")
        if tokens & {"go", "grpc", "microservices"}:
            required.add("go")
        if tokens & {"data", "analytics", "dbt", "snowflake", "databricks"}:
            required.add("data")
        if ai_roles or tokens & {"ai", "ml", "llm", "agent", "inference", "scientist"}:
            required.add("ml")
        if tokens & {"infra", "cloud", "platform", "kubernetes", "terraform"}:
            required.add("infra")
        if tokens & {"react", "frontend", "typescript", "next"}:
            required.add("frontend")
        if not required:
            required.add("data" if sector in {"fintech", "commerce", "healthtech"} else "python")
        return sorted(required)

    def _classify_segment(
        self,
        *,
        employee_estimate: int,
        funding_musd: int,
        funding_months_ago: int,
        job_openings: int,
        layoff_days_ago: int,
        layoff_pct: int,
        leadership_days_ago: int,
        ai_maturity_score: int,
        ai_roles: int,
        source_hits: int,
    ) -> tuple[str, float]:
        fresh_funding = funding_months_ago <= 6 and 5 <= funding_musd <= 30
        recent_layoff = layoff_days_ago <= 120 and layoff_pct <= 40
        leadership_recent = leadership_days_ago <= 90
        specialized_signal = ai_maturity_score >= 2 and ai_roles > 0

        if recent_layoff and fresh_funding and employee_estimate >= 180 and job_openings >= 3:
            confidence = 0.82
            segment = "mid_market_restructuring"
        elif leadership_recent and 50 <= employee_estimate <= 500:
            confidence = 0.78
            segment = "engineering_leadership_transition"
        elif specialized_signal:
            confidence = 0.74
            segment = "specialized_capability_gap"
        elif fresh_funding and 15 <= employee_estimate <= 80 and job_openings >= 5:
            confidence = 0.76
            segment = "recently_funded_startup"
        else:
            confidence = 0.45
            segment = "abstain"

        confidence += min(0.12, source_hits * 0.03)
        if segment == "recently_funded_startup" and recent_layoff and layoff_pct > 15:
            segment = "mid_market_restructuring"
            confidence = min(confidence, 0.72)
        if confidence < 0.6:
            return "abstain", round(confidence, 2)
        return segment, round(min(confidence, 0.94), 2)

    def _build_evidence(
        self,
        source_name: str,
        reference: str,
        note: str,
    ) -> list[EvidenceRef]:
        return [
            EvidenceRef(
                source_name=source_name,
                reference=reference,
                note=note,
            )
        ]

    def enrich(self, intake: LeadIntakeRequest) -> tuple[
        ProspectRecord,
        HiringSignalBrief,
        CompetitorGapBrief,
    ]:
        seed_key = f"{intake.company_name}|{intake.company_domain or ''}|{intake.contact_email or ''}"
        tokens = self._tokens(intake.company_name, intake.company_domain)

        company_record = crunchbase_connector.lookup(intake.company_name, intake.company_domain)
        jobs_record = job_posts_connector.lookup(intake.company_name, intake.company_domain)
        layoffs_record = layoffs_connector.lookup(intake.company_name, intake.company_domain)
        leadership_record = leadership_connector.lookup(intake.company_name, intake.company_domain)
        source_hits = sum(
            1 for record in (company_record, jobs_record, layoffs_record, leadership_record) if record
        )

        sector = (
            (company_record or {}).get("sector")
            or self._infer_sector(tokens)
        )
        employee_estimate = int(
            (company_record or {}).get("employee_count")
            or self._stable_int(seed_key + "employees", 18, 900)
        )
        funding_musd = int(
            (company_record or {}).get("funding_musd")
            or self._stable_int(seed_key + "funding", 4, 28)
        )
        funding_months_ago = int(
            (company_record or {}).get("funding_months_ago")
            or self._stable_int(seed_key + "funding_months", 1, 6)
        )
        job_openings = int(
            (jobs_record or {}).get("open_engineering_roles")
            or self._stable_int(seed_key + "jobs", 1, 18)
        )
        ai_roles = int((jobs_record or {}).get("ai_roles") or 0)
        growth_delta_60d_pct = int((jobs_record or {}).get("growth_delta_60d_pct") or 0)
        job_examples = (jobs_record or {}).get("examples") or []
        tokens |= self._tokens(*job_examples)
        layoff_days_ago = int(
            (layoffs_record or {}).get("days_ago")
            or self._stable_int(seed_key + "layoff_days", 25, 150)
        )
        layoff_pct = int(
            (layoffs_record or {}).get("percent")
            or self._stable_int(seed_key + "layoff_pct", 6, 22)
        )
        leadership_days_ago = int(
            (leadership_record or {}).get("days_ago")
            or self._stable_int(seed_key + "leader_days", 18, 120)
        )

        ai_maturity_score, ai_justification, ai_confidence = self._infer_ai_maturity(
            tokens=tokens,
            job_openings=job_openings,
            ai_roles=ai_roles,
        )

        funding_confidence = 0.86 if company_record else (0.68 if funding_months_ago <= 4 else 0.55)
        jobs_confidence = 0.84 if jobs_record else (0.66 if job_openings >= 8 else 0.47)
        layoff_confidence = 0.82 if layoffs_record else (0.64 if employee_estimate >= 180 else 0.43)
        leadership_confidence = 0.8 if leadership_record else (0.69 if leadership_days_ago <= 90 else 0.44)

        primary_segment, segment_confidence = self._classify_segment(
            employee_estimate=employee_estimate,
            funding_musd=funding_musd,
            funding_months_ago=funding_months_ago,
            job_openings=job_openings,
            layoff_days_ago=layoff_days_ago if layoffs_record else 999,
            layoff_pct=layoff_pct,
            leadership_days_ago=leadership_days_ago if leadership_record else 999,
            ai_maturity_score=ai_maturity_score,
            ai_roles=ai_roles,
            source_hits=source_hits,
        )
        segment_label = SEGMENT_DISPLAY_NAMES[primary_segment]

        prospect = ProspectRecord(
            company_name=intake.company_name,
            company_domain=intake.company_domain,
            contact_name=intake.contact_name,
            contact_email=intake.contact_email,
            contact_phone=intake.contact_phone,
            source=intake.source,
            primary_segment=primary_segment,
            primary_segment_label=segment_label,
            segment_confidence=segment_confidence,
            ai_maturity_score=ai_maturity_score,
            status="source_backed_brief_ready",
        )

        confidence_by_signal = [
            SignalConfidence(
                signal_name="funding_event",
                score=funding_confidence,
                rationale=(
                    "Matched local Crunchbase-style snapshot data."
                    if company_record
                    else "No company snapshot match was found, so funding timing used heuristic fallback."
                ),
            ),
            SignalConfidence(
                signal_name="job_post_velocity",
                score=jobs_confidence,
                rationale=(
                    "Matched local public job-post snapshot data."
                    if jobs_record
                    else "No job-post snapshot match was found, so hiring estimates used heuristic fallback."
                ),
            ),
            SignalConfidence(
                signal_name="layoff_signal",
                score=layoff_confidence,
                rationale=(
                    "Matched layoff snapshot data."
                    if layoffs_record
                    else "No layoff snapshot match was found, so restructuring pressure used heuristic fallback."
                ),
            ),
            SignalConfidence(
                signal_name="leadership_change",
                score=leadership_confidence,
                rationale=(
                    "Matched leadership-change snapshot data."
                    if leadership_record
                    else "No leadership snapshot match was found, so timing used heuristic fallback."
                ),
            ),
            SignalConfidence(
                signal_name="ai_maturity",
                score=ai_confidence,
                rationale=ai_justification,
            ),
        ]

        hiring_signals = [
            HiringSignal(
                name="funding_event",
                summary=f"Funding signal: about {funding_musd}M raised {funding_months_ago} months ago.",
                confidence=funding_confidence,
                evidence=self._build_evidence(
                    "crunchbase_snapshot" if company_record else "heuristic_fallback",
                    company_record.get("domain", seed_key) if company_record else seed_key,
                    "Matched company snapshot." if company_record else "Fallback estimate derived from the input seed.",
                ),
            ),
            HiringSignal(
                name="job_post_velocity",
                summary=(
                    f"Public job-post signal: {job_openings} engineering openings, "
                    f"{growth_delta_60d_pct}% change over 60 days."
                ),
                confidence=jobs_confidence,
                evidence=self._build_evidence(
                    "job_posts_snapshot" if jobs_record else "heuristic_fallback",
                    jobs_record.get("domain", seed_key) if jobs_record else seed_key,
                    "Matched job-post snapshot." if jobs_record else "Fallback estimate derived from the input seed.",
                ),
            ),
            HiringSignal(
                name="leadership_change",
                summary=(
                    f"Leadership signal: {(leadership_record or {}).get('role', 'engineering leadership')} "
                    f"change about {leadership_days_ago} days ago."
                ),
                confidence=leadership_confidence,
                evidence=self._build_evidence(
                    "leadership_snapshot" if leadership_record else "heuristic_fallback",
                    leadership_record.get("domain", seed_key) if leadership_record else seed_key,
                    "Matched leadership-change snapshot."
                    if leadership_record
                    else "Fallback estimate derived from the input seed.",
                ),
            ),
        ]

        if layoffs_record or employee_estimate >= 180:
            hiring_signals.append(
                HiringSignal(
                    name="layoff_signal",
                    summary=(
                        f"Layoff signal: about {layoff_pct}% reduction roughly {layoff_days_ago} days ago."
                    ),
                    confidence=layoff_confidence,
                    evidence=self._build_evidence(
                        "layoffs_snapshot" if layoffs_record else "heuristic_fallback",
                        layoffs_record.get("domain", seed_key) if layoffs_record else seed_key,
                        "Matched layoffs snapshot."
                        if layoffs_record
                        else "Fallback estimate derived from the input seed.",
                    ),
                )
            )

        do_not_claim = [
            "Do not promise staffing capacity without bench confirmation.",
        ]
        if primary_segment == "abstain":
            do_not_claim.append("Do not use a segment-specific pitch; ask one exploratory question instead.")
        if not company_record:
            do_not_claim.append("Do not present funding details as verified until a company snapshot match exists.")
        if not jobs_record:
            do_not_claim.append("Do not claim aggressive hiring unless job-post evidence is matched.")
        if ai_maturity_score < 2:
            do_not_claim.append("Do not pitch a specialized AI capability gap as if it is confirmed.")
        if not layoffs_record:
            do_not_claim.append("Do not assert restructuring pressure directly without layoff evidence.")

        brief_mode = "snapshot-backed" if source_hits >= 2 else "hybrid"
        required_stacks = self._infer_required_stacks(tokens, ai_roles, sector)
        bench_capacity = self._load_bench_capacity()
        available_capacity = {
            stack: bench_capacity.get(stack, 0)
            for stack in required_stacks
        }
        bench_sufficient = all(count > 0 for count in available_capacity.values())
        if not bench_sufficient:
            do_not_claim.append("Do not offer a capability whose current bench count is zero.")
        bench_match = BenchMatch(
            required_stacks=required_stacks,
            available_capacity=available_capacity,
            sufficient=bench_sufficient,
            recommendation=(
                "Bench match is sufficient for a scoped discovery conversation; quote capacity as available, not committed."
                if bench_sufficient
                else "Route staffing-specific questions to a human because at least one required stack has no visible capacity."
            ),
        )

        hiring_signal_brief = HiringSignalBrief(
            summary=(
                f"{brief_mode.title()} brief for {intake.company_name}: {sector} profile, about "
                f"{employee_estimate} employees, likely segment '{segment_label}'. "
                f"Matched {source_hits} source records across the current local enrichment snapshots."
            ),
            primary_segment=segment_label,
            segment_confidence=segment_confidence,
            recommended_pitch_angle=(
                "Lead with the strongest matched public signal first, then qualify gently where signals are still partial."
            ),
            ai_maturity_score=ai_maturity_score,
            ai_maturity_justification=ai_justification,
            bench_match=bench_match,
            confidence_by_signal=confidence_by_signal,
            signals=hiring_signals,
            do_not_claim=do_not_claim,
        )

        peer_candidates = []
        snapshot_records = crunchbase_connector._load_records()
        for record in snapshot_records:
            if record.get("company_name") != intake.company_name and record.get("sector") == sector:
                peer_candidates.append(record["company_name"])
        peer_companies = peer_candidates[:4] or self.PEER_COMPANIES[sector]
        missing_practices = [
            "Publicly visible engineering-hiring specificity",
            "Clear AI or data-platform signaling",
        ]
        if ai_maturity_score >= 2:
            missing_practices = [
                "Sharable proof-points tied to specialized engineering execution",
                "More explicit public signal around delivery capability differentiation",
            ]

        competitor_gap_brief = CompetitorGapBrief(
            peer_group_definition=(
                f"Peer set drawn from the local {sector} company snapshot for similarly staged companies."
            ),
            peer_companies=peer_companies,
            top_quartile_practices=[
                "Signals delivery priorities through public hiring and engineering messaging.",
                "Shows stronger evidence of platform or AI execution maturity.",
                "Makes capability focus legible enough for a warm research-led outreach angle.",
            ],
            prospect_missing_practices=missing_practices,
            safe_gap_framing=(
                "Use the gap as a hypothesis about what peers make legible in public, not as a judgment that the prospect is behind."
            ),
            confidence=min(0.86, round((jobs_confidence + ai_confidence) / 2, 2)),
        )

        return prospect, hiring_signal_brief, competitor_gap_brief


enrichment_service = EnrichmentService()
