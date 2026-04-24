from agent.enrichment.ai_maturity import collect_ai_maturity_inputs, score_ai_maturity
from agent.enrichment.competitor_gap import (
    _build_company_ai_assessment,
    build_competitor_gap_brief,
)
from agent.enrichment.connectors import crunchbase_connector, job_posts_connector, leadership_connector


def _score_target() -> object:
    inputs = collect_ai_maturity_inputs(
        company_name="TargetCo",
        company_domain="targetco.example",
        job_examples=["Backend Engineer"],
        ai_roles=0,
        open_engineering_roles=4,
        leadership_role=None,
        leadership_person=None,
        github_activity_text=None,
        executive_commentary_text=None,
        modern_stack_text=None,
        strategic_communications_text=None,
    )
    return score_ai_maturity(inputs)


def test_competitor_gap_selects_five_to_ten_top_quartile_peers_and_attaches_evidence(monkeypatch) -> None:
    records = [
        {
            "company_name": "TargetCo",
            "domain": "targetco.example",
            "sector": "fintech",
            "employee_count": 100,
            "funding_musd": 12,
        }
    ]
    job_lookup = {
        "targetco.example": {
            "company_name": "TargetCo",
            "domain": "targetco.example",
            "open_engineering_roles": 4,
            "ai_roles": 0,
            "growth_delta_60d_pct": 0,
            "examples": ["Backend Engineer"],
        }
    }
    leadership_lookup = {}

    for index in range(1, 13):
        domain = f"peer{index}.example"
        records.append(
            {
                "company_name": f"Peer {index}",
                "domain": domain,
                "sector": "fintech",
                "employee_count": 80 + index * 5,
                "funding_musd": 15 + index,
                "github_activity": "GitHub repos show active OSS commits",
                "executive_commentary": "The CEO described an AI strategy and automation roadmap",
                "modern_stack": "dbt, Snowflake, MLflow",
                "strategic_communications": "AI roadmap and platform modernization",
            }
        )
        job_lookup[domain] = {
            "company_name": f"Peer {index}",
            "domain": domain,
            "open_engineering_roles": 6 + index,
            "ai_roles": 2 if index % 2 else 1,
            "growth_delta_60d_pct": 20 + index,
            "examples": [
                "Applied Scientist",
                "Data Platform Engineer",
                "Infrastructure Engineer",
            ],
        }
        leadership_lookup[domain] = {
            "company_name": f"Peer {index}",
            "domain": domain,
            "role": "Head of AI" if index % 3 else "VP Machine Learning",
            "person": f"Leader {index}",
        }

    monkeypatch.setattr(crunchbase_connector, "_load_records", lambda: records)
    monkeypatch.setattr(
        job_posts_connector,
        "lookup",
        lambda company_name, company_domain: job_lookup.get(company_domain),
    )
    monkeypatch.setattr(
        leadership_connector,
        "lookup",
        lambda company_name, company_domain: leadership_lookup.get(company_domain),
    )

    brief = build_competitor_gap_brief(
        company_name="TargetCo",
        company_domain="targetco.example",
        sector="fintech",
        target_employee_count=100,
        target_ai_assessment=_score_target(),
    )

    assert 5 <= len(brief.peer_companies) <= 10
    assert brief.top_quartile_companies == brief.peer_companies
    assert len(brief.comparables) == len(brief.peer_companies)
    assert brief.sector_distribution is not None
    assert brief.sector_distribution.total_companies == 13
    assert 2 <= len(brief.gap_practices) <= 3
    assert all(practice.evidence for practice in brief.gap_practices)
    assert all(
        evidence.source_type in {"named_role", "named_tool", "named_public_statement"}
        for practice in brief.gap_practices
        for evidence in practice.evidence
    )
    assert "top-quartile peer set" in (brief.selection_criteria or "").lower()

    top_company = next(record for record in records if record["company_name"] == "Peer 12")
    expected_assessment = _build_company_ai_assessment(
        top_company,
        job_lookup[top_company["domain"]],
        leadership_lookup[top_company["domain"]],
    )
    assert brief.comparables[0].company_name == "Peer 12"
    assert brief.comparables[0].ai_maturity_score == expected_assessment.score


def test_competitor_gap_marks_sparse_sector_when_fewer_than_five_viable_peers(monkeypatch) -> None:
    records = [
        {
            "company_name": "TargetCo",
            "domain": "targetco.example",
            "sector": "healthtech",
            "employee_count": 90,
            "funding_musd": 10,
        },
        {
            "company_name": "Sparse Peer 1",
            "domain": "sparse1.example",
            "sector": "healthtech",
            "employee_count": 95,
            "funding_musd": 11,
            "executive_commentary": "AI strategy and automation roadmap",
        },
        {
            "company_name": "Sparse Peer 2",
            "domain": "sparse2.example",
            "sector": "healthtech",
            "employee_count": 120,
            "funding_musd": 13,
            "modern_stack": "Databricks and dbt",
        },
        {
            "company_name": "Sparse Peer 3",
            "domain": "sparse3.example",
            "sector": "healthtech",
            "employee_count": 70,
            "funding_musd": 9,
            "github_activity": "Open source repository commits are visible",
        },
    ]
    job_lookup = {
        "sparse1.example": {
            "company_name": "Sparse Peer 1",
            "domain": "sparse1.example",
            "open_engineering_roles": 3,
            "ai_roles": 1,
            "growth_delta_60d_pct": 10,
            "examples": ["Machine Learning Engineer"],
        }
    }

    monkeypatch.setattr(crunchbase_connector, "_load_records", lambda: records)
    monkeypatch.setattr(
        job_posts_connector,
        "lookup",
        lambda company_name, company_domain: job_lookup.get(company_domain),
    )
    monkeypatch.setattr(leadership_connector, "lookup", lambda company_name, company_domain: None)

    brief = build_competitor_gap_brief(
        company_name="TargetCo",
        company_domain="targetco.example",
        sector="healthtech",
        target_employee_count=90,
        target_ai_assessment=_score_target(),
    )

    assert brief.sparse_sector is True
    assert brief.sparse_sector_note is not None
    assert len(brief.peer_companies) == 3
    assert brief.top_quartile_companies == brief.peer_companies
