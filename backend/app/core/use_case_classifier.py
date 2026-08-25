"""
app/core/use_case_classifier.py

Phase 5: deterministic use-case classification, ported from the user's
prior offline analysis script (use_case_filter.py). Kept as a separate,
deterministic module rather than left to the extraction model's own
judgment -- same rationale Section 2 of PROJECT_ROADMAP.md already
applies to complexity_classifier.py: reproducible and auditable
classification should not depend on model recall.

Faithful port of use_case_filter.py's use_case_mapping and
categorize_benchmark() logic, adapted from operating on a pandas row
(with task_type as a single string column) to operating directly on a
benchmark's task_type (a list, per orm.py's ARRAY(Text) column),
description, and benchmark_name.
"""

from __future__ import annotations

from typing import Optional

USE_CASE_MAPPING: dict[str, list[str]] = {
    "Medical AI": [
        "medical", "healthcare", "diagnosis", "clinical", "patient", "health", "disease",
        "drug", "pharmaceutical", "treatment", "therapy", "doctor", "hospital",
    ],
    "Financial Services": [
        "financial", "finance", "banking", "investment", "stock", "market", "crypto",
        "trading", "loan", "credit", "mortgage", "risk", "fraud", "compliance", "regulatory",
    ],
    "Customer Service Chatbots": [
        "conversation", "dialogue", "chatbot", "customer", "support", "service", "assistant",
        "multi-turn", "interaction", "chat", "helpdesk", "response", "user interaction", "dialog",
    ],
    "Content Moderation": [
        "toxicity", "toxic", "harmful", "offensive", "abuse", "hate", "moderation",
        "content filter", "inappropriate", "violation", "explicit", "jailbreak", "adversarial",
        "attack", "safety", "safeguard",
    ],
    "Education": [
        "question", "qa", "reading comprehension", "math", "reasoning",
        "knowledge", "student", "learning", "curriculum", "exam", "test", "education",
        "tutoring", "explanation", "teaching",
    ],
    "General Purpose": [
        "general", "benchmark", "eval", "alignment", "bias", "fairness", "stereotype",
        "cultural", "value", "norm", "value alignment", "instruction following",
    ],
}

# The six category labels, in a stable order for use as controlled-vocabulary
# dropdown options on the frontend (no /vocab change needed -- this list is
# the single source of truth for both the classifier and the UI).
USE_CASE_CATEGORIES: list[str] = list(USE_CASE_MAPPING.keys())

_MAX_USE_CASES = 3


def classify_use_cases(
    task_type: list[str],
    description: Optional[str],
    benchmark_name: str,
) -> list[str]:
    """Returns up to 3 use-case category labels for a benchmark, ranked by
    keyword match score, or ["General Purpose"] if nothing matches.

    Faithful port of use_case_filter.py's categorize_benchmark(): keyword
    hits in task_type score 3 points, hits in benchmark_name score 2, hits
    in the first 500 characters of description score 1. The original
    script joined selections into a single "; "-separated string for an
    Excel cell; here it returns a real list, matching how every other
    multi-value field (task_type, entry_modalities, language_support) is
    already stored on the Benchmark ORM model."""
    task_type_lower = " ".join(task_type or []).lower()
    name_lower = (benchmark_name or "").lower()
    description_lower = (description or "").lower()[:500]

    scores: dict[str, int] = {}
    for use_case, keywords in USE_CASE_MAPPING.items():
        score = 0
        for keyword in keywords:
            if keyword in task_type_lower:
                score += 3
            elif keyword in name_lower:
                score += 2
            elif keyword in description_lower:
                score += 1
        if score > 0:
            scores[use_case] = score

    if not scores:
        return ["General Purpose"]

    ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    return [use_case for use_case, _ in ranked[:_MAX_USE_CASES]]
