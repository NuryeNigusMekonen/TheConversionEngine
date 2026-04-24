from datetime import datetime, timedelta, timezone

from agent.enrichment.crunchbase_odm import build_crunchbase_funding_signal
from agent.enrichment.job_post_scraper import (
    build_job_post_signal,
    compute_60_day_job_velocity,
    is_public_job_page,
)
from agent.enrichment.layoffs_fyi_signal import build_layoff_signal
from agent.enrichment.leadership_changes import build_leadership_change_signal
from agent.enrichment.service import enrichment_service
from agent.schemas.prospect import LeadIntakeRequest


def test_hiring_signal_brief_has_four_signals_with_timestamps_and_sources() -> None:
    _, brief, _ = enrichment_service.enrich(
        LeadIntakeRequest(company_name="ClearMint", company_domain="clearmint.io")
    )
    assert len(brief.signals) == 4
    assert brief.generated_at is not None
    for signal in brief.signals:
        assert signal.collected_at is not None
        assert signal.source_attribution
        assert 0.0 <= signal.confidence <= 1.0


def test_unknown_company_exposes_edge_cases_in_source_backed_signals() -> None:
    funding = build_crunchbase_funding_signal("Unknown Co", "unknown.example")
    jobs = build_job_post_signal("Unknown Co", "unknown.example")
    layoffs = build_layoff_signal("Unknown Co", "unknown.example")
    leadership = build_leadership_change_signal("Unknown Co", "unknown.example")

    assert funding["edge_case"] == "missing_crunchbase_record"
    assert jobs["edge_case"] == "missing_job_post_record"
    assert layoffs["edge_case"] == "no_layoff_history"
    assert leadership["edge_case"] == "no_leadership_change_in_window"


def test_job_velocity_is_computed_over_60_day_window() -> None:
    now = datetime.now(timezone.utc).replace(microsecond=0)
    postings = [
        {"published_at": (now - timedelta(days=5)).isoformat()},
        {"published_at": (now - timedelta(days=20)).isoformat()},
        {"published_at": (now - timedelta(days=40)).isoformat()},
        {"published_at": (now - timedelta(days=80)).isoformat()},
    ]
    velocity = compute_60_day_job_velocity(postings, as_of=now)
    assert velocity["current_window_count"] == 3
    assert velocity["previous_window_count"] == 1
    assert velocity["growth_delta_60d_pct"] == 200


def test_public_job_page_filter_only_allows_supported_public_hosts() -> None:
    assert is_public_job_page("https://www.builtin.com/company/acme/jobs") is True
    assert is_public_job_page("https://wellfound.com/company/acme/jobs") is True
    assert is_public_job_page("https://www.linkedin.com/company/acme/jobs") is True
    assert is_public_job_page("https://example.com/private/jobs") is False
