from collections import defaultdict
from math import ceil

from agent.enrichment.ai_maturity import collect_ai_maturity_inputs, score_ai_maturity
from agent.enrichment.common import build_source_ref
from agent.enrichment.connectors import crunchbase_connector, job_posts_connector, leadership_connector
from agent.schemas.briefs import (
    AIMaturityAssessment,
    CompetitorComparable,
    CompetitorGapBrief,
    GapPractice,
    SectorDistributionPosition,
)

# Selection criteria for "top quartile" comparables:
# 1. Same sector as the prospect.
# 2. Public-signal viability: at least one usable public signal across jobs, leadership,
#    executive commentary, GitHub activity, stack references, or strategy messaging.
# 3. Comparable operating stage: employee count within roughly 0.4x to 3.0x the target where possible.
# 4. Ranked by a shared score that combines AI maturity score, AI confidence, and hiring velocity.
# 5. Select a top-quartile peer set capped to 5 to 10 firms when enough viable competitors exist;
#    if fewer than 5 exist, return the sparse set explicitly and mark the brief as sparse-sector constrained.


PRACTICE_TITLES = {
    "specialized_ai_hiring": "Specialized AI hiring",
    "platform_or_data_hiring": "Platform or data hiring focus",
    "named_ai_leadership": "Named AI or ML leadership",
    "public_ai_strategy": "Public AI strategy messaging",
    "modern_ml_stack": "Modern data or ML stack signaling",
}


def _has_public_signal(company_record: dict, jobs_record: dict | None, leadership_record: dict | None) -> bool:
    return any(
        [
            jobs_record,
            leadership_record,
            company_record.get("github_activity"),
            company_record.get("executive_commentary"),
            company_record.get("modern_stack"),
            company_record.get("strategic_communications"),
        ]
    )


def _extract_named_roles(job_examples: list[str], keywords: set[str]) -> list[str]:
    return [
        example
        for example in job_examples
        if any(keyword in example.lower() for keyword in keywords)
    ]


def _extract_named_tools(*texts: str | None) -> list[str]:
    tools = {
        "dbt": "dbt",
        "snowflake": "Snowflake",
        "databricks": "Databricks",
        "mlflow": "MLflow",
        "kubernetes": "Kubernetes",
        "terraform": "Terraform",
        "vector": "Vector search",
        "feature store": "Feature store",
    }
    haystack = " ".join(text or "" for text in texts).lower()
    found = [display for token, display in tools.items() if token in haystack]
    return found


def _build_company_ai_assessment(company_record: dict, jobs_record: dict | None, leadership_record: dict | None) -> AIMaturityAssessment:
    job_examples = (jobs_record or {}).get("examples") or []
    ai_roles = int((jobs_record or {}).get("ai_roles") or 0)
    open_engineering_roles = int((jobs_record or {}).get("open_engineering_roles") or 0)
    company_tokens = {
        token
        for token in ((company_record.get("company_name") or "") + " " + (company_record.get("domain") or "")).lower().split()
        if token
    }
    inputs = collect_ai_maturity_inputs(
        company_name=company_record.get("company_name") or "Unknown",
        company_domain=company_record.get("domain"),
        job_examples=job_examples,
        ai_roles=ai_roles,
        open_engineering_roles=open_engineering_roles,
        leadership_role=(leadership_record or {}).get("role"),
        leadership_person=(leadership_record or {}).get("person"),
        company_tokens=company_tokens,
        github_activity_text=company_record.get("github_activity"),
        executive_commentary_text=company_record.get("executive_commentary"),
        modern_stack_text=company_record.get("modern_stack"),
        strategic_communications_text=company_record.get("strategic_communications"),
    )
    return score_ai_maturity(inputs)


