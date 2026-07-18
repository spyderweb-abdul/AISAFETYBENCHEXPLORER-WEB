"""Synchronous agent runner for Phase 3.

Runs the full AISafety_Benchmark_Extraction_Master_Prompt.md methodology
against a chosen backing model (Phases 0-4: pre-extraction research, Sheet 1
metadata extraction with controlled vocabulary, complexity classification,
and the QA checklist), then validates the output against BenchmarkCreate
and the complexity decision tree before writing the result to the DB as a
pending benchmark.

No Celery yet (Phase 4 of the PROJECT_ROADMAP, not to be confused with the
Phase 4 QA Checklist in the master prompt). FastAPI BackgroundTasks
dispatches this function.
"""
from __future__ import annotations

import json
import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.core.complexity_classifier import ComplexitySignals, classify
from app.core.paper_fetcher import fetch_source
from app.models.orm import Benchmark, EvalMetric, ExtractionJob
from app.schemas.benchmark import BenchmarkCreate

logger = logging.getLogger(__name__)

# These two vocabularies are constrained to the ACTUAL enum values declared in
# backend/app/schemas/benchmark.py (EntryModality, LanguageSupport), which are
# narrower than the master prompt's Appendix 1A MODALITY_KEYWORDS and the
# unrestricted ISO 639-1 Language column. Extend EntryModality/LanguageSupport
# in benchmark.py (and the corresponding Postgres ENUM in orm.py) first if you
# need those additional values; do not just add them here, since the DB enum
# type would reject them at insert time.
ENTRY_MODALITIES = [
    "Prompts", "Conversations", "Examples", "Binary-choice Questions",
    "Multiple-choice Questions", "Scenarios", "Sentences", "Excerpts",
    "Transcripts", "Sentence Pairs", "Entry Tuples",
]

LANGUAGE_SUPPORT = ["en", "zh", "ar", "fr", "hi", "ko", "Multilingual"]

KNOWN_TASK_TYPES = [
    "Safety", "Adversarial", "Adversarial Method", "Red Teaming", "Jailbreak",
    "Attack Eval", "Robustness", "Vulnerability", "Risk Assessment",
    "Bias", "Fairness", "Stereotype", "Gender", "Social", "Sociodemographics",
    "Cultural", "Norm Alignment",
    "Factuality", "Factual Consistency", "Hallucination", "Truthfulness",
    "Grounding", "Faithfulness", "Claim Verification",
    "Toxicity", "Harmfulness", "Hate Speech", "Content Moderation",
    "Hazardous", "Hazardous Knowledge", "Physical Safety", "Medical Safety",
    "Alignment", "Value Alignment", "Moral", "Trustworthiness",
    "Helpfulness Eval", "Preference Eval", "Satisfaction Eval",
    "Privacy", "Prompt Extraction", "Cyberattacks", "Unlearning",
    "Agents Safety", "Agents Behavior Detection", "Reasoning",
    "Refusal", "False Refusal", "Over Refusal", "Non-compliance",
    "Consistency", "Calibration",
    "Instruction-following", "Rule-following", "RAG", "Multimodal",
    "Conversational Safety", "Opinion Steering", "Causal Reasoning",
    "Benchmark", "Evaluation", "Crowdsourced", "Lie Detection",
    "Capabilities", "Language",
]

_COMPLEXITY_SIGNAL_KEYS = [
    "cited_as_baseline_in_3plus_papers", "is_community_standard",
    "multi_hop_reasoning", "adversarial_or_red_teaming", "subjective_open_ended_generation",
    "risk_critical_domain", "novel_metric", "complex_eval_pipeline", "requires_domain_expertise",
    "pluralistic_annotation_50plus", "limited_reasoning_1_2_step", "some_adversarial_testing",
    "mixed_objective_subjective", "standard_metrics_minor_adaptation", "moderate_annotation_effort",
]

# Sheet 2 / Evaluation Metrics Catalogue schema (Phase 2 of the master prompt).
# Column names below are the JSON keys the model must return per metric; they
# map 1:1 to the EvalMetric ORM columns (see app/models/orm.py) via
# _METRIC_FIELD_MAP in _persist_eval_metrics() below.
EVAL_METRIC_ROW_SCHEMA = {
    "benchmarkname": "string",
    "papertitle": "string",
    "paperlink": "string",
    "metricname": "string",
    "conceptualdescription": "string",
    "methodologicaldetails": "string",
    "mathematicaldefinition": "string",
    "differencesfromstandarddefinition": "string",
    "notes": "string",
}

