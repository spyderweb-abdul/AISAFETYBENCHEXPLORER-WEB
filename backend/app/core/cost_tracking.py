"""
app/core/cost_tracking.py

Roadmap item 12: per-run cost and run-to-run variance tracking for agent
extraction jobs. Kept separate from agent_runner.py by design -- see
agent_runner_patch_instructions.md for the three small integration
points needed there.

IMPORTANT SCOPE NOTE: this table prices every model string a caller
might pass as model_used, across OpenAI, Anthropic, Google Gemini,
Moonshot (Kimi), DeepSeek, and Alibaba (Qwen). That does NOT mean all of
these providers are actually callable yet -- as of this writing,
agent_runner.py's run_extraction() only dispatches to _call_openai and
_call_anthropic (see the `if provider == "openai" / elif provider ==
"anthropic" / else: raise ValueError` block). Submitting a job with
model_used="google/gemini-3-pro" (or kimi/deepseek/qwen) will fail at
that dispatch step today, regardless of whether pricing exists here.
This table is intentionally ahead of that integration so cost tracking
needs no further changes once a given provider's _call_* function is
added.

Pricing is USD per 1,000,000 tokens. Verified against each provider's
own pricing page or a current aggregator citing it, checked 2026-08-16.
LLM API pricing changes frequently and varies by exact model snapshot,
context-length tier, and cache hit/miss -- treat these as good-faith
point-in-time estimates, not contractual figures, and re-verify before
using them for real budget/billing decisions. Update
_MODEL_PRICING_PER_MILLION whenever a new model string is added to
ExtractionJobCreate.model_used, or when a provider changes its rate.
A model_used value not in this table returns None for estimated cost
rather than a fabricated number.

Sources checked 2026-08-16:
- OpenAI: https://developers.openai.com/api/docs/models/gpt-4o
- Anthropic: https://platform.claude.com/docs/en/about-claude/pricing,
  https://www.anthropic.com/claude/haiku
- Google Gemini: https://ai.google.dev/gemini-api/docs/pricing,
  https://benchlm.ai/google/api-pricing
- Moonshot AI (Kimi): https://benchlm.ai/moonshot/api-pricing,
  https://www.kimi.com/resources/kimi-k3-pricing
- DeepSeek: https://api-docs.deepseek.com/quick_start/pricing (note:
  DeepSeek moved to peak/off-peak tiered pricing effective 2026-08-16;
  the off-peak, cache-miss rate is used below as the baseline)
- Alibaba Qwen: https://www.alibabacloud.com/help/en/model-studio/model-pricing,
  https://benchlm.ai/alibaba/api-pricing
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
    "anthropic/claude-3-5-sonnet-20241022": (Decimal("3.00"), Decimal("15.00")),
    "anthropic/claude-3-5-sonnet-20240620": (Decimal("3.00"), Decimal("15.00")),
    "anthropic/claude-haiku-4-5-20251001": (Decimal("1.00"), Decimal("5.00")),
    "anthropic/claude-opus-5": (Decimal("5.00"), Decimal("25.00")),

    # --- Google Gemini ---
    # NOT YET CALLABLE from agent_runner.py -- see module docstring.
    "google/gemini-3.1-pro": (Decimal("2.00"), Decimal("12.00")),
    "google/gemini-3.6-flash": (Decimal("1.50"), Decimal("7.50")),
    "google/gemini-3.5-flash-lite": (Decimal("0.30"), Decimal("2.50")),
    "google/gemini-2.5-flash-lite": (Decimal("0.10"), Decimal("0.40")),

    # --- Moonshot AI (Kimi) ---
    # NOT YET CALLABLE from agent_runner.py -- see module docstring.
    # Cache-miss input rate used below; Kimi also offers a much cheaper
    # cache-hit input rate ($0.30/M for K3) not modeled here since usage
    # objects returned by run_extraction() do not currently distinguish
    # cache hit vs miss tokens.
    "moonshot/kimi-k3": (Decimal("3.00"), Decimal("15.00")),
    "moonshot/kimi-k2.6": (Decimal("0.95"), Decimal("4.00")),
    "moonshot/kimi-k2.5": (Decimal("0.60"), Decimal("3.00")),

    # --- DeepSeek ---
    # NOT YET CALLABLE from agent_runner.py -- see module docstring.
    # DeepSeek's off-peak, cache-miss rate used as the baseline; actual
    # cost varies by time of day under DeepSeek's peak/off-peak scheme
    # introduced 2026-08-16.
    "deepseek/deepseek-v4-pro": (Decimal("0.66"), Decimal("1.98")),
    "deepseek/deepseek-v4-flash": (Decimal("0.22"), Decimal("0.66")),

    # --- Alibaba Qwen ---
    # NOT YET CALLABLE from agent_runner.py -- see module docstring.
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
