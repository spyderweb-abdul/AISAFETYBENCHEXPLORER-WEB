# AISafetyBenchExplorer Web Scaling - Project Roadmap

Status document. Last updated: 2026-09-04.

This file is the canonical memory reference for this Space. Consult it
first in every future session before proposing new work. Update it
whenever scope, phases, or architecture decisions change.

IMPORTANT: this file was reset to a lean, forward-looking format on
2026-09-02. The full session-by-session history through 2026-08-28
(including the original detailed rationale for every fix listed as
"resolved" below) was NOT deleted -- it lives in
PROJECT_ROADMAP_ARCHIVE.md (rename the previous PROJECT_ROADMAP.md to
this filename; its content was left untouched to avoid any risk of
losing detail during this reorganization). Consult the archive when you
need the full "why" behind a past decision; consult this file for
"what is the current state and what is still open."

---

## 1. Project Background

AISafetyBenchExplorer is a workbook-backed catalogue of 195+ AI safety
benchmarks for LLMs, plus a Python extraction toolkit
(github.com/spyderweb-abdul/AISAFETYBENCHEXPLORER). It has three
extraction pipelines: a DOI-based API pipeline, a Master Prompt for
AI-agent extraction, and a legacy PDF pipeline. Complexity
classification (Popular, High, Medium, Low) follows the decision tree
in complexity-methodology.md.

The web app lives in a separate repository,
github.com/spyderweb-abdul/AISAFETYBENCHEXPLORER-WEB, kept distinct
from the original pipeline repository.

---

## 2. Current Architecture

- Database: PostgreSQL, migrated via Alembic (current head:
  0009_add_vocab_terms)
- Backend: FastAPI, SQLAlchemy ORM, Pydantic v2 schemas
- Task queue: Celery + Redis (weekly citation refresh, repo stats
  refresh)
- Frontend: Next.js (App Router) + React, TypeScript
- Auth: JWT, admin and researcher roles
- Agent-as-orchestrator: a tool-using LLM (OpenAI, Anthropic, or an
  Ollama Cloud open-weight model) runs a condensed version of
  AISafety_Benchmark_Extraction_Master_Prompt.md as its system prompt
  (see backend/app/core/agent_runner.py), with deterministic tool
  calls (Semantic Scholar, GitHub, HuggingFace) feeding numeric fields
  that drive complexity classification.

### Key tables

| Table | Purpose |
|---|---|
| benchmarks | Sheet 1 -- one row per catalogued benchmark |
| eval_metrics | Sheet 2 -- one row per metric per benchmark |
| repo_stats | Append-only history of GitHub/HuggingFace activity snapshots |
| extraction_jobs | One row per admin-triggered agent extraction run |
| submissions | One row per researcher-submitted community DOI |
| notifications | Per-user in-app inbox |
| model_options | Admin-managed catalogue of models offered in extraction dropdowns |
| vocab_terms | Admin-managed, agent-grown catalogue of task_type / evaluation_metric terms |
| audit_log | Generic before/after diff log for benchmarks, vocab_terms, model_options |

---

## 3. Phase Status Summary

| Phase | Status |
|---|---|
| 1 -- Foundation | DONE |
| 2 -- Admin CRUD Panel | DONE |
| 2b -- Eval Metrics Catalogue UI | DONE |
| 3 -- Agent Orchestration Layer | LIVE, iterating on extraction quality |
| 4 -- Repo Activity Statistics | DONE |
| 5 -- Researcher Dashboard (/browse) | SUBSTANTIALLY COMPLETE |
| 6 -- Community and Governance | LIVE (submissions, notifications, version history, citation refresh) |
| 7 (informal) -- Admin catalogue management (models, vocab) | DONE, this session |

---

## 4. Non-Negotiable Principles

- Pipeline code is imported as a package, never rewritten from scratch
- All DB schema and exports remain compatible with the Excel template
  so the workbook and web app can coexist during transition
- No non-printable Unicode characters in any DB field, API response,
  or frontend-rendered text