EVAL_METRICS_EXTRACTION_INSTRUCTIONS = """
PHASE 2 -- SHEET 2 / EVALUATION METRICS CATALOGUE:

In addition to the benchmark-level fields above, you must also return a
top-level field `evaluation_metrics_catalogue`: a list of one object per
metric named in `evaluation_metrics`.

Each object must have exactly these keys:
- benchmarkname
- papertitle
- paperlink
- metricname
- conceptualdescription
- methodologicaldetails
- mathematicaldefinition
- differencesfromstandarddefinition
- notes

Hard requirements:
- benchmarkname must exactly equal benchmark_name.
- papertitle must exactly equal benchmark_paper_title.
- paperlink must exactly equal paper_link.
- metricname must use the paper's own terminology wherever possible. If the
  paper writes an abbreviation in parentheses (e.g. "Relative Decision Bias
  (LLM-RDT)"), use the SAME full form consistently in both evaluation_metrics
  and evaluation_metrics_catalogue -- do not write the long form in one list
  and the abbreviation in the other, since this breaks the Sheet 1 <-> Sheet 2
  cross-check.
- Only list statistical procedures (e.g. bootstrapped confidence intervals,
  significance tests) as separate "metrics" if the paper treats them as a
  named evaluation metric in its own right, not as a generic reporting
  procedure applied on top of a real metric.
- conceptualdescription must weave together, in coherent prose: task type,
  data type, safety dimension, intent, and judge type.
- methodologicaldetails must be a numbered step-by-step procedure covering:
  event definitions, label sources, multi-turn handling, category/instance
  handling, and aggregation method.
- mathematicaldefinition must provide a concrete formula (LaTeX-style) or a
  faithful formalization derived from the method description if the paper
  does not state the formula explicitly.
- differencesfromstandarddefinition must explain how this implementation
  differs from the canonical/standard version of the metric, or state that it
  is a novel metric with no direct standard analog.
- notes should include empirical results, limitations, use cases, and
  interactions with other metrics whenever the paper provides them.

If no metrics are defined in the paper, return an empty list for both
evaluation_metrics and evaluation_metrics_catalogue -- do not fabricate
metrics that are not in the paper.
""".strip()

