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


POPULAR_CITATION_THRESHOLD = 100

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


def classify(signals: ComplexitySignals) -> tuple[str, str]:
    if (
        signals.citation_count > POPULAR_CITATION_THRESHOLD
        or signals.cited_as_baseline_in_3plus_papers
        or signals.is_community_standard
    ):
        reasons = []
        if signals.citation_count > POPULAR_CITATION_THRESHOLD:
            reasons.append(f"citation count ({signals.citation_count}) exceeds {POPULAR_CITATION_THRESHOLD}")
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