def _build_company_practices(company_record: dict, jobs_record: dict | None, leadership_record: dict | None) -> list[GapPractice]:
    practices: list[GapPractice] = []
    company_name = company_record.get("company_name") or "Unknown company"
    domain = company_record.get("domain") or company_name
    job_examples = (jobs_record or {}).get("examples") or []
    ai_roles = _extract_named_roles(job_examples, {"ai", "ml", "llm", "scientist", "applied"})
    platform_roles = _extract_named_roles(job_examples, {"platform", "data", "backend", "security", "infra"})
    named_tools = _extract_named_tools(
        company_record.get("modern_stack"),
        company_record.get("strategic_communications"),
        " ".join(job_examples),
    )
    strategy_text = company_record.get("executive_commentary") or company_record.get("strategic_communications")

    if ai_roles:
        practices.append(
            GapPractice(
                practice_name=PRACTICE_TITLES["specialized_ai_hiring"],
                description="Peers publicly advertise AI-adjacent roles rather than only generalist engineering hires.",
                evidence=[
                    build_source_ref(
                        source_name="public_job_pages",
                        reference=domain,
                        note=f"Named role observed: {role}",
                        source_type="named_role",
                    )
                    for role in ai_roles[:2]
                ],
            )
        )

    if platform_roles:
        practices.append(
            GapPractice(
                practice_name=PRACTICE_TITLES["platform_or_data_hiring"],
                description="Peers make platform, security, or data execution priorities legible through named roles.",
                evidence=[
                    build_source_ref(
                        source_name="public_job_pages",
                        reference=domain,
                        note=f"Named role observed: {role}",
                        source_type="named_role",
                    )
                    for role in platform_roles[:2]
                ],
            )
        )

    if leadership_record and leadership_record.get("role"):
        practices.append(
            GapPractice(
                practice_name=PRACTICE_TITLES["named_ai_leadership"],
                description="Peers publicly show named technical leadership that anchors their capability story.",
                evidence=[
                    build_source_ref(
                        source_name="leadership_snapshot",
                        reference=domain,
                        note=(
                            f"Leadership role observed: {leadership_record.get('role')} "
                            f"({leadership_record.get('person') or 'unnamed leader'})"
                        ),
                        source_type="named_role",
                    )
                ],
            )
        )

    if named_tools:
        practices.append(
            GapPractice(
                practice_name=PRACTICE_TITLES["modern_ml_stack"],
                description="Peers reference modern data or ML stack choices in public materials.",
                evidence=[
                    build_source_ref(
                        source_name="public_stack_signal",
                        reference=domain,
                        note=f"Named tool observed: {tool}",
                        source_type="named_tool",
                    )
                    for tool in named_tools[:2]
                ],
            )
        )

    if strategy_text:
        practices.append(
            GapPractice(
                practice_name=PRACTICE_TITLES["public_ai_strategy"],
                description="Peers publish strategic messaging that makes AI or platform priorities legible.",
                evidence=[
                    build_source_ref(
                        source_name="executive_commentary",
                        reference=domain,
                        note=f"Named public statement: {strategy_text}",
                        source_type="named_public_statement",
                    )
                ],
            )
        )

    return practices[:3]


def compute_distribution_position(target_score: int, competitor_scores: list[int]) -> SectorDistributionPosition:
    all_scores = sorted([target_score, *competitor_scores], reverse=True)
    rank = all_scores.index(target_score) + 1
    total = len(all_scores)
    below_or_equal = sum(1 for score in all_scores if score <= target_score)
    percentile = round((below_or_equal / total) * 100, 2) if total else 0.0
    quartile = (
        "top_quartile"
        if rank <= max(1, ceil(total * 0.25))
        else "upper_middle"
        if rank <= max(1, ceil(total * 0.5))
        else "lower_half"
    )
    top_cutoff_index = max(0, ceil(total * 0.25) - 1)
    cutoff_score = all_scores[top_cutoff_index] if all_scores else target_score
    return SectorDistributionPosition(
        rank=rank,
        total_companies=total,
        percentile=percentile,
        quartile=quartile,
        target_score=target_score,
        top_quartile_cutoff_score=cutoff_score,
    )