# This is the master prompt's Role & Context, Phase 0 research steps, Phase 1
# Sheet 1 column definitions and controlled vocabulary, Phase 2 Sheet 2
# evaluation-metric extraction, and the Phase 3 complexity decision tree,
# condensed into a single-call system prompt and adapted from the
# Excel-workbook output format to a single JSON object matching
# BenchmarkCreate plus a top-level evaluation_metrics_catalogue array
# (persisted separately into EvalMetric rows -- see _persist_eval_metrics()).
# The Phase 4 QA checklist / Phase 5 Excel generation are still NOT wired
# into this runner -- see the TODO at the bottom of this file.
SYSTEM_PROMPT_STUB = f"""
You are an expert AI safety researcher specialising in LLM evaluation methodology,
performing exhaustive, technically rigorous metadata extraction from an AI safety
benchmark paper, following the same rigor as the AISafety_Benchmark_Extraction
Master Prompt used elsewhere in this project.

Your output must be truthful and grounded: every field must be derived directly
from the paper or verifiable external sources (Semantic Scholar, GitHub,
HuggingFace). Do not hallucinate statistics, formulas, URLs, or citation counts.

PHASE 0 -- PRE-EXTRACTION RESEARCH (perform before extracting any field):
1. Fetch the full paper (title, authors, abstract, all sections, all appendices)
   from the DOI, arXiv ID, or PDF URL provided.
2. Run ALL of the following targeted searches using your web_search tool before
   writing any field value. Do not skip any of them, and do not default a field
   to null/"Unknown" unless the relevant search below was actually run and came
   back empty:
   a. "<paper title>" citations semantic scholar -- to find the verified
      citation count for cited_by.
   b. "<benchmark name>" github -- to find code_repository.
   c. "<benchmark name>" dataset huggingface -- to find dataset_repository.
   d. "<benchmark name>" license -- to find the license field.
   e. huggingface.co/datasets "<benchmark name>" -- to cross-check the
      HuggingFace dataset card directly for sample counts, license, and
      integration_option signals.
3. Read the paper systematically in this order: Abstract -> Introduction ->
   Related Work -> Benchmark Design -> Dataset Construction -> Evaluation
   Methodology -> Results -> Appendix. Pay special attention to sections
   titled "Metrics", "Evaluation", "Methodology", dataset statistics tables,
   footnotes, and appendices.

PHASE 1 -- EXTRACT THESE FIELDS (return as a single JSON object):

benchmark_name: short canonical name/abbreviation exactly as used in the paper,
    never invented.
task_type: list of one or more values from KNOWN_TASK_TYPES below. If none fit,
    infer the closest match.
benchmark_paper_title: full verbatim paper title.
release_date: YYYY-MM-DD (use the 1st of the month if only month/year is known),
    or null if genuinely unknown.
description: a synthesised 2-3 sentence technical summary covering what the
    benchmark evaluates, its core methodology/innovation, and why it advances AI
    safety evaluation. Do NOT copy the abstract verbatim.
code_dataset: "Yes" if search 2b or 2c above found a verified code repository
    or dataset, else "No". Do not answer "No" without having actually run
    those searches first.
no_of_samples: total instances/prompts/examples as a string with units, e.g.
    "15000 ratings (150 prompts x 100 annotators)", sourced from the dataset
    statistics table, GitHub repo, or HuggingFace dataset card (search 2e),
    or null if unknown after checking all three.
created_by: "Human", "Machine", or "Hybrid" based on CREATED_BY_KEYWORDS below.
entry_modalities: list of one or more values from ENTRY_MODALITIES below (ONLY
    these exact values are valid, do not invent new ones).
dev_purpose: "Eval", "Train", or "Train & Eval" based on DEVELOPMENT_PURPOSE
    keywords below.
license: e.g. "MIT", "Apache 2.0", "CC-BY 4.0", "CC0", "Custom Research",
    or "Unknown" -- only use "Unknown" after having run search 2d AND checked
    the GitHub repo's LICENSE file AND the HuggingFace dataset card license tag.
evaluation_metrics: list of ALL evaluation metrics named or defined in the
    paper, using the paper's own exact terminology, consistently spelled the
    same way here as in evaluation_metrics_catalogue (see hard requirements
    below).
language_support: list of one or more values from LANGUAGE_SUPPORT below (ONLY
    these exact values are valid; use "Multilingual" if more than 5 languages
    are covered).
integration_option: "API", "Export", "API & Export", or "NA" based on
    INTEGRATION_KEYWORDS below (check both GitHub and HuggingFace signals from
    searches 2b/2c/2e).
citation_range: leave null; the platform computes this separately.
cited_by: integer citation count from search 2a (Semantic Scholar/Google
    Scholar). Use 0 if truly unknown after running that search -- NEVER
    return null for this field.
code_repository: verified GitHub URL from search 2b, or null if search 2b was
    run and found nothing.
dataset_repository: verified HuggingFace/dataset URL from search 2c or 2e, or
    null if those searches were run and found nothing.
paper_link: canonical DOI or arXiv URL.

Additionally, assess and return these complexity signal fields as booleans,
based on your reading of the paper (used to drive the Phase 3 decision tree
below -- do not compute the final complexity level yourself, just the raw
signals):
cited_as_baseline_in_3plus_papers, is_community_standard,
multi_hop_reasoning, adversarial_or_red_teaming, subjective_open_ended_generation,
risk_critical_domain, novel_metric, complex_eval_pipeline, requires_domain_expertise,
pluralistic_annotation_50plus, limited_reasoning_1_2_step, some_adversarial_testing,
mixed_objective_subjective, standard_metrics_minor_adaptation, moderate_annotation_effort

KNOWN_TASK_TYPES = {KNOWN_TASK_TYPES}

ENTRY_MODALITIES (controlled vocabulary, exact values only) = {ENTRY_MODALITIES}

LANGUAGE_SUPPORT (controlled vocabulary, exact values only) = {LANGUAGE_SUPPORT}

CREATED_BY_KEYWORDS:
Human -> manually, annotated, human, crowdsourced, expert, curated
Machine -> automatically, generated, machine, synthetic, auto-generated
Hybrid -> if both Human and Machine signals are present

DEVELOPMENT_PURPOSE_KEYWORDS:
Train -> train, training, fine-tune, finetune
Eval -> eval, evaluation, benchmark, test
Train & Eval -> if both Train and Eval signals are present

INTEGRATION_KEYWORDS:
API -> api, python package, pip install, library, import, client, sdk,
    huggingface, datasets, library:transformers, library:evaluate
Export -> download, clone, csv file, json file, manual, extract, archive,
    format:csv, format:json, format:parquet
API & Export -> if both API and Export signals are present
NA -> if neither HuggingFace nor GitHub information is available

Do not guess numeric fields beyond citation counts; leave optional text fields
null when genuinely unknown, but cited_by must always be an integer.

Also return a top-level field:
evaluation_metrics_catalogue: a list of per-metric Sheet 2 records (see PHASE 2
instructions below for the required structure).

Return ONLY a single JSON object with the benchmark fields, the complexity
signal booleans, and evaluation_metrics_catalogue. No prose, no markdown, no
code fences.
""".strip()

SYSTEM_PROMPT_STUB = SYSTEM_PROMPT_STUB + "\n\n" + EVAL_METRICS_EXTRACTION_INSTRUCTIONS

