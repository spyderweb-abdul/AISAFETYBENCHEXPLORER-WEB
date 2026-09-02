# Destination path: backend/app/core/vocab_normalize.py
# New file.
#
# Extracted from agent_runner.py's pre-existing _normalize_metric_name/
# _metric_name_variants helpers (originally written to reconcile Sheet
# 1 <-> Sheet 2 metric-name drift within a single extraction) so that
# app/routers/vocab_terms.py can reuse the EXACT same normalization
# when checking vocab_terms uniqueness, instead of maintaining a second,
# potentially-drifting copy of the same logic. agent_runner.py should
# import from here too (see the agent_runner.py patch) rather than
# keeping its own private copies -- this is the single source of truth
# for "what counts as the same term" across both the extraction
# pipeline and the admin CRUD.

from __future__ import annotations

import re
from typing import Any

_PAREN_SUFFIX_RE = re.compile(r"\s*\([^)]*\)\s*$")
_PUNCT_RE = re.compile(r"[^a-z0-9 ]+")


def normalize_term(value: Any) -> str:
    """Lowercase, whitespace-collapsed form used for exact-duplicate
    detection (vocab_terms.normalized_term column, and the DB
    uniqueness check in vocab_terms.py / agent_runner.py's upsert)."""
    return " ".join(str(value or "").strip().lower().split())


def term_variants(value: Any) -> set[str]:
    """Returns a set of normalized forms of a term, to reconcile minor
    naming drift (e.g. a trailing parenthetical abbreviation, or
    punctuation differences) without requiring exact string equality.
    Used for FUZZY matching only (e.g. Sheet 1 <-> Sheet 2 metric name
    reconciliation within one extraction) -- the DB uniqueness
    constraint itself still uses the single exact normalize_term()
    form, so two genuinely different-looking terms are not silently
    merged in the catalogue without an admin's explicit alias action.
    """
    base = normalize_term(value)
    variants = {base}
    stripped = _PAREN_SUFFIX_RE.sub("", base).strip()
    if stripped:
        variants.add(stripped)
    no_punct = _PUNCT_RE.sub("", base).strip()
    if no_punct:
        variants.add(no_punct)
    no_punct_stripped = _PUNCT_RE.sub("", stripped).strip()
    if no_punct_stripped:
        variants.add(no_punct_stripped)
    return {v for v in variants if v}
