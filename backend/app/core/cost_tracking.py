"""
app/core/cost_tracking.py

Roadmap item 12: per-run cost and run-to-run variance tracking for agent
extraction jobs. Kept separate from agent_runner.py by design -- see
agent_runner_patch_instructions.md for the three small integration
points needed there.

IMPORTANT SCOPE NOTE: this table prices every model string a caller
might pass as model_used, across OpenAI, Anthropic, Google Gemini,
Moonshot (Kimi), DeepSeek, and Alibaba (Qwen). That does NOT mean all of
these providers are actually callable yet -- agent_runner.py's
run_extraction() dispatches to _call_openai, _call_anthropic, and
_call_ollama (via the "ollama" provider prefix); Gemini/Kimi/DeepSeek/
Qwen direct-provider entries below are priced for completeness but not
wired up as their own callable branch (the Kimi/DeepSeek/Qwen models
that ARE callable go through Ollama Cloud instead, under the "ollama/"
prefix, and intentionally have no pricing entry here -- see the Ollama
note below).

Pricing is USD per 1,000,000 tokens. Verified against each provider's
own pricing page or a current aggregator citing it, checked 2026-08-16
unless noted otherwise. LLM API pricing changes frequently and varies by
exact model snapshot, context-length tier, and cache hit/miss -- treat
these as good-faith point-in-time estimates, not contractual figures,
and re-verify before using them for real budget/billing decisions.

MODEL LIFECYCLE WARNING (2026-08-23): a real extraction job submitted
against anthropic/claude-3-5-sonnet-20241022 failed with
anthropic.NotFoundError: 404 model not found. Verified against
platform.claude.com/docs/en/about-claude/model-deprecations and
endoflife.date/claude: this model was deprecated 2025-08-13 and retired
2025-10-28 -- it has been non-functional for roughly 10 months. Its
pricing entry (and claude-3-5-sonnet-20240620's) is left in this table
ONLY because removing it would silently change the estimated_cost_usd
of already-completed historical ExtractionJob rows if this function is
ever re-run against them; it must NOT be re-added to
frontend/app/admin/extraction/page.tsx's MODEL_OPTIONS dropdown. Update
_MODEL_PRICING_PER_MILLION whenever a new model string is added to that
dropdown, or when a provider changes its published rate -- and check the
provider's own deprecation page before doing so, not just its pricing
page.

A model_used value not in this table returns None for estimated cost
rather than a fabricated number.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Optional, Sequence

# (input_price_per_million_usd, output_price_per_million_usd)
_MODEL_PRICING_PER_MILLION: dict[str, tuple[Decimal, Decimal]] = {
    # --- OpenAI ---
    "openai/gpt-4o": (Decimal("2.50"), Decimal("10.00")),
    "openai/gpt-4o-mini": (Decimal("0.15"), Decimal("0.60")),

    # --- Anthropic ---
    # claude-sonnet-5 introductory pricing runs through 2026-08-31; the
    # standard rate from 2026-09-01 is $3/$15 -- update this entry then.
    "anthropic/claude-sonnet-5": (Decimal("2.00"), Decimal("10.00")),
    "anthropic/claude-haiku-4-5-20251001": (Decimal("1.00"), Decimal("5.00")),
    "anthropic/claude-opus-5": (Decimal("5.00"), Decimal("25.00")),
    # RETIRED 2025-10-28 -- do not offer in the model dropdown. Kept only
    # so historical ExtractionJob rows already priced against this
    # snapshot are not silently reinterpreted if this function re-runs.
    "anthropic/claude-3-5-sonnet-20241022": (Decimal("3.00"), Decimal("15.00")),
    "anthropic/claude-3-5-sonnet-20240620": (Decimal("3.00"), Decimal("15.00")),

    # --- Google Gemini ---
    # NOT YET CALLABLE from agent_runner.py -- see module docstring.
    "google/gemini-3.1-pro": (Decimal("2.00"), Decimal("12.00")),
    "google/gemini-3.6-flash": (Decimal("1.50"), Decimal("7.50")),
    "google/gemini-3.5-flash-lite": (Decimal("0.30"), Decimal("2.50")),
    "google/gemini-2.5-flash-lite": (Decimal("0.10"), Decimal("0.40")),

    # --- Moonshot AI (Kimi) direct API ---
    # NOT the callable path -- the actual callable Kimi models go through
    # Ollama Cloud under the "ollama/" prefix (ollama/kimi-k3,
    # ollama/kimi-k2.6), which is a flat subscription and intentionally
    # has no pricing entry here (see cost_tracking module docstring).
    # These entries describe Moonshot's own direct API, priced for
    # reference only, in case that path is ever wired up separately.
    "moonshot/kimi-k3": (Decimal("3.00"), Decimal("15.00")),
    "moonshot/kimi-k2.6": (Decimal("0.95"), Decimal("4.00")),
    "moonshot/kimi-k2.5": (Decimal("0.60"), Decimal("3.00")),

    # --- DeepSeek direct API ---
    # NOT the callable path -- see Kimi note above; callable DeepSeek
    # models go through Ollama Cloud (ollama/deepseek-v4-pro,
    # ollama/deepseek-v4-flash).
    "deepseek/deepseek-v4-pro": (Decimal("0.66"), Decimal("1.98")),
    "deepseek/deepseek-v4-flash": (Decimal("0.22"), Decimal("0.66")),

    # --- Alibaba Qwen direct API ---
    # NOT the callable path -- see Kimi note above; callable Qwen models
    # go through Ollama Cloud (ollama/qwen3.5:397b, ollama/qwen3-coder:480b).
    "alibaba/qwen3.5-397b": (Decimal("0.60"), Decimal("3.60")),
    "alibaba/qwen3.5-plus": (Decimal("0.40"), Decimal("2.40")),
    "alibaba/qwen3.5-flash": (Decimal("0.10"), Decimal("0.40")),
    "alibaba/qwen3.7-flash": (Decimal("0.03"), Decimal("0.13")),
}


def estimate_cost_usd(
    model_used: Optional[str],
    input_tokens: Optional[int],
    output_tokens: Optional[int],
) -> Optional[Decimal]:
    """Returns an estimated USD cost for one extraction run, or None if
    model_used is not in _MODEL_PRICING_PER_MILLION (unknown/unpriced
    model) or either token count is missing."""
    if not model_used or input_tokens is None or output_tokens is None:
        return None
    pricing = _MODEL_PRICING_PER_MILLION.get(model_used)
    if pricing is None:
        return None
    input_price, output_price = pricing
    cost = (
        Decimal(input_tokens) * input_price + Decimal(output_tokens) * output_price
    ) / Decimal("1000000")
    return cost.quantize(Decimal("0.0001"))


def compute_run_variance(quality_scores: Sequence[Optional[Decimal]]) -> dict:
    """Given the quality_score of every ExtractionJob run for the same
    source_value, returns run_count, mean, and population stddev.

    Returns stddev_quality_score=0.0 for a single run, since variance is
    mathematically undefined for n=1 and 0.0 communicates "no observed
    variance yet" more usefully to an admin reviewing the Pending Review
    queue than a null/NaN would."""
    scores = [float(s) for s in quality_scores if s is not None]
    count = len(scores)
    if count == 0:
        return {"run_count": 0, "mean_quality_score": None, "stddev_quality_score": None}
    mean = sum(scores) / count
    if count == 1:
        return {
            "run_count": count,
            "mean_quality_score": round(mean, 4),
            "stddev_quality_score": 0.0,
        }
    variance = sum((s - mean) ** 2 for s in scores) / count
    stddev = variance ** 0.5
    return {
        "run_count": count,
        "mean_quality_score": round(mean, 4),
        "stddev_quality_score": round(stddev, 4),
    }