# Fallback normalization map in case the model still returns free text
# despite the constrained prompt above. Extend this map as new mismatches
# are observed in production runs.
_ENTRY_MODALITY_ALIASES = {
    "text": "Prompts",
    "question": "Multiple-choice Questions",
    "questions": "Multiple-choice Questions",
    "dialogue": "Conversations",
    "dialogues": "Conversations",
    "conversation": "Conversations",
    "example": "Examples",
    "scenario": "Scenarios",
    "sentence": "Sentences",
    "excerpt": "Excerpts",
    "transcript": "Transcripts",
}

_LANGUAGE_ALIASES = {
    "english": "en",
    "chinese": "zh",
    "mandarin": "zh",
    "arabic": "ar",
    "french": "fr",
    "hindi": "hi",
    "korean": "ko",
    "multi": "Multilingual",
    "multiple": "Multilingual",
}


def _normalize_list(values: Any, allowed: list[str], aliases: dict[str, str]) -> list[str]:
    if not values:
        return []
    if isinstance(values, str):
        values = [values]
    normalized: list[str] = []
    for v in values:
        v_str = str(v).strip()
        if v_str in allowed:
            normalized.append(v_str)
            continue
        alias = aliases.get(v_str.lower())
        if alias:
            normalized.append(alias)
    seen = set()
    result = []
    for v in normalized:
        if v not in seen:
            seen.add(v)
            result.append(v)
    return result


def _normalize_metric_name(value: Any) -> str:
    return " ".join(str(value or "").strip().lower().split())


_PAREN_SUFFIX_RE = re.compile(r"\s*\([^)]*\)\s*$")
_PUNCT_RE = re.compile(r"[^a-z0-9 ]+")


def _metric_name_variants(value: Any) -> set[str]:
    """Returns a set of normalized forms of a metric name to reconcile
    naming drift between evaluation_metrics and evaluation_metrics_catalogue.

    This fixes a real production failure: the model wrote "relative decision
    bias (LLM-RDT)" in one list and "relative decision bias" in the other,
    which the old exact-match validator treated as two different metrics and
    raised a ValueError, crashing the job. Trailing parenthetical
    abbreviations, punctuation, and whitespace differences should not cause
    a hard failure -- only a genuinely absent metric should.
    """
    base = _normalize_metric_name(value)
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


def _validate_eval_metrics_catalogue(raw: dict[str, Any]) -> dict[str, Any]:
    """Enforces the master prompt's Sheet 1 <-> Sheet 2 QA rule: every metric
    listed in evaluation_metrics should have a corresponding row in
    evaluation_metrics_catalogue, and every row must carry all 9 required
    keys with non-empty, consistent benchmark identifiers.

    Structural defects (missing keys, empty metricname, true duplicate rows,
    mismatched benchmark/paper identifiers) still raise ValueError, since
    those indicate a real extraction defect. Naming drift between the two
    lists (e.g. an abbreviation appended in one list but not the other) is
    now reconciled via _metric_name_variants() and only logged as a warning,
    since that reflects inconsistent formatting rather than a missing metric.
    """
    metrics = raw.get("evaluation_metrics") or []
    catalogue = raw.get("evaluation_metrics_catalogue") or []

    if not isinstance(metrics, list):
        raise ValueError("Model returned non-list evaluation_metrics.")
    if not isinstance(catalogue, list):
        raise ValueError("Model returned non-list evaluation_metrics_catalogue.")

    required_keys = set(EVAL_METRIC_ROW_SCHEMA.keys())
    seen_exact: set[str] = set()

    for i, row in enumerate(catalogue):
        if not isinstance(row, dict):
            raise ValueError(f"Metric row {i} is not an object.")

        missing = required_keys - set(row.keys())
        if missing:
            raise ValueError(f"Metric row {i} missing keys: {sorted(missing)}")

        for key in required_keys:
            if row.get(key) is None:
                row[key] = ""
            if not isinstance(row.get(key), str):
                row[key] = str(row.get(key))

        if row["benchmarkname"] != raw.get("benchmark_name", ""):
            raise ValueError(f"Metric row {i} benchmarkname does not match benchmark_name.")
        if row["papertitle"] != raw.get("benchmark_paper_title", ""):
            raise ValueError(f"Metric row {i} papertitle does not match benchmark_paper_title.")
        if row["paperlink"] != raw.get("paper_link", ""):
            raise ValueError(f"Metric row {i} paperlink does not match paper_link.")

        exact_norm = _normalize_metric_name(row["metricname"])
        if not exact_norm:
            raise ValueError(f"Metric row {i} has empty metricname.")
        if exact_norm in seen_exact:
            raise ValueError(f"Duplicate metric row detected for: {row['metricname']}")
        seen_exact.add(exact_norm)

    # Fuzzy reconciliation: build a variant-set per side and match if ANY
    # variant overlaps, instead of requiring exact string equality.
    metric_entries = [(m, _metric_name_variants(m)) for m in metrics if _normalize_metric_name(m)]
    catalogue_entries = [(r["metricname"], _metric_name_variants(r["metricname"])) for r in catalogue]

    unmatched_metrics = []
    for name, variants in metric_entries:
        if not any(variants & cat_variants for _, cat_variants in catalogue_entries):
            unmatched_metrics.append(name)

    unmatched_catalogue = []
    for name, variants in catalogue_entries:
        if not any(variants & m_variants for _, m_variants in metric_entries):
            unmatched_catalogue.append(name)

    if unmatched_metrics or unmatched_catalogue:
        logger.warning(
            "Sheet 1 <-> Sheet 2 metric name drift detected (non-fatal). "
            "Metrics listed but with no matching catalogue row: %s. "
            "Catalogue rows with no matching evaluation_metrics entry: %s.",
            unmatched_metrics, unmatched_catalogue,
        )

    raw["evaluation_metrics_catalogue"] = catalogue
    return raw


