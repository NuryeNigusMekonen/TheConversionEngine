"""
Tenacious seed material loader.

Reads docs/tenacious_sales_data/seed/ at import time and exposes typed
accessors. Parsing is simple and deterministic — no LLM involved.

All seed materials are loaded once at module level via `seed_materials`.
Every public method returns a safe default if the backing file is absent.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from agent.config import settings


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class IcpPitchLanguage:
    high_readiness: str  # AI maturity score >= 2
    low_readiness: str   # AI maturity score 0–1


@dataclass(frozen=True)
class StyleConstraints:
    max_cold_body_words: int = 120
    max_subject_chars: int = 60
    banned_subject_prefixes: frozenset[str] = field(
        default_factory=lambda: frozenset({"quick", "just", "hey", "following up", "circling back"})
    )
    banned_vendor_cliches: frozenset[str] = field(
        default_factory=lambda: frozenset({
            "top talent", "world-class", "a-players", "rockstar", "ninja",
            "cost savings of", "guaranteed savings", "we can definitely",
            "we're not like other", "aggressive hiring",
        })
    )


@dataclass(frozen=True)
class CaseStudy:
    name: str           # internal label (e.g. "adtech")
    descriptor: str     # public-safe descriptor
    quotable: str       # verbatim text the agent may use
    segment_hint: str   # loosely matched segment key


@dataclass(frozen=True)
class PricingGuardrail:
    """Approved pricing language derived from pricing_sheet.md + transcript_05."""
    engagement_minimum: str
    extension_cadence: str
    quotable_talent_floor: str
    quotable_project_floor: str
    objection_price_too_high: str
    objection_small_poc: str
    not_quotable_note: str


@dataclass(frozen=True)
class ObjectionPatterns:
    """Agent-usable phrases extracted from discovery_transcripts/transcript_05."""
    offshore_concern: str
    capacity_proof: str
    price_comparison: str
    small_poc: str
    architecture_boundary: str


@dataclass(frozen=True)
class EmailSequenceStructure:
    """Structure rules extracted from email_sequences/cold.md."""
    # Subject prefix by segment key
    subject_prefix: dict[str, str]
    # Bottleneck sentences by segment key (grounded observations)
    bottleneck_by_segment: dict[str, str]
    max_email1_words: int = 120
    max_email2_words: int = 100
    max_email3_words: int = 70


# ---------------------------------------------------------------------------
# Parser helpers (private)
# ---------------------------------------------------------------------------


def _parse_icp_pitch_language(text: str) -> dict[str, IcpPitchLanguage]:
    """Extract pitch language for each segment from icp_definition.md."""
    # Segment header → internal key mapping
    segment_map = {
        "Segment 1": "recently_funded_startup",
        "Segment 2": "mid_market_restructuring",
        "Segment 3": "engineering_leadership_transition",
        "Segment 4": "specialized_capability_gap",
    }
    result: dict[str, IcpPitchLanguage] = {}
    current_segment: str | None = None
    in_pitch_section = False
    high_text: str | None = None
    low_text: str | None = None

    def _save(seg: str, hi: str | None, lo: str | None) -> None:
        if seg and (hi or lo):
            result[seg] = IcpPitchLanguage(
                high_readiness=hi or lo or "",
                low_readiness=lo or hi or "",
            )

    for line in text.splitlines():
        # Detect segment block header
        for seg_prefix, seg_key in segment_map.items():
            if line.startswith(f"## {seg_prefix} "):
                _save(current_segment or "", high_text, low_text)
                current_segment = seg_key
                in_pitch_section = False
                high_text = None
                low_text = None
                break

        # Detect pitch language sub-section
        if line.strip() == "### Pitch language":
            in_pitch_section = True
            continue

        # Any h3 closes the pitch section
        if line.startswith("### ") and line.strip() != "### Pitch language":
            in_pitch_section = False

        if not in_pitch_section or current_segment is None:
            continue

        # Segment 3 special case: no AI split
        if "AI-readiness score does **not**" in line:
            high_text = (
                "reassess your vendor mix — the first 90 days as CTO are "
                "typically when offshore delivery gets a fresh look"
            )
            low_text = high_text
            continue

        # Segment 4 special case: grounded in capability gap
        if "Always grounded in the specific capability gap" in line:
            high_text = (
                "fill the specific capability gap your public signal shows — "
                "grounded in what peer companies are already building"
            )
            low_text = high_text
            continue

        if "**High AI-readiness" in line:
            parts = line.split("**:", 1)
            if len(parts) > 1:
                high_text = parts[1].strip().strip('"')
        elif "**Low AI-readiness" in line:
            parts = line.split("**:", 1)
            if len(parts) > 1:
                low_text = parts[1].strip().strip('"')

    _save(current_segment or "", high_text, low_text)
    return result


def _parse_case_studies(text: str) -> list[CaseStudy]:
    """Extract quotable language from case_studies.md."""
    studies: list[CaseStudy] = []
    name_map = {
        "Case Study 1": ("adtech", "Global Advertising Technology Platform", "mid_market_restructuring"),
        "Case Study 2": ("loyalty", "North American Loyalty Platform", "specialized_capability_gap"),
        "Case Study 3": ("fitness", "Multi-Location Fitness Franchise", "specialized_capability_gap"),
    }
    current_name: str | None = None
    current_key: tuple[str, str, str] | None = None
    quotable: str | None = None

    for line in text.splitlines():
        for heading, meta in name_map.items():
            if f"## {heading}" in line:
                if current_key and quotable:
                    studies.append(
                        CaseStudy(
                            name=current_key[0],
                            descriptor=current_key[1],
                            quotable=quotable.strip(),
                            segment_hint=current_key[2],
                        )
                    )
                current_key = meta
                quotable = None
                break

        # Capture the blockquote line after "Quotable language for the agent:"
        if current_key and quotable is None and line.startswith("> "):
            quotable = line.lstrip("> ").strip()

    if current_key and quotable:
        studies.append(
            CaseStudy(
                name=current_key[0],
                descriptor=current_key[1],
                quotable=quotable.strip(),
                segment_hint=current_key[2],
            )
        )
    return studies


def _parse_objection_patterns(transcript_text: str) -> ObjectionPatterns:
    """Extract agent-usable phrases from transcript_05_objection_heavy.md."""
    # These are explicit in the "Agent-usable phrases" section.
    # We parse by looking for lines under that heading before "Agent-NOT-usable".
    usable: list[str] = []
    in_usable = False
    for line in transcript_text.splitlines():
        if "## Agent-usable phrases" in line:
            in_usable = True
            continue
        if "## Agent-NOT-usable phrases" in line:
            in_usable = False
        if in_usable and line.startswith("- "):
            phrase = line.lstrip("- ").strip().strip('"')
            usable.append(phrase)

    def _pick(idx: int, default: str) -> str:
        return usable[idx] if idx < len(usable) else default

    return ObjectionPatterns(
        # "We're not the cheapest offshore option..."
        offshore_concern=_pick(0, "We compete on reliability and retention, not hourly rate."),
        # "Any vendor who pitches you a percentage savings..."
        price_comparison=_pick(1, "Any vendor who pitches percentage savings without a scoping conversation is making up numbers."),
        # "We do not replace in-house architecture."
        capacity_proof=_pick(2, "We do not replace in-house architecture — we augment it."),
        # "The smallest real engagement we do..."
        small_poc=_pick(3, "The smallest real engagement we do is a fixed-scope project consulting contract."),
        architecture_boundary=_pick(4, "If after the technical walkthrough you decide we're not the right fit, tell us."),
    )


def _parse_pricing_guardrail(pricing_text: str, objections: ObjectionPatterns) -> PricingGuardrail:
    """Extract quotable pricing language from pricing_sheet.md."""
    return PricingGuardrail(
        engagement_minimum="1-month minimum for staff augmentation engagements.",
        extension_cadence="Extension in 2-week blocks after the first month, at your option.",
        quotable_talent_floor=(
            "Monthly rates start from our public junior floor and scale by seniority. "
            "Coverage includes engineer salary, project management, insurance, and standard tooling — "
            "cloud and SaaS costs are billed directly to you at actuals."
        ),
        quotable_project_floor=(
            "Starter fixed-scope projects begin at our public project floor. "
            "Deliverable and timeline are agreed upfront; milestone payments are tied to phase sign-off."
        ),
        objection_price_too_high=objections.offshore_concern,
        objection_small_poc=objections.small_poc,
        not_quotable_note=(
            "Specific total-contract values for multi-phase engagements, discounts, "
            "volume pricing, and multi-year commitments require a scoping conversation "
            "with the delivery lead."
        ),
    )


def _build_email_sequence_structure() -> EmailSequenceStructure:
    """Return structure rules derived from email_sequences/cold.md."""
    return EmailSequenceStructure(
        subject_prefix={
            "recently_funded_startup": "Context",
            "mid_market_restructuring": "Note on",
            "engineering_leadership_transition": "Congrats on",
            "specialized_capability_gap": "Question on",
            "abstain": "Context",
        },
        bottleneck_by_segment={
            "recently_funded_startup": (
                "The typical bottleneck at this stage is recruiting capacity, not budget — "
                "in-house hiring rarely keeps pace with post-Series-B output demand."
            ),
            "mid_market_restructuring": (
                "After a restructure, the challenge is usually preserving delivery velocity "
                "while reducing cost — not starting over."
            ),
            "engineering_leadership_transition": (
                "In our experience, the first 90 days in a new engineering leadership role "
                "are when vendor mix and offshore partnerships get a fresh review."
            ),
            "specialized_capability_gap": (
                "The bottleneck for specialized builds is usually capability access, not budget — "
                "specifically, the time to find, hire, and onboard the right engineers."
            ),
            "abstain": (
                "The public signal I found is partial, so I won't over-claim. "
                "This note is mainly to ask whether the pattern I see matches your actual constraint."
            ),
        },
    )


# ---------------------------------------------------------------------------
# Top-level loader
# ---------------------------------------------------------------------------


class SeedLoader:
    """Loads and exposes all Tenacious seed materials."""

    def __init__(self) -> None:
        self.bench_capacity: dict[str, int] = self._load_bench_capacity()
        self.bench_loaded: bool = bool(self.bench_capacity)

        icp_text = self._read(settings.icp_definition_path)
        self.icp_pitch: dict[str, IcpPitchLanguage] = (
            _parse_icp_pitch_language(icp_text) if icp_text else {}
        )

        self.case_studies: list[CaseStudy] = (
            _parse_case_studies(self._read(settings.case_studies_path))
            if settings.case_studies_path.exists()
            else []
        )

        transcript_text = self._read(
            settings.discovery_transcripts_dir / "transcript_05_objection_heavy.md"
        )
        self.objection_patterns: ObjectionPatterns = (
            _parse_objection_patterns(transcript_text)
            if transcript_text
            else ObjectionPatterns(
                offshore_concern="We compete on reliability and retention, not hourly rate.",
                price_comparison="Any vendor who pitches percentage savings without a scoping conversation is making up numbers.",
                capacity_proof="We do not replace in-house architecture.",
                small_poc="The smallest real engagement we do is a fixed-scope project consulting contract.",
                architecture_boundary="A 'no' saves us both time.",
            )
        )

        self.pricing: PricingGuardrail = _parse_pricing_guardrail(
            self._read(settings.pricing_sheet_path) or "", self.objection_patterns
        )

        self.style: StyleConstraints = StyleConstraints()
        self.email_sequence: EmailSequenceStructure = _build_email_sequence_structure()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _read(path: Path) -> str:
        if not path.exists():
            return ""
        return path.read_text(encoding="utf-8")

    def _load_bench_capacity(self) -> dict[str, int]:
        if not settings.bench_summary_path.exists():
            return {}
        with open(settings.bench_summary_path, encoding="utf-8") as fh:
            bench = json.load(fh)
        return {
            stack_name: int(stack.get("available_engineers", 0))
            for stack_name, stack in bench.get("stacks", {}).items()
        }

    # ------------------------------------------------------------------
    # Public accessors
    # ------------------------------------------------------------------

    def get_pitch_language(self, segment: str, ai_maturity_score: int) -> str:
        """Return the seed-derived pitch sentence for this segment and AI tier."""
        pitch = self.icp_pitch.get(segment)
        if pitch is None:
            return "help with your engineering capacity needs"
        return pitch.high_readiness if ai_maturity_score >= 2 else pitch.low_readiness

    def get_subject_prefix(self, segment: str) -> str:
        return self.email_sequence.subject_prefix.get(segment, "Context")

    def get_bottleneck_sentence(self, segment: str) -> str:
        return self.email_sequence.bottleneck_by_segment.get(
            segment,
            "Companies at this stage often face capacity constraints that slow output.",
        )

    def find_case_study(self, segment: str) -> CaseStudy | None:
        """Return the best matching case study for the segment, or None."""
        for cs in self.case_studies:
            if cs.segment_hint == segment:
                return cs
        # Fallback: first study is loosely applicable to most ML/data engagements
        if segment in {"recently_funded_startup", "mid_market_restructuring"} and self.case_studies:
            return self.case_studies[0]
        return None

    def validate_email_style(
        self,
        subject: str,
        body_excluding_signature: str,
    ) -> list[str]:
        """Check subject + body against style_guide.md constraints.

        Returns a list of violation strings. Empty list = compliant.
        """
        violations: list[str] = []
        s = self.style

        # Subject length
        if len(subject) > s.max_subject_chars:
            violations.append(
                f"subject_too_long:{len(subject)}_chars_max_{s.max_subject_chars}"
            )

        # Subject prefix
        first_word = subject.split(":")[0].strip().lower() if ":" in subject else subject.split()[0].lower()
        if first_word in s.banned_subject_prefixes:
            violations.append(f"banned_subject_prefix:{first_word}")

        # Body word count
        word_count = len(body_excluding_signature.split())
        if word_count > s.max_cold_body_words:
            violations.append(
                f"body_too_long:{word_count}_words_max_{s.max_cold_body_words}"
            )

        # Banned vendor clichés
        body_lower = body_excluding_signature.lower()
        for phrase in s.banned_vendor_cliches:
            if phrase in body_lower:
                violations.append(f"banned_phrase:{phrase!r}")

        return violations


# Singleton — loaded once at module import. All modules import this instance.
seed_materials = SeedLoader()
