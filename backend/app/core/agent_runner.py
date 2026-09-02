from __future__ import annotations

import json
import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session
from app.schemas.benchmark import BenchmarkCreate
from app.models.orm import Benchmark, EvalMetric, ExtractionJob, RepoStat, VocabTerm

from app.core.complexity_classifier import ComplexitySignals, classify
from app.core.paper_fetcher import fetch_source
from app.core.config import settings
from app.core.cost_tracking import estimate_cost_usd
from app.core.safety_dimension_classifier import classify_safety_dimensions
from app.core.use_case_classifier import classify_use_cases
from app.core.github_scrapper import fetch_github_stats
from app.core.hf_scrapper import fetch_hf_dataset_stats
from app.core.vocab_normalize import normalize_term, term_variants
from app.core.citation_range import compute_citation_range

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

# DEMOTED (2026-09-01): this used to be the live prompt vocabulary, and had
# already silently drifted from controlled_vocab.py's independent copy (the
# same class of bug fixed once before for USE_CASES -- Known Gap 19). It is
# now ONLY a fallback, used when VocabTerm has no active task_type rows
# (fresh DB before migration 0009's seed, or a DB error at fetch time). See
# _fetch_vocab_reference() and _build_system_prompt() below for the live path.
_FALLBACK_TASK_TYPES = [
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

# NEW (2026-09-01): small bootstrap set only -- the real evaluation_metric
# reference is expected to grow almost entirely from real extractions (see
# _upsert_vocab_terms below), since metric naming is intentionally
# paper-terminology-driven rather than a closed vocabulary.
_FALLBACK_EVAL_METRICS = [
    "Accuracy", "F1 Score", "Precision", "Recall", "Exact Match",
    "Attack Success Rate", "Refusal Rate", "BLEU", "ROUGE-L",
    "Mean Absolute Error (MAE)", "Spearman Correlation", "Pearson Correlation",
    "AUROC", "Win Rate", "Pass@k",
]

_VOCAB_REFERENCE_LIMIT = 150

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

# CHANGE (2026-09-01): added the INCLUSION RULE paragraph -- the direct fix
# for metrics being pulled from Related Work / literature-review mentions
# instead of the benchmark's own evaluation protocol. Also added the
# per-call KNOWN EVALUATION METRIC NAMES reference block, appended
# dynamically by _build_eval_metrics_instructions() below rather than baked
# into this fixed string.
EVAL_METRICS_EXTRACTION_INSTRUCTIONS_TEMPLATE = """
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

INCLUSION RULE (provenance-grounded -- this is the most important rule in
this section): only include a metric in evaluation_metrics /
evaluation_metrics_catalogue if the paper's OWN results for the benchmark
being introduced actually compute it -- a results table, a reported score,
or an explicit "we evaluate using X" statement tied to THIS benchmark's own
test items or protocol. Do NOT include a metric that appears only in:
  - Related Work / background discussion of how OTHER benchmarks or prior
    papers evaluate similar tasks,
  - motivation or introduction sections citing a metric by name without
    applying it here,
  - a passing mention of a metric family without a corresponding reported
    number for this benchmark.
Even a well-known, frequently-cited metric name (e.g. "F1", "BLEU") must be
excluded if you cannot point to where THIS paper actually reports a score
computed with it for THIS benchmark. Before finalizing your list, mentally
verify each metric against a specific table, figure, or section (e.g.
"Table 3", "Section 4.2 evaluation protocol") -- if you cannot identify
where it is actually used, remove it. Conversely, do not omit a real,
paper-defined metric because it does not resemble anything in the reference
list below -- a metric with genuinely no name in the paper should still be
extracted using a descriptive bracketed name (see Phase 5 Ambiguity Handling
in the master prompt), not dropped.

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
#
# CHANGE (2026-09-01): this is now a .format()-style TEMPLATE (placeholders
# {known_task_types} and {eval_metric_reference_block}) built per-call by
# _build_system_prompt(), instead of an f-string evaluated once at import
# time against the hardcoded KNOWN_TASK_TYPES constant. This is what makes
# the DB-backed vocabulary actually reach the model: every run now reflects
# the CURRENT VocabTerm table contents, not whatever was hardcoded when this
# module was last edited.
SYSTEM_PROMPT_TEMPLATE = """
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
task_type: list of one or more values, ideally from the KNOWN_TASK_TYPES
    reference below. INCLUSION RULE: only include a task type that this
    benchmark's OWN test items and evaluation protocol actually measure --
    not a related safety concern that is only discussed in the paper's
    motivation, background, or Related Work section without being part of
    what this benchmark itself tests. If the paper discusses adjacent risks
    it does not test, do not add them here. If the benchmark's true task
    type is not in the reference list, infer the closest genuinely-fitting
    new value rather than force-fitting an existing one.
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
evaluation_metrics: list of evaluation metrics ACTUALLY USED TO EVALUATE THIS
    BENCHMARK'S OWN RESULTS (see the detailed INCLUSION RULE in the Phase 2
    instructions below -- the same rule applies here; do not list a metric
    that is only named in Related Work or background discussion), using the
    paper's own exact terminology, consistently spelled the same way here as
    in evaluation_metrics_catalogue.
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