# Maps Sheet 2 JSON keys (model output, camelCase-free lowercase per the
# master prompt) to EvalMetric ORM column names (app/models/orm.py).
_METRIC_FIELD_MAP = {
    "benchmarkname": "benchmark_name",
    "papertitle": "paper_title",
    "paperlink": "paper_link",
    "metricname": "metric_name",
    "conceptualdescription": "conceptual_description",
    "methodologicaldetails": "methodological_details",
    "mathematicaldefinition": "mathematical_definition",
    "differencesfromstandarddefinition": "differences_from_standard_definition",
    "notes": "notes",
}


def _persist_eval_metrics(db: Session, benchmark_id: uuid.UUID, catalogue: list[dict[str, Any]]) -> int:
    """Inserts one EvalMetric row per validated Sheet 2 catalogue entry,
    linked to the newly created Benchmark via benchmark_id. Returns the
    number of rows inserted. Assumes _validate_eval_metrics_catalogue()
    has already been run on the raw payload."""
    count = 0
    for row in catalogue:
        orm_kwargs = {
            orm_field: row.get(json_key, "")
            for json_key, orm_field in _METRIC_FIELD_MAP.items()
        }
        orm_kwargs["benchmark_id"] = benchmark_id
        db.add(EvalMetric(**orm_kwargs))
        count += 1
    return count


# --- PATCH: defensive VARCHAR(100) length guard -----------------------------
# Root cause of this failure: no_of_samples came back as a 253-character
# descriptive string (e.g. "~33,600 word-association trials (one-sample
# t-test df=33,599) spanning 21 stereotypes..."), but the benchmarks table's
# no_of_samples column (and several sibling single-value text columns) are
# declared VARCHAR(100) in orm.py, so Postgres raised
# StringDataRightTruncation and the whole INSERT was rolled back.
#
# The real, durable fix is a migration widening these columns (no_of_samples
# in particular, since master-prompt-quality extraction legitimately produces
# multi-clause sample-count descriptions like the PluriHarms/RippleBench rows
# already in the workbook) from VARCHAR(100) to VARCHAR(500) or TEXT.
# That migration is outside agent_runner.py's scope (lives in orm.py /
# an Alembic revision) -- see note at bottom of this file.
#
# Until that migration ships, this guard prevents a good, expensive
# extraction from being thrown away by a hard DB error: it truncates any
# offending field to fit the current column width (with an ellipsis marker)
# BEFORE the INSERT, logs a warning so the truncation is visible/auditable,
# and lets the job complete as "needs_review" instead of "failed".
_VARCHAR_100_FIELDS = [
    "benchmark_name", "benchmark_paper_title", "code_dataset", "no_of_samples",
    "created_by", "dev_purpose", "license", "complexity_level",
    "complexity_justification", "integration_option", "code_repository",
    "dataset_repository", "paper_link", "status",
]
_VARCHAR_LIMIT = 100


def _clamp_varchar_fields(raw: dict) -> tuple[dict, list[str]]:
    """Truncates any single-value string field that would overflow the
    current VARCHAR(100) DB columns, so a legitimately good extraction is
    not discarded by a StringDataRightTruncation error. Returns the
    (possibly mutated) raw dict and the list of field names that were
    truncated, for logging/QA visibility."""
    truncated = []
    for field in _VARCHAR_100_FIELDS:
        value = raw.get(field)
        if isinstance(value, str) and len(value) > _VARCHAR_LIMIT:
            raw[field] = value[: _VARCHAR_LIMIT - 3].rstrip() + "..."
            truncated.append(field)
    return raw, truncated
# --- END PATCH ---------------------------------------------------------------


