import re

from agent.schemas.briefs import AIMaturityAssessment, AIMaturitySignalInput

HIGH_WEIGHT = 4
MEDIUM_WEIGHT = 2
LOW_WEIGHT = 1

AI_ROLE_KEYWORDS = {
    "ai",
    "ml",
    "machine learning",
    "llm",
    "genai",
    "data scientist",
    "applied scientist",
    "inference",
}
AI_LEADERSHIP_KEYWORDS = {
    "ai",
    "ml",
    "machine learning",
    "chief ai officer",
    "head of ai",
    "vp ai",
    "director of ai",
}
GITHUB_ACTIVITY_KEYWORDS = {
    "github",
    "oss",
    "open source",
    "repo",
    "repository",
    "commit",
    "star",
}
EXECUTIVE_COMMENTARY_KEYWORDS = {
    "ai strategy",
    "llm",
    "automation",
    "agentic",
    "machine learning",
    "model",
}
MODERN_STACK_KEYWORDS = {
    "dbt",
    "snowflake",
    "databricks",
    "mlflow",
    "vector",
    "feature store",
    "airflow",
    "kubernetes",
    "terraform",
}
STRATEGIC_COMMUNICATION_KEYWORDS = {
    "ai roadmap",
    "platform",
    "data strategy",
    "personalization",
    "copilot",
    "intelligence",
}


def _tokenize(*parts: str | None) -> set[str]:
    text = " ".join(part or "" for part in parts).lower()
    return set(re.findall(r"[a-z0-9\.\+\-]+", text))


def collect_ai_maturity_inputs(
    *,
    company_name: str,
    company_domain: str | None,
    job_examples: list[str],
    ai_roles: int,
    open_engineering_roles: int,
    leadership_role: str | None,
    leadership_person: str | None,
    company_tokens: set[str] | None = None,
    github_activity_text: str | None = None,
    executive_commentary_text: str | None = None,
    modern_stack_text: str | None = None,
    strategic_communications_text: str | None = None,
) -> list[AIMaturitySignalInput]:
    company_token_set = set(company_tokens or set())
    job_token_set = _tokenize(*job_examples)
    leadership_text = " ".join(part for part in [leadership_role, leadership_person] if part)
    leadership_tokens = _tokenize(leadership_text)
    github_tokens = _tokenize(github_activity_text, company_name, company_domain)
    exec_tokens = _tokenize(executive_commentary_text, *job_examples, company_name)
    stack_tokens = _tokenize(modern_stack_text, *job_examples, company_domain)
    strategy_tokens = _tokenize(strategic_communications_text, company_name, company_domain)

    ai_adjacent_roles_observed = ai_roles > 0 or any(
        any(keyword in example.lower() for keyword in AI_ROLE_KEYWORDS)
        for example in job_examples
    )
    named_ai_leadership_observed = any(keyword in leadership_text.lower() for keyword in AI_LEADERSHIP_KEYWORDS)
    github_activity_observed = bool(github_tokens & GITHUB_ACTIVITY_KEYWORDS)
    executive_commentary_observed = bool(exec_tokens & EXECUTIVE_COMMENTARY_KEYWORDS)
    modern_stack_observed = bool(stack_tokens & MODERN_STACK_KEYWORDS)
    strategic_comms_observed = bool(strategy_tokens & STRATEGIC_COMMUNICATION_KEYWORDS or company_token_set & {"ai", "data", "platform"})

    return [
        AIMaturitySignalInput(
            name="ai_adjacent_open_roles",
            tier="high",
            weight=HIGH_WEIGHT,
            observed=ai_adjacent_roles_observed,
            value=f"{ai_roles} AI-adjacent roles across {open_engineering_roles} engineering openings",
            justification=(
                "AI-adjacent open roles are visible in public job postings."
                if ai_adjacent_roles_observed
                else "No AI-adjacent public roles were found."
            ),
        ),
        AIMaturitySignalInput(
            name="named_ai_ml_leadership",
            tier="high",
            weight=HIGH_WEIGHT,
            observed=named_ai_leadership_observed,
            value=leadership_text or "No named AI/ML leadership found",
            justification=(
                "Named AI or ML leadership appears in public leadership records."
                if named_ai_leadership_observed
                else "No named AI or ML leadership was found in public leadership records."
            ),
        ),
        AIMaturitySignalInput(
            name="public_github_org_activity",
            tier="medium",
            weight=MEDIUM_WEIGHT,
            observed=github_activity_observed,
            value=github_activity_text or "No GitHub organization activity found",
            justification=(
                "Public GitHub organization activity suggests active technical execution."
                if github_activity_observed
                else "No public GitHub organization activity was found."
            ),
        ),
        AIMaturitySignalInput(
            name="executive_commentary",
            tier="medium",
            weight=MEDIUM_WEIGHT,
            observed=executive_commentary_observed,
            value=executive_commentary_text or "No executive AI commentary found",
            justification=(
                "Executive commentary references AI, automation, or model strategy."
                if executive_commentary_observed
                else "No executive commentary about AI strategy was found."
            ),
        ),
        AIMaturitySignalInput(
            name="modern_data_or_ml_stack",
            tier="low",
            weight=LOW_WEIGHT,
            observed=modern_stack_observed,
            value=modern_stack_text or ", ".join(job_examples[:3]) or "No modern data or ML stack references found",
            justification=(
                "Public materials reference a modern data or ML stack."
                if modern_stack_observed
                else "No explicit modern data or ML stack references were found."
            ),
        ),
        AIMaturitySignalInput(
            name="strategic_communications",
            tier="low",
            weight=LOW_WEIGHT,
            observed=strategic_comms_observed,
            value=strategic_communications_text or company_name,
            justification=(
                "Strategic communications imply AI, data, or platform priorities."
                if strategic_comms_observed
                else "No strategic communications signal about AI priorities was found."
            ),
        ),
    ]


def score_ai_maturity(inputs: list[AIMaturitySignalInput]) -> AIMaturityAssessment:
    observed_weight = sum(item.weight for item in inputs if item.observed)
    observed_high = sum(1 for item in inputs if item.tier == "high" and item.observed)
    observed_medium = sum(1 for item in inputs if item.tier == "medium" and item.observed)
    observed_low = sum(1 for item in inputs if item.tier == "low" and item.observed)
    silent_company = observed_weight == 0

    if silent_company:
        return AIMaturityAssessment(
            score=0,
            confidence=0.92,
            summary=(
                "No public AI maturity signal was found. This absence is not proof of absence; "
                "it only means the current public-source sweep is silent."
            ),
            silent_company=True,
            inputs=inputs,
        )

    if observed_high >= 2 or observed_weight >= 10:
        score = 3
    elif observed_high >= 1 or observed_weight >= 6:
        score = 2
    elif observed_medium >= 1 or observed_low >= 2 or observed_weight >= 2:
        score = 1
    else:
        score = 0

    if score == 3:
        confidence = 0.88 if observed_high >= 2 else 0.76
    elif score == 2:
        confidence = 0.81 if observed_high >= 1 else 0.63
    elif score == 1:
        confidence = 0.69 if observed_medium >= 1 else 0.52
    else:
        confidence = 0.57

    summary_parts = [
        item.justification
        for item in inputs
        if item.observed
    ]
    if not summary_parts:
        summary_parts.append(
            "Only weak or indirect public evidence was found, so the score stays conservative."
        )

    return AIMaturityAssessment(
        score=score,
        confidence=confidence,
        summary=" ".join(summary_parts),
        silent_company=False,
        inputs=inputs,
    )
