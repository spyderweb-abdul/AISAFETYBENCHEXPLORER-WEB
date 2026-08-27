# Destination path: backend/app/core/domain_relevance.py
# New file.
#
# Phase 6 item 4: deterministic AI-safety domain-relevance check for
# community submissions, run after extraction completes and before a
# submission is allowed into the admin review queue.
#
# Implements the check requested directly: overlap between the
# extracted task_type list and the controlled AI-safety task-type
# vocabulary (app/core/controlled_vocab.py's KNOWN_TASK_TYPES).
#
# TIGHTENING beyond the literal request: a small number of entries in
# KNOWN_TASK_TYPES are generic enough (Benchmark, Evaluation,
# Crowdsourced, Capabilities, Language) that almost any NLP paper could
# match them, which would make the check nearly meaningless on its own
# -- a benchmark paper about, say, translation quality would match
# "Language" and "Benchmark" without being remotely AI-safety-related.
# To keep the check meaningful, matches are split into two tiers:
#   - STRICT match (any task_type value outside the generic set): high
#     confidence, domain_check_passed=True.
#   - GENERIC-ONLY match (only generic entries matched, or nothing
#     matched but a safety-related keyword appears in the paper title/
#     description): borderline, domain_check_passed=None -- still
#     queued for review per the admin user's explicit instruction that
#     validation results should be surfaced to admin, not used to
#     silently auto-reject, but visibly flagged as needing a closer
#     look.
#   - NO match at all, strict or generic, and no safety keyword hit:
#     domain_check_passed=False -- combined with the quality_score
#     floor in submission_runner.py, this is the one case that DOES
#     auto-reject before ever reaching an admin (see
#     MIN_QUALITY_SCORE_FOR_REVIEW / the domain check in
#     submission_runner.py for exactly how the two combine).

from __future__ import annotations

from app.core.controlled_vocab import KNOWN_TASK_TYPES

_GENERIC_TASK_TYPES = {"benchmark", "evaluation", "crowdsourced", "capabilities", "language"}

_SAFETY_KEYWORDS = [
    "safety", "jailbreak", "red team", "red-team", "bias", "hallucination",
    "toxicity", "toxic", "alignment", "moral", "trustworthiness", "privacy",
    "adversarial", "harmful", "harm", "unlearning", "refusal", "misuse",
    "attack", "guardrail", "safeguard", "risk", "robustness", "fairness",
]


def check_domain_relevance(
    task_type: list[str] | None,
    benchmark_name: str = "",
    description: str = "",
) -> tuple[bool | None, str]:
    """Returns (domain_check_passed, reason).

    domain_check_passed is a tri-state: True (confident match), None
    (borderline -- queue with a visible flag), False (no signal at
    all -- combined with a low quality_score, this is what triggers
    auto-rejection in submission_runner.py).
    """
    known_lower = {t.lower() for t in KNOWN_TASK_TYPES}
    values = [t.strip() for t in (task_type or []) if t and t.strip()]
    values_lower = [v.lower() for v in values]

    strict_matches = [v for v in values if v.lower() in known_lower and v.lower() not in _GENERIC_TASK_TYPES]
    generic_matches = [v for v in values if v.lower() in known_lower and v.lower() in _GENERIC_TASK_TYPES]

    if strict_matches:
        return True, (
            f"Matched controlled AI-safety task types: {', '.join(strict_matches)}."
        )

    haystack = f"{benchmark_name} {description}".lower()
    keyword_hits = [kw for kw in _SAFETY_KEYWORDS if kw in haystack]

    if generic_matches or keyword_hits:
        reason_parts = []
        if generic_matches:
            reason_parts.append(
                f"only generic task type(s) matched ({', '.join(generic_matches)}), "
                "which are not specific enough to AI safety on their own"
            )
        if keyword_hits:
            reason_parts.append(
                f"safety-related keyword(s) found in title/description: {', '.join(keyword_hits[:5])}"
            )
        return None, (
            "Borderline domain match -- " + "; ".join(reason_parts) +
            ". Manual review recommended to confirm this paper is genuinely AI-safety-related."
        )

    return False, (
        "No extracted task_type value matched the controlled AI-safety task-type "
        "vocabulary (app/core/controlled_vocab.py's KNOWN_TASK_TYPES), and no "
        "safety-related keyword was found in the paper title or description. "
        "This paper is likely not AI-safety-related, or the free-tier extraction "
        "model mis-classified task_type."
    )