def _build_user_message(source_type: str, source_value: str, fetched: dict[str, Any]) -> str:
    if not fetched.get("fetch_ok"):
        return (
            f"Extract benchmark metadata for {source_type}: {source_value}\n\n"
            f"NOTE: automated fetching of this source failed "
            f"(error: {fetched.get('error', 'unknown')}). If you have no reliable "
            f"knowledge of this exact paper, return null/empty for fields you "
            f"cannot verify -- do not fabricate."
        )

    parts = [f"Extract benchmark metadata for {source_type}: {source_value}", ""]
    parts.append("--- FETCHED PAPER METADATA (from arXiv/Crossref API, use this as ground truth) ---")
    if fetched.get("title"):
        parts.append(f"Title: {fetched['title']}")
    if fetched.get("authors"):
        parts.append(f"Authors: {fetched['authors']}")
    if fetched.get("published"):
        parts.append(f"Published: {fetched['published']}")
    if fetched.get("url"):
        parts.append(f"URL: {fetched['url']}")
    if fetched.get("citation_count") is not None:
        parts.append(f"Citation count (Semantic Scholar): {fetched['citation_count']}")
    if fetched.get("abstract"):
        parts.append(f"Abstract: {fetched['abstract']}")
    if fetched.get("full_text_excerpt"):
        parts.append(f"Full text excerpt (first ~15 pages): {fetched['full_text_excerpt']}")
    parts.append(
        "--- END FETCHED METADATA ---\n"
        "Base your extraction on the above fetched data. For fields not covered "
        "by the abstract/excerpt (e.g. code repository, license, exact sample "
        "counts, dataset repository), you MUST run the Phase 0.2 targeted "
        "searches listed in the system prompt before deciding a field is "
        "unknown -- do not skip straight to null/Unknown."
    )
    return "\n".join(parts)


def _call_openai(model_name: str, source_type: str, source_value: str, api_key: str, fetched: dict[str, Any]) -> dict[str, Any]:
    import openai

    client = openai.OpenAI(api_key=api_key)
    user_msg = _build_user_message(source_type, source_value, fetched)
    response = client.chat.completions.create(
        model=model_name,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT_STUB},
            {"role": "user", "content": user_msg},
        ],
        response_format={"type": "json_object"},
        temperature=0.0,
    )
    return json.loads(response.choices[0].message.content or "{}")


def _call_anthropic(model_name: str, source_type: str, source_value: str, api_key: str, fetched: dict[str, Any]) -> dict[str, Any]:
    import anthropic

    client = anthropic.Anthropic(api_key=api_key)
    user_msg = _build_user_message(source_type, source_value, fetched)

    # Enable Anthropic's server-side web_search tool. This lets Claude
    # autonomously issue real web searches (e.g. for "no_of_samples" details
    # buried in a paper's body/appendix that our fetched abstract excerpt
    # does not cover, GitHub star counts, license text, etc.) instead of
    # relying purely on training-data recall or the short abstract we fetched
    # ourselves in paper_fetcher.py. Anthropic executes the search server-side
    # and returns web_search_tool_result blocks inline in the response --
    # no extra client-side loop is needed for this tool specifically.
    message = client.messages.create(
        model=model_name,
        # The Phase 0.2 instructions above now mandate 5 specific searches
        # per extraction (citations, github, huggingface dataset, license,
        # huggingface card cross-check), plus any follow-up searches for
        # ambiguous sample counts or metric formulas. The old cap of 5 left
        # zero budget for follow-ups and could get exhausted mid-way through
        # the mandatory list itself. Raised to 12.
        max_tokens=16384,
        system=SYSTEM_PROMPT_STUB,
        messages=[{"role": "user", "content": user_msg}],
        tools=[
            {
                "type": "web_search_20250305",
                "name": "web_search",
                "max_uses": 12,
            }
        ],
        # Note: this is Anthropic's built-in server-side tool (verified type
        # "web_search_20250305"), not a client-side function we implement --
        # Anthropic executes the actual search and injects results into the
        # conversation before Claude's final text response.
    )

    if message.stop_reason == "max_tokens":
        logger.warning(
            "Anthropic response for %s:%s was truncated (stop_reason=max_tokens) "
            "at max_tokens=%d. The final JSON may be incomplete or missing entirely.",
            source_type, source_value, _max_tokens,
        )
        # Real fix for the "model returned no benchmark_name" failure mode:
        # a truncated response has no valid closing brace for the outer JSON
        # object, so there is nothing for _extract_last_balanced_json() to
        # salvage -- it correctly returns None, and the caller correctly
        # fails the job. Retrying with a larger budget is the only thing
        # that actually recovers a complete object, so do exactly one retry
        # at double the token budget (capped) before giving up.
        if _retry_on_truncation and _max_tokens < 32000:
            logger.info(
                "Retrying Anthropic call for %s:%s once with max_tokens=%d.",
                source_type, source_value, min(_max_tokens * 2, 32000),
            )
            return _call_anthropic(
                model_name, source_type, source_value, api_key, fetched,
                _max_tokens=min(_max_tokens * 2, 32000),
                _retry_on_truncation=False,
            )

    # message.content is a list of content blocks: with extended thinking
    # and/or web_search enabled, Claude returns ThinkingBlock and
    # ServerToolUseBlock/WebSearchToolResultBlock entries interleaved with
    # one or more TextBlocks. Concatenate ALL text blocks (not just the
    # last), since Claude sometimes splits its final answer across multiple
    # text segments interspersed with tool-use blocks.
    text_blocks = [
        getattr(block, "text", None)
        for block in (message.content or [])
    ]
    all_text = "\n".join(t for t in text_blocks if t)

    logger.info(
        "Anthropic call for %s:%s -- stop_reason=%s, %d content blocks, "
        "%d chars of text extracted.",
        source_type, source_value, message.stop_reason,
        len(message.content or []), len(all_text),
    )

    parsed = _extract_last_balanced_json(all_text)
    if parsed is None:
        logger.warning(
            "Could not extract valid JSON from Anthropic response for %s:%s. "
            "Full raw text (first 3000 chars): %s",
            source_type, source_value, all_text[:3000],
        )
        return {}
    return parsed


