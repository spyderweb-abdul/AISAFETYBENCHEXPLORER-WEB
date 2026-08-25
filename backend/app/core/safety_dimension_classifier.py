"""
app/core/safety_dimension_classifier.py

Phase 5: deterministic safety-dimension classification and Research Gap
Heatmap severity scoring, ported from the user's prior offline analysis
script (research_gap_heatmap.py). Kept deterministic for the same
reason as use_case_classifier.py -- see that module's docstring.

Faithful port of research_gap_heatmap.py's safety_dimensions mapping,
categorize_benchmark(), and calculate_gap_severity() logic, adapted to
operate on task_type as a list rather than a pandas string column.

One deliberate cleanup: the original script's 'Content Moderation'
keyword list contained a literal duplicate entry ('moderation' appeared
twice) -- a no-op typo, not a meaningful design choice, since duplicate
keywords cannot change an "any keyword present" match. Deduplicated
here; behavior is identical.
"""

from __future__ import annotations

from typing import Optional

SAFETY_DIMENSIONS: dict[str, list[str]] = {
    "Toxicity": ["toxicity", "toxic", "offensive", "abusive", "hate speech", "abuse"],
    "Jailbreak & Adversarial": [
        "jailbreak", "adversarial", "adversarial method", "attack", "red teaming",
        "red team", "fuzzing",
    ],
    "Privacy & Security": [
        "privacy", "memorization", "association", "cybersecurity", "vulnerability", "backdoor",
    ],
    "Bias & Fairness": ["bias", "fairness", "stereotype", "sociodemographics", "gender", "discrimination"],
    "Factuality & Truthfulness": [
        "factuality", "truthfulness", "hallucination", "lie detection", "consistency", "factual",
    ],
    "Alignment & Values": ["alignment", "value alignment", "norm alignment", "moral", "ethics", "cultural"],
    "Harmfulness Evaluation": ["harmfulness", "harmful", "harm", "helpfulness", "helplessness"],
    "Agent & Tool Safety": [
        "agent", "agents safety", "tool", "tooluse", "refusal", "instruction-following",
    ],
    "Grounding & RAG": ["grounding", "rag", "retrieval-augmented", "faithfulness"],
    "Content Moderation": ["content moderation", "moderation"],
}

GENERAL_SAFETY_FALLBACK = "General Safety"

COMPLEXITY_LEVELS = ["Popular", "High", "Medium", "Low"]


def classify_safety_dimensions(task_type: list[str]) -> list[str]:
    """Returns every safety dimension whose keyword list matches
    task_type, or [GENERAL_SAFETY_FALLBACK] if none match. A benchmark
    can have multiple dimensions (matches "break" only within a single
    dimension's keyword loop once one hit is found, not across
    dimensions), exactly matching the original script's behavior."""
    task_type_lower = " ".join(task_type or []).lower()
    if not task_type_lower.strip():
        return [GENERAL_SAFETY_FALLBACK]

    dimensions = []
    for dimension, keywords in SAFETY_DIMENSIONS.items():
        for keyword in keywords:
            if keyword in task_type_lower:
                dimensions.append(dimension)
                break

    return dimensions if dimensions else [GENERAL_SAFETY_FALLBACK]


def calculate_gap_severity(counts: dict[str, int]) -> str:
    """Faithful port of research_gap_heatmap.py's calculate_gap_severity().
    counts must have 'Popular', 'High', and 'Total' keys."""
    total = counts.get("Total", 0)
    if total == 0:
        return "Not Covered"

    popular = counts.get("Popular", 0)
    high = counts.get("High", 0)

    if popular == 0 and high == 0:
        return "Critical Gap"
    elif popular == 0 and high < 2:
        return "Under-benchmarked"
    elif (popular + high) / total < 0.3:
        return "Under-benchmarked"
    elif high == 0 and popular > 0:
        return "Limited Advanced"
    else:
        return "Well-covered"


def build_research_gap_heatmap(rows: list[tuple[list[str], str]]) -> list[dict]:
    """Aggregates (safety_dimensions, complexity_level) pairs -- one per
    benchmark -- into per-dimension counts and gap severity, replicating
    research_gap_heatmap.py's heatmap_data construction. rows is a list
    of (safety_dimensions, complexity_level) tuples, one per benchmark
    (a benchmark contributes to every dimension in its own list)."""
    all_dimensions = list(SAFETY_DIMENSIONS.keys()) + [GENERAL_SAFETY_FALLBACK]
    counts: dict[str, dict[str, int]] = {
        dim: {"Popular": 0, "High": 0, "Medium": 0, "Low": 0, "Total": 0}
        for dim in all_dimensions
    }

    for safety_dimensions, complexity_level in rows:
        level = complexity_level if complexity_level in COMPLEXITY_LEVELS else None
        for dimension in safety_dimensions or [GENERAL_SAFETY_FALLBACK]:
            if dimension not in counts:
                continue
            counts[dimension]["Total"] += 1
            if level:
                counts[dimension][level] += 1

    result = []
    for dimension in all_dimensions:
        dim_counts = counts[dimension]
        result.append({
            "dimension": dimension,
            "popular": dim_counts["Popular"],
            "high": dim_counts["High"],
            "medium": dim_counts["Medium"],
            "low": dim_counts["Low"],
            "total": dim_counts["Total"],
            "gap_severity": calculate_gap_severity(dim_counts),
        })
    return result
