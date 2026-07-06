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
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.core.complexity_classifier import ComplexitySignals, classify
from app.core.paper_fetcher import fetch_source
from app.models.orm import Benchmark, ExtractionJob
from app.schemas.benchmark import BenchmarkCreate

logger = logging.getLogger(__name__)

# These two vocabularies are constrained to the ACTUAL enum values declared in
# backend/app/schemas/benchmark.py (EntryModality, LanguageSupport), which are
# narrower than the master prompt's Appendix 1A MODALITY_KEYWORDS and the
# unrestricted ISO 639-1 Language column. The master prompt's Appendix 1A
# Section 2 also lists Posts, Location Templates, Stories, Comments, and
# Anecdotes as valid modalities, and its Language column accepts any ISO
# 639-1 code -- neither is supported by the current Pydantic/Postgres enum,
# so this is a known template gap. Extend EntryModality/LanguageSupport in
# benchmark.py (and the corresponding Postgres ENUM in orm.py) first if you
# need those additional values; do not just add them here, since the DB
# enum type would reject them at insert time.
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

# This is the master prompt's Role & Context, Phase 0 research steps, Phase 1
# Sheet 1 column definitions and controlled vocabulary, and the Phase 3
# complexity decision tree, condensed into a single-call system prompt and
# adapted from the Excel-workbook output format to a single JSON object
# matching BenchmarkCreate. Sheet 2 (Evaluation Metrics Catalogue) extraction
# and the Phase 4 QA checklist / Phase 5 Excel generation are NOT yet wired
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
2. Search for supplementary information: citation count (Semantic Scholar /
   Google Scholar), code repository (GitHub), dataset availability
   (HuggingFace), and license.
3. Read systematically in this order: Abstract -> Introduction -> Related Work
   -> Benchmark Design -> Dataset Construction -> Evaluation Methodology ->
   Results -> Appendix. Pay special attention to sections titled "Metrics",
   "Evaluation", "Methodology", dataset statistics tables, footnotes, and
   appendices.

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
code_dataset: "Yes" if a code repository or dataset was found and verified,
  else "No".
no_of_samples: total instances/prompts/examples as a string with units, e.g.
  "15000 ratings (150 prompts x 100 annotators)", sourced from the dataset
  statistics table or repository, or null if unknown.
created_by: "Human", "Machine", or "Hybrid" based on CREATED_BY_KEYWORDS below.
entry_modalities: list of one or more values from ENTRY_MODALITIES below (ONLY
  these exact values are valid, do not invent new ones).
dev_purpose: "Eval", "Train", or "Train & Eval" based on DEVELOPMENT_PURPOSE
  keywords below.
license: e.g. "MIT", "Apache 2.0", "CC-BY 4.0", "CC0", "Custom Research",
  or "Unknown" if not found after searching.
evaluation_metrics: list of ALL evaluation metrics named or defined in the
  paper, using the paper's own exact terminology.
language_support: list of one or more values from LANGUAGE_SUPPORT below (ONLY
  these exact values are valid; use "Multilingual" if more than 5 languages
  are covered).
integration_option: "API", "Export", "API & Export", or "NA" based on
  INTEGRATION_KEYWORDS below (check both GitHub and HuggingFace signals).
citation_range: leave null; the platform computes this separately.
cited_by: integer citation count from Semantic Scholar/Google Scholar. Use 0
  if truly unknown -- NEVER return null for this field.
code_repository: verified GitHub URL, or null if not found.
dataset_repository: verified HuggingFace/dataset URL, or null if not found.
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

Return ONLY a single JSON object with the fields above (benchmark fields plus
the complexity signal booleans). No prose, no markdown, no code fences.
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
        "counts), use your own knowledge if you recognize this paper, otherwise "
        "return null rather than guessing."
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
    return json.loads(response.choices[0].message.content or "{{}}")


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
        # web_search results get injected into context and consume a lot of
        # tokens before Claude produces its final JSON answer. 4096 was too
        # low and caused stop_reason="max_tokens" truncation, so the model's
        # response was cut off before any JSON was emitted at all (raw ended
        # up as {} downstream). Raised to 8192 to give enough room for
        # multiple search results plus the full structured JSON output.
        max_tokens=8192,
        system=SYSTEM_PROMPT_STUB,
        messages=[{"role": "user", "content": user_msg}],
        tools=[
            {
                "type": "web_search_20250305",
                "name": "web_search",
                "max_uses": 5,
            }
        ],
        # Note: this is Anthropic's built-in server-side tool (verified type
        # "web_search_20250305"), not a client-side function we implement --
        # Anthropic executes the actual search and injects results into the
        # conversation before Claude's final text response.
    )

    if message.stop_reason == "max_tokens":
        logger.warning(
            "Anthropic response for %s:%s was truncated (stop_reason=max_tokens). "
            "The final JSON may be incomplete or missing entirely.",
            source_type, source_value,
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
    """Find the LAST balanced-brace {{...}} span in text and parse it as JSON.

    Naive find("{{")/rfind("}}") breaks when the text contains other brace
    pairs before/after the real JSON object -- e.g. web_search tool results
    often contain JSON-like snippets or code examples in their text, which
    can make rfind("}}") match a closing brace that belongs to unrelated
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

        qs = _quality_score(raw)

        raw.setdefault("task_type", [])
        raw.setdefault("evaluation_metrics", [])

        # If the model returned null/missing for these two required string
        # fields, log the full raw response for diagnosis (likely causes:
        # the model could not fetch/read the source at all, or the crude
        # brace-matching JSON extraction in _call_anthropic truncated the
        # response) and fail the job with a clear, specific message instead
        # of letting a generic pydantic ValidationError obscure the cause.
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
# - Sheet 2 / Evaluation Metrics Catalogue extraction (Phase 2 of the master
#   prompt): for every metric in evaluation_metrics, generate a full
#   EvalMetric row (conceptual_description, methodological_details,
#   mathematical_definition, differences_from_standard_definition, notes)
#   using the 5-subcomponent structure specified in the master prompt.
# - Phase 4 QA checklist enforcement as an explicit second validation pass
#   (currently only the 8-field quality_score heuristic gates review).
# - Live Phase 0.2 web search calls (Semantic Scholar / GitHub / HuggingFace)
#   as deterministic tool calls, rather than relying on the model's own
#   training data or built-in browsing for citation counts and repo URLs.