- No long dashes in any generated text or code within this project
- A threshold or controlled vocabulary must have exactly ONE source of
  truth. This project has hit "the same constant hardcoded in two
  places, silently drifts" bugs repeatedly (KNOWN_TASK_TYPES,
  USE_CASES, POPULAR_CITATION_THRESHOLD each independently). Before
  adding any new configurable value, grep for existing usages first.

---

## 5. Resolved This Session (2026-09-01 to 2026-09-04)

Full rationale for each item lives in PROJECT_ROADMAP_ARCHIVE.md and
in this session's own conversation history. Summary only, so future
sessions know what NOT to re-investigate from scratch:

- Admin re-processing a submitted job created a duplicate benchmark
  instead of updating the existing one. Fixed via a
  reuse_benchmark_id parameter threaded through
  agent_runner.run_extraction(), wired into the submissions
  re-extract flow and a new POST /extraction/jobs/{id}/rerun
  endpoint.
- BenchmarkCreate crashed with a Pydantic enum ValidationError when
  the model returned code_dataset/integration_option explicitly as
  null. Fixed by popping null enum fields before validation so their
  class defaults apply.
- Admin extraction and submission re-extract dropdowns were limited to
  2-11 hardcoded models. Replaced with a model_options DB table,
  full CRUD (/admin/models), and both dropdowns now fetch live.
- The extraction agent sometimes included evaluation metrics/task
  types only mentioned in Related Work, not actually used to evaluate
  the benchmark. Fixed with an explicit provenance-grounded INCLUSION
  RULE in the extraction prompt, plus a vocab_terms DB table
  (task_type and evaluation_metric categories) that the prompt now
  references as a growing, non-enforced guidance sample, with new
  terms auto-upserted after every successful extraction.
- Notification "View" links 404'd for admins
  (/admin/submissions/{id}, a route that never existed) and appeared
  inert for submitters (/submit with no identifier). Fixed with
  ?highlight={id} query-param deep links and matching
  scroll-and-highlight behavior on both pages.
- The Popular complexity threshold was hardcoded at 100 citations in
  three independent places (complexity_classifier.py,
  app/core/tasks.py's weekly citation refresh job, and
  complexity-methodology.md, which itself internally disagreed with
  itself -- 100 in one section, 1000 in another). Consolidated to a
  single Settings.POPULAR_CITATION_THRESHOLD (default 500,
  env-overridable), read by every consumer.
- citation_range was a free-text field nobody populated. Added
  compute_citation_range(), wired into both the manual admin save
  path and the extraction pipeline, so it is always server-derived
  from cited_by.
- ComplexityBadge had no way to show the classification reason.
  Added an optional justification prop rendered as a tooltip; wired
  into /browse, /browse/[id], and the admin benchmark form.
- The admin Task Type panel was a checkbox grid sourced from a stale,
  independently-drifted controlled_vocab.py list, and would grow
  physically larger as the vocabulary grew. Replaced with a new
  TagMultiSelect component (searchable, chip-based) sourced from the
  live vocab_terms catalogue; the same fix applied to the /browse
  Task Type filter.
- Two Next.js build failures from useSearchParams() used without a
  Suspense boundary (/submit, /admin/submissions) -- fixed by
  splitting each page into an inner component wrapped in Suspense.
- TagMultiSelect dropdown option text was invisible (white-on-white,
  inherited a global button text color) despite being fully clickable
  -- fixed with an explicit text color and hover state.
- The public /browse catalogue now has a compact live executive summary
  backed by GET /stats/catalogue-summary. It aggregates all published
  benchmarks independently of table filters and list pagination, including
  complexity counts, average evaluation metrics, average citations, and the
  percentage with both code and dataset repository links.
- A live meta-analysis report explorer now sits below the /browse catalogue,
  backed by GET /stats/catalogue-reports. It pairs exact data tables with
  accessible responsive SVG charts for publication trend, complexity,
  research gaps, task types, evaluation metrics, citations, repositories,
  language and modality coverage, licenses, creation method, development
  purpose, and use cases. Reports aggregate every published record and use
  only the latest repository snapshot per source.
