from dataclasses import dataclass, field


@dataclass
class ComplexitySignals:
    citation_count: int = 0
    cited_as_baseline_in_3plus_papers: bool = False
    is_community_standard: bool = False

    multi_hop_reasoning: bool = False
    adversarial_or_red_teaming: bool = False
    subjective_open_ended_generation: bool = False
    risk_critical_domain: bool = False
    novel_metric: bool = False
    complex_eval_pipeline: bool = False
    requires_domain_expertise: bool = False
    pluralistic_annotation_50plus: bool = False

    limited_reasoning_1_2_step: bool = False
    some_adversarial_testing: bool = False
    mixed_objective_subjective: bool = False
    standard_metrics_minor_adaptation: bool = False
    moderate_annotation_effort: bool = False

    notes: list[str] = field(default_factory=list)


# Fallback ONLY -- used when app.core.config.settings cannot be
# imported/loaded for any reason (e.g. a standalone script or test with
# no .env present). The live, normally-used value comes from
# Settings.POPULAR_CITATION_THRESHOLD (backend/app/core/config.py),
# defaulting to 500 there.
DEFAULT_POPULAR_CITATION_THRESHOLD = 500

HIGH_CRITERIA = {
    "multi_hop_reasoning": "multi-hop or compositional reasoning across > 2 steps",
    "adversarial_or_red_teaming": "adversarial robustness testing (red-teaming/jailbreaking)",
    "subjective_open_ended_generation": "subjective/open-ended generation requiring nuanced evaluation",
    "risk_critical_domain": "risk-critical domain (medical, legal, financial, CBRN)",
    "novel_metric": "novel metric development",
    "complex_eval_pipeline": "complex multi-phase evaluation pipeline",
    "requires_domain_expertise": "requires domain expertise for annotation or evaluation",
    "pluralistic_annotation_50plus": "pluralistic annotation with >= 50 annotators",
}

MEDIUM_CRITERIA = {
    "limited_reasoning_1_2_step": "1-2 step reasoning or limited compositional requirements",
    "some_adversarial_testing": "some adversarial testing, but not the primary focus",
    "mixed_objective_subjective": "mix of objective and subjective evaluation",
    "standard_metrics_minor_adaptation": "standard metrics with minor domain-specific adaptations",
    "moderate_annotation_effort": "moderate annotation effort (single-pass, specialist annotators)",
}


def get_popular_citation_threshold(explicit: int | None = None) -> int:
    """Resolves the live Popular citation threshold: explicit override
    if passed, else Settings.POPULAR_CITATION_THRESHOLD, else the
    DEFAULT_POPULAR_CITATION_THRESHOLD fallback if settings cannot be
    loaded at all. This is the single source of truth other modules
    (app/core/citation_range.py, app/core/tasks.py) should call instead
    of re-reading settings.POPULAR_CITATION_THRESHOLD directly, so a
    future change to the resolution logic only needs to happen here."""
    if explicit is not None:
        return explicit
    try:
        from app.core.config import settings
        return settings.POPULAR_CITATION_THRESHOLD
    except Exception:
        return DEFAULT_POPULAR_CITATION_THRESHOLD


def classify(signals: ComplexitySignals, popular_citation_threshold: int | None = None) -> tuple[str, str]:
    """popular_citation_threshold: optional override. When omitted, the
    live value comes from get_popular_citation_threshold() above
    (Settings.POPULAR_CITATION_THRESHOLD, default 500, env-overridable).
    Pass an explicit value (as tests do) to pin the threshold
    regardless of environment/.env state.
    """
    threshold = get_popular_citation_threshold(popular_citation_threshold)

    if (
        signals.citation_count > threshold
        or signals.cited_as_baseline_in_3plus_papers
        or signals.is_community_standard
    ):
        reasons = []
        if signals.citation_count > threshold:
            reasons.append(f"citation count ({signals.citation_count}) exceeds {threshold}")
        if signals.cited_as_baseline_in_3plus_papers:
            reasons.append("cited as a baseline in 3 or more safety papers")
        if signals.is_community_standard:
            reasons.append("adopted as a community standard")
        justification = f"Popular -- {'; '.join(reasons[:2])}."
        return "Popular", justification

    high_met = [label for key, label in HIGH_CRITERIA.items() if getattr(signals, key)]
    if len(high_met) >= 2:
        justification = f"High -- {high_met[0]} and {high_met[1]}."
        return "High", justification

    medium_met = [label for key, label in MEDIUM_CRITERIA.items() if getattr(signals, key)]
    if len(medium_met) >= 2:
        justification = f"Medium -- {medium_met[0]} and {medium_met[1]}."
        return "Medium", justification

    justification = (
        "Low -- single-step reasoning and standard unmodified metrics with "
        "minimal adversarial considerations."
    )
    return "Low", justification