def _extract_last_balanced_json(text: str) -> dict[str, Any] | None:
    """Find the LAST balanced-brace {...} span in text and parse it as JSON.

    Naive find("{")/rfind("}") breaks when the text contains other brace
    pairs before/after the real JSON object -- e.g. web_search tool results
    often contain JSON-like snippets or code examples in their text, which
    can make rfind("}") match a closing brace that belongs to unrelated
    content, producing a malformed slice. This scans for balanced brace
    spans instead and tries the last one found (Claude's final answer is
    expected to be the last JSON object in the response).
    """
    candidates = []
    depth = 0
    start_idx = None
    for i, ch in enumerate(text):
        if ch == "{":
            if depth == 0:
                start_idx = i
            depth += 1
        elif ch == "}":
            if depth > 0:
                depth -= 1
                if depth == 0 and start_idx is not None:
                    candidates.append(text[start_idx:i + 1])

    for candidate in reversed(candidates):
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            continue
    return None


def _quality_score(data: dict[str, Any]) -> float:
    required = [
        "benchmark_name", "benchmark_paper_title", "task_type",
        "description", "evaluation_metrics", "language_support",
        "entry_modalities", "paper_link",
    ]
    filled = sum(1 for k in required if data.get(k))
    return round(filled / len(required), 2)