- The /browse layout was tightened after visual review: the catalogue now
  shrinks for short result sets while retaining an internal maximum-height
  scroll for long sets, filters use a balanced responsive grid, exports and
  result counts share the records header, final-row borders are explicit,
  mobile reports offer chart/table views, and publication charts include
  zero-count years, axis labels, and a partial-current-year note.
- A pre-existing Alembic branch (two unmerged heads,
  0006_add_community_submissions and 0007_use_case_safety_dim_cols)
  was merged via 0008_add_model_options's tuple down_revision.

---

## 6. Known Gaps / Open Items (as of 2026-09-04)

### Carried over, not yet addressed

1. Ollama Cloud subscription decision (long-standing): paid-tier
   Ollama models remain unverified in practice; the free-tier
   gpt-oss:120b-cloud community submission model has no real web
   search capability. Ollama's own free /api/web_search endpoint is
   a credible path (see archive for full detail) but requires a
   multi-turn tool-calling loop in _call_ollama() -- real engineering
   work, not a config change. Still the top-priority item if a
   dedicated session is available.
2. Email notification channel (SMTP_HOST) is implemented but
   inert until configured -- decide if submitters/admins should be
   notified outside the in-app bell.
3. Admin UI for is_trusted_submitter does not exist yet --
   currently API-only via POST /users/{id}/trust?trusted=true.

### New, surfaced this session

4. Retroactive recompute not run: benchmarks catalogued before
   this session's citation_range and POPULAR_CITATION_THRESHOLD
   changes were not backfilled -- their citation_range may still be
   blank/stale, and complexity_level may still reflect the old
   100-citation Popular threshold. A one-off script (query, recompute
   via compute_citation_range()/classify(), update where changed)
   would close this; not yet written.
5. Vocab term dedup UI is basic: /admin/vocab supports
   activate/deactivate/rename/delete, but not a proper "merge into
   canonical" workflow for near-duplicate agent-added terms (e.g.
   "ASR" vs "Attack Success Rate"). VocabTerm.canonical_term_id
   exists in the schema for this but has no dedicated UI action yet.
6. Audit for the invisible-button-text bug: this was found and fixed
   in TagMultiSelect.tsx specifically. No audit was done for whether
   any other custom button/dropdown component in the frontend has the
   same missing-explicit-color issue against this app's global button
   styling.
7. Verify the TagMultiSelect fix in production: the fix was
   delivered but not yet confirmed working by the user as of this
   file's last update -- confirm on next session start.
8. /browse Task Type filter now public-reads vocab_terms: this
   required relaxing GET /vocab-terms from admin-only to public read
   access. Worth a quick sanity check that no other consumer assumed
   that endpoint was auth-protected.

---

## 7. Working Notes for Future Sessions

- When asked to modify a hardcoded constant, grep the whole backend
  for other usages of that name before assuming a single-file fix is
  complete (see Section 4's non-negotiable principle -- this project's
  most common recurring bug class).
- Space project files are reliably readable via the file_explore tool,
  even when GitHub's own content API or direct chat attachments fail
  to surface real content for certain files (notably .tsx files
  containing embedded HTML tables, which a text-extraction pass can
  mangle). Prefer file_explore for verbatim source when in doubt.
- Deliver full files, not patches, whenever the full current content
  of a file has been verified in-session -- this has been the user's
  stated preference throughout. Only fall back to a clearly-labeled
  find/replace patch when the file's true current content could not be
  verified, and say so explicitly.
- Before delivering any generated file, re-check its literal content
  for a stray closing tag artifact resembling an XML/HTML closing tag
  for the file-content parameter itself -- this has occurred more than
  once this session and the user has flagged it as something to
  actively guard against. Do not even reference the exact string as an
  example inside a delivered file's body; describe it instead.