KNOWN_TASK_TYPES (reference sample from the live catalogue, NOT exhaustive and
NOT a closed enum -- reuse an existing value when it genuinely fits this
benchmark's own evaluation, but infer a new value when none of these do; do
not force-fit) = {known_task_types}

ENTRY_MODALITIES (controlled vocabulary, exact values only) = {entry_modalities}

LANGUAGE_SUPPORT (controlled vocabulary, exact values only) = {language_support}

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


# CHANGE (2026-09-01): these two are now thin wrappers around
# app/core/vocab_normalize.py's shared normalize_term()/term_variants(), so
# app/routers/vocab_terms.py's uniqueness check and this module's Sheet 1 <->
# Sheet 2 reconciliation and vocab-catalogue upsert all use the EXACT same
# normalization -- previously this logic was private to this file only.
def _normalize_metric_name(value: Any) -> str:
    return normalize_term(value)


def _metric_name_variants(value: Any) -> set[str]:
    return term_variants(value)


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
    linked to the Benchmark via benchmark_id. Returns the number of rows
    inserted. Assumes _validate_eval_metrics_catalogue() has already been
    run on the raw payload."""
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


_VARCHAR_100_FIELDS = [
    "benchmark_name", "benchmark_paper_title", "code_dataset",
    "created_by", "dev_purpose", "complexity_level",
    "integration_option", "code_repository",
    "dataset_repository", "paper_link", "status",
]
_VARCHAR_LIMIT = 100

# FIX (2026-09-01, carried over from an earlier session's patch, now applied):
# code_dataset/integration_option/complexity_level are declared as
# non-Optional enums with class-level defaults in BenchmarkBase (e.g.
# code_dataset: CodeDataset = CodeDataset.no). That default ONLY applies when
# the key is ABSENT from the dict passed to BenchmarkCreate(**raw) -- if the
# model returns the key explicitly set to null (because it could not confirm
# the value for this specific paper), Pydantic validates that literal None
# against the enum and raises ValidationError, crashing the whole job. See
# _pop_null_enum_defaults() below, called from run_extraction() right before
# BenchmarkCreate(**raw).
_ENUM_FIELDS_WITH_DEFAULTS = ("code_dataset", "integration_option", "complexity_level")


def _pop_null_enum_defaults(raw: dict) -> dict:
    for field in _ENUM_FIELDS_WITH_DEFAULTS:
        if raw.get(field) is None:
            raw.pop(field, None)
    return raw


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


def _build_user_message(source_type: str, source_value: str, fetched: dict[str, Any], has_search_tool: bool = True,) -> str:
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
    if has_search_tool:
        parts.append(
            "--- END FETCHED METADATA ---\n"
            "Base your extraction on the above fetched data. For fields not covered "
            "by the abstract/excerpt (e.g. code repository, license, exact sample "
            "counts, dataset repository), you MUST run the Phase 0.2 targeted "
            "searches listed in the system prompt before deciding a field is "
            "unknown -- do not skip straight to null/Unknown."
        )
    else:
        parts.append(
            "--- END FETCHED METADATA ---\n"
            "Base your extraction ENTIRELY on the fetched metadata above. You do "
            "NOT have access to any web search or browsing tool in this call -- do "
            "not attempt to invoke one, narrate searching, or describe search "
            "queries you would run. For any field not directly supported by the "
            "fetched title/abstract/excerpt above (e.g. code repository, license, "
            "exact sample counts, dataset repository), set that field to null or "
            "\"Unknown\" rather than guessing or attempting to search. Respond with "
            "the JSON object only -- no commentary, no search narration, no "
            "markdown code fences."
        )
    return "\n".join(parts)


def _parse_model_json_response(raw_text: str, log_label: str) -> dict[str, Any]:
    """Robustly parses a model's JSON response, tolerating the common
    failure modes seen across providers: markdown code fences (```json
    ... ```), leading/trailing prose, or an empty/whitespace body.

    Tries, in order:
    1. Direct json.loads() on the raw text (the happy path).
    2. Stripping a leading/trailing ```json or ``` fence, then
       json.loads() again.
    3. _extract_last_balanced_json() -- the same brace-matching
       fallback already used for Anthropic responses -- as a last
       resort for cases where the model wrapped valid JSON in
       explanatory prose without fences.

    Raises ValueError with a truncated preview of the raw text if all
    three attempts fail, so a failure is diagnosable from the
    persisted failure_reason (see ExtractionJob.failure_reason) instead
    of showing only Python's generic, uninformative
    "Expecting value: line 1 column 1 (char 0)" message.
    """
    text = (raw_text or "").strip()
    if not text:
        raise ValueError(
            f"{log_label}: model returned an empty response body. This is a "
            "known limitation with some models/providers (e.g. Ollama Cloud "
            "does not support structured outputs, and gpt-oss models have a "
            "documented incompatibility with the OpenAI SDK's "
            "response_format=json_object parameter due to their Harmony "
            "response format) rather than a prompt or extraction-logic bug."
        )

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    fence_stripped = re.sub(r"^```(?:json)?\s*", "", text)
    fence_stripped = re.sub(r"\s*```$", "", fence_stripped).strip()
    if fence_stripped != text:
        try:
            return json.loads(fence_stripped)
        except json.JSONDecodeError:
            pass

    balanced = _extract_last_balanced_json(text)
    if balanced is not None:
        return balanced

    preview = text[:300].replace("\n", " ")
    raise ValueError(
        f"{log_label}: could not parse a valid JSON object from the model's "
        f"response after trying direct parse, markdown-fence stripping, and "
        f"balanced-brace extraction. Response preview: {preview!r}"
    )


# CHANGE (2026-09-01): all three _call_* functions now take system_prompt as
# an explicit parameter instead of closing over the old module-level
# SYSTEM_PROMPT_STUB constant, since the prompt is now built per-call (with
# live DB vocabulary) by _build_system_prompt() in run_extraction().
def _call_openai(model_name: str, source_type: str, source_value: str, api_key: str, fetched: dict[str, Any], system_prompt: str) -> tuple[dict[str, Any], dict[str, int]]:
    import openai

    client = openai.OpenAI(api_key=api_key)
    user_msg = _build_user_message(source_type, source_value, fetched, has_search_tool=False)
    response = client.chat.completions.create(
        model=model_name,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_msg},
        ],
        response_format={"type": "json_object"},
        temperature=0.0,
    )
    usage = {
        "input_tokens": getattr(response.usage, "prompt_tokens", 0) or 0,
        "output_tokens": getattr(response.usage, "completion_tokens", 0) or 0,
    }
    return _parse_model_json_response(response.choices[0].message.content, "openai"), usage


def _call_ollama(
    model_name: str, source_type: str, source_value: str,
    base_url: str, api_key: str, fetched: dict[str, Any], system_prompt: str,
    _max_tokens: int = 8192, _retry_on_empty: bool = True,
) -> tuple[dict[str, Any], dict[str, int]]:
    """Calls an open-weight model (DeepSeek, Qwen, Kimi, gpt-oss, etc.)
    hosted on Ollama Cloud via its OpenAI-compatible
    /v1/chat/completions endpoint (https://ollama.com/v1 by default,
    see app/core/config.py's OLLAMA_BASE_URL_CLOUD). Reuses the same
    openai SDK as _call_openai -- Ollama's cloud and local APIs both
    speak this protocol, so no separate client library is needed.

    max_tokens is set explicitly and generously (8192, doubling once on
    retry) because gpt-oss models spend part of their token budget on
    internal chain-of-thought reasoning (their "Harmony" response
    format) before emitting a final answer -- if the budget runs out
    during that reasoning phase, the model returns an EMPTY response
    rather than a partial one. Mirrors _call_anthropic()'s existing
    retry-on-truncation pattern.
    """
    import openai

    if not base_url:
        raise ValueError(
            "OLLAMA_BASE_URL_CLOUD is not set -- cannot call an ollama/* "
            "model. Set it in backend/.env (default: https://ollama.com/v1)."
        )
    if not api_key:
        raise ValueError(
            "OLLAMA_API_KEY is not set -- Ollama Cloud requires an API "
            "key. Create one at https://ollama.com/settings/keys and set "
            "OLLAMA_API_KEY in backend/.env."
        )

    client = openai.OpenAI(base_url=base_url, api_key=api_key)
    user_msg = _build_user_message(source_type, source_value, fetched, has_search_tool=False)
    response = client.chat.completions.create(
        model=model_name,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_msg},
        ],
        max_tokens=_max_tokens,
        temperature=0.0,
    )

    content = response.choices[0].message.content
    finish_reason = getattr(response.choices[0], "finish_reason", None)

    if not (content or "").strip() and _retry_on_empty and _max_tokens < 32000:
        logger.warning(
            "Ollama call for %s:%s returned an empty response with "
            "max_tokens=%d (finish_reason=%s) -- likely exhausted its "
            "token budget on internal reasoning before emitting a final "
            "answer (a documented gpt-oss behavior). Retrying once with "
            "max_tokens=%d.",
            source_type, source_value, _max_tokens, finish_reason,
            min(_max_tokens * 2, 32000),
        )
        return _call_ollama(
            model_name, source_type, source_value, base_url, api_key, fetched, system_prompt,
            _max_tokens=min(_max_tokens * 2, 32000), _retry_on_empty=False,
        )

    usage = {
        "input_tokens": getattr(response.usage, "prompt_tokens", 0) or 0,
        "output_tokens": getattr(response.usage, "completion_tokens", 0) or 0,
    }
    return _parse_model_json_response(content, "ollama"), usage


def _call_anthropic(
    model_name: str, source_type: str, source_value: str, api_key: str, fetched: dict[str, Any], system_prompt: str,
    _max_tokens: int = 16384, _retry_on_truncation: bool = True,
) -> tuple[dict[str, Any], dict[str, int]]:
    import anthropic

    client = anthropic.Anthropic(api_key=api_key)
    user_msg = _build_user_message(source_type, source_value, fetched, has_search_tool=True)

    message = client.messages.create(
        model=model_name,
        max_tokens=_max_tokens,
        system=system_prompt,
        messages=[{"role": "user", "content": user_msg}],
        tools=[
            {
                "type": "web_search_20250305",
                "name": "web_search",
                "max_uses": 12,
            }
        ],
    )

    usage = {
        "input_tokens": getattr(message.usage, "input_tokens", 0) or 0,
        "output_tokens": getattr(message.usage, "output_tokens", 0) or 0,
    }

    if message.stop_reason == "max_tokens":
        logger.warning(
            "Anthropic response for %s:%s was truncated (stop_reason=max_tokens) "
            "at max_tokens=%d. The final JSON may be incomplete or missing entirely.",
            source_type, source_value, _max_tokens,
        )
        if _retry_on_truncation and _max_tokens < 32000:
            logger.info(
                "Retrying Anthropic call for %s:%s once with max_tokens=%d.",
                source_type, source_value, min(_max_tokens * 2, 32000),
            )
            retry_parsed, retry_usage = _call_anthropic(
                model_name, source_type, source_value, api_key, fetched, system_prompt,
                _max_tokens=min(_max_tokens * 2, 32000),
                _retry_on_truncation=False,
            )
            combined_usage = {
                "input_tokens": usage["input_tokens"] + retry_usage["input_tokens"],
                "output_tokens": usage["output_tokens"] + retry_usage["output_tokens"],
            }
            return retry_parsed, combined_usage

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
        return {}, usage
    return parsed, usage


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


def _wrap_provider_error(provider: str, model_name: str, exc: Exception) -> Exception:
    if provider == "ollama":
        try:
            import openai
            if isinstance(exc, openai.PermissionDeniedError):
                return ValueError(
                    f"Ollama Cloud rejected model '{model_name}': the current "
                    "account subscription tier does not include this model "
                    "(HTTP 403, 'this model requires a subscription'). "
                    "Upgrade at https://ollama.com/upgrade, then resubmit "
                    "this job."
                )
        except ImportError:
            pass
    return exc


def _fetch_vocab_reference(db: Session, category: str, fallback: list[str]) -> list[str]:
    """Fetches active, canonical VocabTerm entries for the given category,
    ordered by usage_count so the most-established terms surface first.
    Falls back to the hardcoded list (_FALLBACK_TASK_TYPES /
    _FALLBACK_EVAL_METRICS) if the DB has no active rows yet for this
    category (e.g. migration 0009 not yet applied) or the query fails for
    any reason -- extraction must never hard-fail just because the
    vocabulary table is temporarily empty or unreachable."""
    try:
        rows = (
            db.query(VocabTerm.term)
            .filter(
                VocabTerm.category == category,
                VocabTerm.is_active.is_(True),
                VocabTerm.is_canonical.is_(True),
            )
            .order_by(VocabTerm.usage_count.desc())
            .limit(_VOCAB_REFERENCE_LIMIT)
            .all()
        )
        terms = [r[0] for r in rows]
        return terms if terms else list(fallback)
    except Exception as exc:
        logger.warning(
            "Could not fetch vocab_terms for category=%s (falling back to "
            "hardcoded reference list): %s", category, exc,
        )
        return list(fallback)


def _build_eval_metrics_instructions(eval_metric_reference: list[str]) -> str:
    reference_block = ""
    if eval_metric_reference:
        reference_block = (
            "\n\nKNOWN EVALUATION METRIC NAMES SEEN IN THIS CATALOGUE SO FAR "
            "(reference sample, NOT exhaustive and NOT a closed vocabulary -- "
            "reuse an existing name from this list ONLY if the paper's metric "
            "is genuinely the same measure, for spelling/terminology "
            "consistency. Do NOT force-fit a metric name from this list onto "
            "a different measure, and do NOT omit or rename a real metric "
            "just because it is missing from this list -- new metric names "
            "are expected and correct as the catalogue grows):\n"
            f"{eval_metric_reference}"
        )
    return EVAL_METRICS_EXTRACTION_INSTRUCTIONS_TEMPLATE + reference_block


def _build_system_prompt(task_type_reference: list[str], eval_metric_reference: list[str]) -> str:
    """Builds the full system prompt for this specific extraction call,
    injecting the CURRENT DB vocabulary (task types and evaluation metric
    names) as reference material. Replaces the old module-level
    SYSTEM_PROMPT_STUB f-string, which baked in a hardcoded, since-drifted
    KNOWN_TASK_TYPES constant once at import time."""
    base = SYSTEM_PROMPT_TEMPLATE.format(
        known_task_types=task_type_reference,
        entry_modalities=ENTRY_MODALITIES,
        language_support=LANGUAGE_SUPPORT,
    )
    return base + "\n\n" + _build_eval_metrics_instructions(eval_metric_reference)


def _upsert_vocab_terms(db: Session, category: str, terms: list[str], benchmark_id: uuid.UUID | None) -> None:
    """Records every task_type / evaluation_metrics value from a
    successful extraction into VocabTerm, incrementing usage_count on a
    repeat or inserting a new row (source='agent') for a genuinely new
    term. Called AFTER the benchmark row is committed, never before a
    failed/crashed extraction, so a bad run cannot pollute the reference
    catalogue used to guide future extractions."""
    for term in terms or []:
        term = str(term).strip()
        if not term:
            continue
        normalized = normalize_term(term)
        existing = (
            db.query(VocabTerm)
            .filter(VocabTerm.category == category, VocabTerm.normalized_term == normalized)
            .first()
        )
        if existing:
            existing.usage_count = (existing.usage_count or 0) + 1
        else:
            db.add(VocabTerm(
                category=category,
                term=term,
                normalized_term=normalized,
                is_active=True,
                is_canonical=True,
                source="agent",
                first_seen_benchmark_id=benchmark_id,
                usage_count=1,
            ))


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
    reuse_benchmark_id: uuid.UUID | None = None,
) -> None:
    """reuse_benchmark_id: when set, this run UPDATES the existing
    Benchmark row with this id in place instead of inserting a new one.
    Used by app/routers/submissions.py's _run_reextraction_background()
    (admin re-extraction of a community submission) and
    app/routers/extraction.py's rerun_job() (admin re-running the Agent
    Extraction Panel on a job that already produced a benchmark). Fixes
    the bug where re-processing the same paper through the admin
    extraction pipeline created a duplicate catalogue entry instead of
    refreshing the one already under review.
    """
    job = db.query(ExtractionJob).filter(ExtractionJob.id == job_id).first()
    if job is None:
        logger.error("ExtractionJob %s not found", job_id)
        return

    try:
        job.status = "running"
        db.commit()

        # NEW (2026-09-01): fetch the live vocabulary BEFORE building the
        # system prompt, so every run reflects the current VocabTerm table
        # rather than a hardcoded constant frozen at import time.
        task_type_reference = _fetch_vocab_reference(db, "task_type", _FALLBACK_TASK_TYPES)
        eval_metric_reference = _fetch_vocab_reference(db, "evaluation_metric", _FALLBACK_EVAL_METRICS)
        system_prompt = _build_system_prompt(task_type_reference, eval_metric_reference)

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
        try:
            if provider == "openai":
                raw, usage = _call_openai(model_name, source_type, source_value, openai_api_key, fetched, system_prompt)
            elif provider == "anthropic":
                raw, usage = _call_anthropic(model_name, source_type, source_value, anthropic_api_key, fetched, system_prompt)
            elif provider == "ollama":
                raw, usage = _call_ollama(model_name, source_type, source_value, settings.OLLAMA_BASE_URL_CLOUD, settings.OLLAMA_API_KEY, fetched, system_prompt)
            else:
                raise ValueError(f"Unknown model provider: {provider}")
        except Exception as provider_exc:
            raise _wrap_provider_error(provider, model_name, provider_exc) from provider_exc

        raw.setdefault("task_type", [])
        raw.setdefault("evaluation_metrics", [])
        raw.setdefault("evaluation_metrics_catalogue", [])

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
        raw["citation_range"] = compute_citation_range(raw["cited_by"])

        raw = _pop_null_enum_defaults(raw)

        raw, _truncated_fields = _clamp_varchar_fields(raw)
        if _truncated_fields:
            logger.warning(
                "Job %s: truncated oversized field(s) to fit current VARCHAR(100) "
                "DB columns (see PATCH note above _build_user_message for the real fix): %s.",
                job_id, _truncated_fields,
            )

        github_stats = None
        hf_stats = None

        if raw.get("code_repository"):
            try:
                github_stats = fetch_github_stats(raw["code_repository"], github_token=settings.GITHUB_TOKEN)
                if github_stats.error is None:
                    if github_stats.license_spdx:
                        raw["license"] = github_stats.license_spdx
                    logger.info(
                        "Job %s: verified GitHub repo %s/%s -- stars=%d, activity=%s.",
                        job_id, github_stats.owner, github_stats.repo,
                        github_stats.stars, github_stats.activity_status,
                    )
                else:
                    logger.warning(
                        "Job %s: GitHub verification failed for %s: %s",
                        job_id, raw["code_repository"], github_stats.error,
                    )
            except Exception as exc:
                logger.warning("Job %s: github_scrapper raised %s -- continuing without it.", job_id, exc)

        if raw.get("dataset_repository"):
            try:
                hf_stats = fetch_hf_dataset_stats(raw["dataset_repository"], hf_token=settings.HF_TOKEN)
                if hf_stats.error is None:
                    if hf_stats.license_id and not raw.get("license"):
                        raw["license"] = hf_stats.license_id
                    logger.info(
                        "Job %s: verified HF dataset %s/%s -- likes=%d, activity=%s.",
                        job_id, hf_stats.owner, hf_stats.name,
                        hf_stats.likes, hf_stats.activity_status,
                    )
                else:
                    logger.warning(
                        "Job %s: HuggingFace verification failed for %s: %s",
                        job_id, raw["dataset_repository"], hf_stats.error,
                    )
            except Exception as exc:
                logger.warning("Job %s: hf_scrapper raised %s -- continuing without it.", job_id, exc)

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

        # FIX (2026-09-01, now actually applied): reuse_benchmark_id was
        # accepted as a parameter but never referenced anywhere in this
        # function body -- every run unconditionally created a new
        # Benchmark row. This is the direct fix for admin re-processing
        # creating a duplicate catalogue entry instead of updating the
        # benchmark already under review.
        existing_benchmark = None
        if reuse_benchmark_id is not None:
            existing_benchmark = (
                db.query(Benchmark).filter(Benchmark.id == reuse_benchmark_id).first()
            )
            if existing_benchmark is None:
                logger.warning(
                    "Job %s: reuse_benchmark_id=%s was requested but no "
                    "matching benchmark exists -- falling back to creating "
                    "a new benchmark row.",
                    job_id, reuse_benchmark_id,
                )

        if existing_benchmark is not None:
            for field, value in benchmark_data.items():
                if hasattr(existing_benchmark, field):
                    setattr(existing_benchmark, field, value)
            benchmark = existing_benchmark
            benchmark.use_cases = classify_use_cases(
                benchmark.task_type, benchmark.description, benchmark.benchmark_name
            )
            benchmark.safety_dimensions = classify_safety_dimensions(benchmark.task_type)
            db.flush()

            # Replace the previous run's Sheet 2 rows instead of appending on
            # top of them, so re-extraction never leaves stale metrics mixed
            # in with the fresh catalogue.
            db.query(EvalMetric).filter(EvalMetric.benchmark_id == benchmark.id).delete()
        else:
            benchmark_data["created_by_user_id"] = submitted_by
            benchmark = Benchmark(**benchmark_data)
            benchmark.use_cases = classify_use_cases(
                benchmark.task_type, benchmark.description, benchmark.benchmark_name
            )
            benchmark.safety_dimensions = classify_safety_dimensions(benchmark.task_type)
            db.add(benchmark)
            db.flush()

        metrics_persisted = _persist_eval_metrics(
            db, benchmark.id, raw.get("evaluation_metrics_catalogue", [])
        )
        logger.info(
            "Job %s: persisted %d eval_metrics row(s) for benchmark %s (reused=%s).",
            job_id, metrics_persisted, benchmark.id, existing_benchmark is not None,
        )

        if github_stats is not None and github_stats.error is None:
            db.add(RepoStat(
                id=uuid.uuid4(),
                benchmark_id=benchmark.id,
                source="github",
                url=raw["code_repository"],
                owner=github_stats.owner,
                name=github_stats.repo,
                stars_or_likes=github_stats.stars,
                forks=github_stats.forks,
                open_issues=github_stats.open_issues,
                contributors_count=github_stats.contributors_count,
                last_commit_at=github_stats.last_commit_at,
                days_since_last_activity=github_stats.days_since_last_commit,
                activity_status=github_stats.activity_status,
                is_archived=github_stats.is_archived,
                license_id=github_stats.license_spdx,
                fetch_error=github_stats.error,
                fetched_at=github_stats.fetched_at,
            ))

        if hf_stats is not None and hf_stats.error is None:
            db.add(RepoStat(
                id=uuid.uuid4(),
                benchmark_id=benchmark.id,
                source="hf_dataset",
                url=raw.get("dataset_repository") or "",
                owner=hf_stats.owner,
                name=hf_stats.name,
                stars_or_likes=hf_stats.likes,
                downloads=hf_stats.downloads,
                last_commit_at=hf_stats.last_modified_at,
                days_since_last_activity=hf_stats.days_since_last_modified,
                activity_status=hf_stats.activity_status,
                is_private=hf_stats.is_private,
                is_gated=hf_stats.is_gated,
                license_id=hf_stats.license_id,
                fetch_error=hf_stats.error,
                fetched_at=hf_stats.fetched_at,
            ))

        # NEW (2026-09-01): grow the reference vocabulary from this
        # successful extraction, AFTER the benchmark row exists (so
        # first_seen_benchmark_id is valid) and only on the success path
        # (a failed/crashed job never reaches here, so it cannot pollute
        # future prompts with bad terms).
        _upsert_vocab_terms(db, "task_type", benchmark.task_type, benchmark.id)
        _upsert_vocab_terms(db, "evaluation_metric", benchmark.evaluation_metrics, benchmark.id)

        if _truncated_fields:
            job.status = "needs_review"
        else:
            job.status = "needs_review" if qs < 0.75 else "done"
        job.quality_score = qs
        job.requires_review = qs < 0.75
        job.result_benchmark_id = benchmark.id
        job.completed_at = datetime.now(timezone.utc)

        job.input_tokens = usage.get("input_tokens")
        job.output_tokens = usage.get("output_tokens")
        job.estimated_cost_usd = estimate_cost_usd(
            model_used, usage.get("input_tokens"), usage.get("output_tokens")
        )

        db.commit()
        logger.info("Extraction job %s completed. quality_score=%.2f status=%s", job_id, qs, job.status)

    except Exception as exc:
        db.rollback()
        job = db.query(ExtractionJob).filter(ExtractionJob.id == job_id).first()
        if job:
            job.status = "failed"
            job.completed_at = datetime.now(timezone.utc)
            job.failure_reason = str(exc)[:2000]
            db.commit()
        logger.exception("Extraction job %s failed: %s", job_id, exc)