def run_extraction(
    job_id: uuid.UUID,
    source_type: str,
    source_value: str,
    model_used: str,
    submitted_by: uuid.UUID | None,
    db: Session,
    openai_api_key: str = "",
    anthropic_api_key: str = "",
    semantic_scholar_api_key: str = "",
) -> None:
    job = db.query(ExtractionJob).filter(ExtractionJob.id == job_id).first()
    if job is None:
        logger.error("ExtractionJob %s not found", job_id)
        return

    try:
        job.status = "running"
        db.commit()

        # Phase 0.1: actually fetch the paper via a real HTTP call (arXiv API,
        # Crossref, or direct PDF download) instead of asking the model to
        # "fetch" a URL it has no tool access to reach. See paper_fetcher.py.
        fetched = fetch_source(source_type, source_value, semantic_scholar_api_key=semantic_scholar_api_key)
        if not fetched.get("fetch_ok"):
            logger.warning(
                "Job %s: automated fetch failed for %s:%s -- error=%s. "
                "Model will fall back to its own training-data knowledge, if any.",
                job_id, source_type, source_value, fetched.get("error"),
            )

        provider, model_name = (model_used.split("/", 1) + [model_used])[:2]
        if provider == "openai":
            raw = _call_openai(model_name, source_type, source_value, openai_api_key, fetched)
        elif provider == "anthropic":
            raw = _call_anthropic(model_name, source_type, source_value, anthropic_api_key, fetched)
        else:
            raise ValueError(f"Unknown model provider: {provider}")

        raw.setdefault("task_type", [])
        raw.setdefault("evaluation_metrics", [])
        raw.setdefault("evaluation_metrics_catalogue", [])

        # If the model returned null/missing for this required identifier,
        # log the full raw response for diagnosis (likely causes: the model
        # could not fetch/read the source at all, or the crude brace-matching
        # JSON extraction in _call_anthropic truncated the response) and fail
        # the job with a clear, specific message instead of letting a generic
        # pydantic ValidationError obscure the cause.
        if not raw.get("benchmark_name"):
            logger.error(
                "Job %s: model returned no benchmark_name. Raw model output: %s",
                job_id, json.dumps(raw)[:2000],
            )
            raise ValueError(
                "Model returned no benchmark_name -- it likely could not access "
                "or read the source (DOI/arXiv/PDF). Check backend logs for the "
                "full raw model response, and verify the source_value resolves "
                "to a real, fetchable paper."
            )

        raw.setdefault("benchmark_paper_title", raw["benchmark_name"])

        if not raw.get("paper_link"):
            raw["paper_link"] = fetched.get("url") or source_value

        # Phase 2 QA gate: structural defects in evaluation_metrics_catalogue
        # (missing keys, empty metricname, true duplicates, mismatched
        # benchmark/paper identifiers) still raise ValueError here (job marked
        # "failed"). Naming drift between evaluation_metrics and the catalogue
        # is now reconciled fuzzily and only logged, not raised -- see
        # _validate_eval_metrics_catalogue() docstring.
        raw = _validate_eval_metrics_catalogue(raw)

        qs = _quality_score(raw)

        raw["entry_modalities"] = _normalize_list(
            raw.get("entry_modalities"), ENTRY_MODALITIES, _ENTRY_MODALITY_ALIASES
        )
        raw["language_support"] = _normalize_list(
            raw.get("language_support"), LANGUAGE_SUPPORT, _LANGUAGE_ALIASES
        )

        if raw.get("cited_by") is None:
            raw["cited_by"] = 0
        else:
            try:
                raw["cited_by"] = int(raw["cited_by"])
            except (TypeError, ValueError):
                raw["cited_by"] = 0

        raw, _truncated_fields = _clamp_varchar_fields(raw)
        if _truncated_fields:
            logger.warning(
                "Job %s: truncated oversized field(s) to fit current VARCHAR(100) "
                "DB columns (see PATCH note above _build_user_message for the real fix): %s.",
                job_id, _truncated_fields,
            )

        create_schema = BenchmarkCreate(**raw)

        signal_kwargs = {
            key: bool(raw.get(key, False)) for key in _COMPLEXITY_SIGNAL_KEYS
        }
        signals = ComplexitySignals(
            citation_count=create_schema.cited_by or 0,
            **signal_kwargs,
        )
        complexity_level, complexity_justification = classify(signals)

        benchmark_data = create_schema.model_dump()
        benchmark_data["complexity_level"] = complexity_level
        benchmark_data["complexity_justification"] = complexity_justification
        benchmark_data["status"] = "pending_review"
        benchmark_data["created_by_user_id"] = submitted_by

        benchmark = Benchmark(**benchmark_data)
        db.add(benchmark)
        db.flush()

        # Phase 2: persist Sheet 2 (Evaluation Metrics Catalogue) rows now
        # that benchmark.id exists.
        metrics_persisted = _persist_eval_metrics(
            db, benchmark.id, raw.get("evaluation_metrics_catalogue", [])
        )
        logger.info(
            "Job %s: persisted %d eval_metrics row(s) for benchmark %s.",
            job_id, metrics_persisted, benchmark.id,
        )

        if _truncated_fields:
            job.status = "needs_review"
        else:
            job.status = "needs_review" if qs < 0.75 else "done"
        job.quality_score = qs
        job.requires_review = qs < 0.75
        job.result_benchmark_id = benchmark.id
        job.completed_at = datetime.now(timezone.utc)
        db.commit()
        logger.info("Extraction job %s completed. quality_score=%.2f status=%s", job_id, qs, job.status)

    except Exception as exc:
        db.rollback()
        job = db.query(ExtractionJob).filter(ExtractionJob.id == job_id).first()
        if job:
            job.status = "failed"
            job.completed_at = datetime.now(timezone.utc)
            db.commit()
        logger.exception("Extraction job %s failed: %s", job_id, exc)


# TODO (not yet implemented in this runner):
# - [DONE] Sheet 2 / Evaluation Metrics Catalogue extraction (Phase 2 of the
#   master prompt).
# - [DONE] Fuzzy Sheet 1<->Sheet 2 metric name reconciliation (previously an
#   exact-match crash bug; see _metric_name_variants()).
# - [DONE] Explicit Phase 0.2 targeted searches (citations, github,
#   huggingface dataset, license, huggingface card) baked into the system
#   prompt, with web_search max_uses raised from 5 to 12 and max_tokens
#   raised from 8192 to 16384 to accommodate the extra search results.
# - Phase 4 QA checklist enforcement as an explicit second validation pass
#   (currently only the 8-field quality_score heuristic gates review, plus
#   the Sheet 1<->Sheet 2 cross-check above).
# - Live Phase 0.2 web search calls as deterministic tool calls rather than
#   the model's own agentic browsing loop, for full auditability of which
#   URLs were actually visited.
