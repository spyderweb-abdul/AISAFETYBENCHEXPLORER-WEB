from pydantic import BaseModel


class ComplexitySignalsIn(BaseModel):
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


class ComplexityResultOut(BaseModel):
    complexity_level: str
    justification: str
