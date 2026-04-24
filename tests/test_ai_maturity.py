from agent.enrichment.ai_maturity import (
    HIGH_WEIGHT,
    LOW_WEIGHT,
    MEDIUM_WEIGHT,
    collect_ai_maturity_inputs,
    score_ai_maturity,
)
from agent.enrichment.service import enrichment_service
from agent.schemas.prospect import LeadIntakeRequest


def test_ai_maturity_collects_all_six_input_categories_with_tier_weights() -> None:
    inputs = collect_ai_maturity_inputs(
        company_name="ClearMint",
        company_domain="clearmint.io",
        job_examples=["LLM Engineer", "Data Platform Engineer"],
        ai_roles=2,
        open_engineering_roles=8,
        leadership_role="Head of AI",
        leadership_person="Amara Cole",
        github_activity_text="GitHub repos show active OSS commits",
        executive_commentary_text="The CEO described an AI strategy and automation roadmap",
        modern_stack_text="dbt, Snowflake, MLflow",
        strategic_communications_text="AI roadmap and platform modernization",
    )
    assert len(inputs) == 6
    assert [item.weight for item in inputs] == [
        HIGH_WEIGHT,
        HIGH_WEIGHT,
        MEDIUM_WEIGHT,
        MEDIUM_WEIGHT,
        LOW_WEIGHT,
        LOW_WEIGHT,
    ]


def test_ai_maturity_scoring_returns_score_confidence_and_per_signal_justification() -> None:
    inputs = collect_ai_maturity_inputs(
        company_name="ClearMint",
        company_domain="clearmint.io",
        job_examples=["LLM Engineer", "Applied Scientist"],
        ai_roles=3,
        open_engineering_roles=12,
        leadership_role="Chief AI Officer",
        leadership_person="Amara Cole",
        github_activity_text="GitHub repository activity is public",
        executive_commentary_text="Executive AI strategy discussed publicly",
        modern_stack_text="Databricks and MLflow",
        strategic_communications_text="AI roadmap and platform strategy",
    )
    assessment = score_ai_maturity(inputs)
    assert 0 <= assessment.score <= 3
    assert 0.0 <= assessment.confidence <= 1.0
    assert assessment.score == 3
    assert all(item.justification for item in assessment.inputs)


def test_ai_maturity_silent_company_returns_zero_and_acknowledges_absence_not_proof() -> None:
    inputs = collect_ai_maturity_inputs(
        company_name="Unknown Co",
        company_domain="unknown.example",
        job_examples=[],
        ai_roles=0,
        open_engineering_roles=0,
        leadership_role=None,
        leadership_person=None,
        github_activity_text=None,
        executive_commentary_text=None,
        modern_stack_text=None,
        strategic_communications_text=None,
    )
    assessment = score_ai_maturity(inputs)
    assert assessment.score == 0
    assert assessment.silent_company is True
    assert "not proof of absence" in assessment.summary.lower()


def test_ai_maturity_rationale_is_persisted_in_hiring_signal_brief() -> None:
    _, brief, _ = enrichment_service.enrich(
        LeadIntakeRequest(company_name="ClearMint", company_domain="clearmint.io")
    )
    assert brief.ai_maturity_assessment is not None
    assert brief.ai_maturity_assessment.summary == brief.ai_maturity_justification
    assert brief.ai_maturity_assessment.inputs