def build_competitor_gap_brief(
    *,
    company_name: str,
    company_domain: str | None,
    sector: str,
    target_employee_count: int,
    target_ai_assessment: AIMaturityAssessment,
) -> CompetitorGapBrief:
    snapshot_records = crunchbase_connector._load_records()
    candidate_records = [
        record
        for record in snapshot_records
        if record.get("company_name") != company_name and record.get("sector") == sector
    ]

    viable: list[tuple[dict, CompetitorComparable, list[GapPractice]]] = []
    for candidate in candidate_records:
        employee_count = int(candidate.get("employee_count") or 0)
        if target_employee_count and employee_count:
            ratio = employee_count / max(target_employee_count, 1)
            if ratio < 0.4 or ratio > 3.0:
                continue
        jobs_record = job_posts_connector.lookup(candidate["company_name"], candidate.get("domain"))
        leadership_record = leadership_connector.lookup(candidate["company_name"], candidate.get("domain"))
        if not _has_public_signal(candidate, jobs_record, leadership_record):
            continue
        ai_assessment = _build_company_ai_assessment(candidate, jobs_record, leadership_record)
        rank_score = (
            ai_assessment.score * 100
            + round(ai_assessment.confidence * 10, 2)
            + int((jobs_record or {}).get("growth_delta_60d_pct") or 0)
        )
        comparable = CompetitorComparable(
            company_name=candidate["company_name"],
            company_domain=candidate.get("domain"),
            sector=sector,
            rank_score=rank_score,
            ai_maturity_score=ai_assessment.score,
            ai_maturity_confidence=ai_assessment.confidence,
            employee_count=employee_count,
            funding_musd=int(candidate.get("funding_musd") or 0),
        )
        viable.append((candidate, comparable, _build_company_practices(candidate, jobs_record, leadership_record)))

    viable.sort(key=lambda item: item[1].rank_score, reverse=True)
    sparse_sector = len(viable) < 5
    selected_count = (
        len(viable)
        if sparse_sector
        else min(10, max(5, ceil(len(viable) * 0.25)))
    )
    top_quartile = viable[:selected_count]

    target_practices = _build_company_practices(
        crunchbase_connector.lookup(company_name, company_domain)
        or {"company_name": company_name, "domain": company_domain, "sector": sector},
        job_posts_connector.lookup(company_name, company_domain),
        leadership_connector.lookup(company_name, company_domain),
    )
    target_practice_names = {practice.practice_name for practice in target_practices}

    aggregated: dict[str, GapPractice] = {}
    counts: defaultdict[str, int] = defaultdict(int)
    for _, _, practices in top_quartile:
        for practice in practices:
            counts[practice.practice_name] += 1
            if practice.practice_name not in aggregated:
                aggregated[practice.practice_name] = GapPractice.model_validate(practice.model_dump(mode="json"))
            else:
                aggregated[practice.practice_name].evidence.extend(practice.evidence)

    gap_practices: list[GapPractice] = []
    for practice_name, practice in aggregated.items():
        if practice_name in target_practice_names:
            continue
        practice.observed_by_peer_count = counts[practice_name]
        gap_practices.append(practice)
    gap_practices.sort(key=lambda item: (-item.observed_by_peer_count, -len(item.evidence), item.practice_name))
    gap_practices = gap_practices[:3]
    if len(gap_practices) < 2:
        fallback_practices = sorted(
            aggregated.values(),
            key=lambda item: (-counts[item.practice_name], -len(item.evidence), item.practice_name),
        )
        for practice in fallback_practices:
            if any(existing.practice_name == practice.practice_name for existing in gap_practices):
                continue
            practice.observed_by_peer_count = counts[practice.practice_name]
            gap_practices.append(practice)
            if len(gap_practices) == 3:
                break

    competitor_scores = [item[1].ai_maturity_score for item in viable]
    sector_distribution = compute_distribution_position(
        target_ai_assessment.score,
        competitor_scores,
    )
    top_quartile_companies = [item[1].company_name for item in top_quartile]
    comparables = [item[1] for item in top_quartile]
    top_quartile_practices = [practice.practice_name for practice in gap_practices]
    prospect_missing_practices = [practice.description for practice in gap_practices]

    return CompetitorGapBrief(
        selection_criteria=(
            "Same-sector candidates with public-signal viability are ranked by shared AI maturity scoring, "
            "AI confidence, and job-post velocity. The top-quartile peer set is capped to 5 to 10 firms when "
            "enough viable competitors exist, with an explicit sparse-sector fallback below that threshold."
        ),
        peer_group_definition=(
            f"Peer set drawn from the local {sector} company snapshot, filtered for same-sector comparables and ranked by shared AI maturity plus hiring-velocity signals."
        ),
        peer_companies=[item[1].company_name for item in top_quartile],
        top_quartile_companies=top_quartile_companies,
        comparables=comparables,
        sector_distribution=sector_distribution,
        top_quartile_practices=top_quartile_practices,
        gap_practices=gap_practices,
        prospect_missing_practices=prospect_missing_practices,
        sparse_sector=sparse_sector,
        sparse_sector_note=(
            f"Only {len(viable)} viable same-sector competitors were available in the current public-signal snapshot."
            if sparse_sector
            else None
        ),
        safe_gap_framing=(
            "Use the gap as a research finding about what top-quartile peers make legible in public, not as a judgment that the prospect is behind."
        ),
        confidence=min(
            0.9,
            round(
                (
                    target_ai_assessment.confidence
                    + (sum(item[1].ai_maturity_confidence for item in top_quartile) / max(len(top_quartile), 1))
                )
                / 2,
                2,
            ),
        ),
    )
