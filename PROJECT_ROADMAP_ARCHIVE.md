# AISafetyBenchExplorer Web Scaling - Project Roadmap

Status document. Last updated: 2026-08-28.

This file is the canonical memory reference for this Space. Consult it first
in every future session before proposing new work. Update it whenever scope,
phases, or architecture decisions change.

## 1. Project Background

AISafetyBenchExplorer is a workbook-backed catalogue of 182+ AI safety
benchmarks for LLMs, plus a Python extraction toolkit
(github.com/spyderweb-abdul/AISAFETYBENCHEXPLORER). It has three extraction
pipelines: a DOI-based API pipeline, a Master Prompt for AI-agent extraction,
and a legacy PDF pipeline. Complexity classification (Popular, High, Medium,
Low) follows the decision tree in complexity-methodology.md.

Goal: scale the workbook into a database-backed web application with an
admin CRUD and pipeline-control panel, and a researcher-facing dashboard,
while keeping every field aligned to the existing Excel template schema.

The web app now lives in a separate repository,
github.com/spyderweb-abdul/AISAFETYBENCHEXPLORER-WEB, kept distinct from the
original AISAFETYBENCHEXPLORER pipeline repository to avoid mixing the
Python extraction toolkit's history with the web app's history.

## 2. Key Decision: Agent-as-Orchestrator Architecture

A capable tool-using LLM (e.g. Claude, GPT-4o) running the existing
AISafety_Benchmark_Extraction_Master_Prompt.md as its instruction set can
replace most of the manual extraction code, since the prompt already encodes
the phased reading order, controlled vocabularies, and QA checklist that
mainExtractor.py, pdf_parser.py, and chunker.py implement in code.

However, the following modules must remain deterministic tools called by the
agent, not left to model recall, because they feed numeric fields that drive
the complexity classification and must be reproducible and auditable:

- doi_based_resolver.py -- Semantic Scholar, arXiv, Unpaywall, Crossref
  lookups for citation counts, venue, authors, OA status
- github_scrapper.py / hf_scrapper.py -- star counts, commit recency,
  likes, activity status via REST APIs
- repo_extractor.py -- regex-based GitHub/HuggingFace/Kaggle URL extraction
  from paper text
- models.py -- Pydantic schema used to validate all agent output before
  it is written to the database

Architecture pattern: the agent runs the master prompt, but calls the
above modules as function-calling tools mid-conversation instead of
guessing values. Final output is validated against models.py and the
complexity decision tree before entering a Pending Review queue.

NOTE (2026-07-12): Phase 3's live implementation (agent_runner.py,
paper_fetcher.py) originally followed a lighter variant of this pattern:
paper_fetcher.py IS the deterministic tool for Phase 0.1 (arXiv/Crossref/
Semantic Scholar HTTP calls happen in real code, not model recall), but
Phase 0.2 (GitHub/HuggingFace/license/dataset lookups) was delegated to the
backing model's own agentic web_search tool rather than a separate
deterministic github_scrapper.py / hf_scrapper.py call. This gap is now
CLOSED as of 2026-07-26 -- see Phase 4 below and Section 9 item 10.

## 3. Target Architecture

- Database: PostgreSQL (plus pgvector for future semantic search)
- Backend: FastAPI, reusing existing Pydantic models as shared schemas
- Task queue: Celery + Redis for long-running pipeline and scraper jobs
- Frontend: Next.js (React, TypeScript)
- Charts: Plotly (Python) and Recharts (JS)
- Auth: JWT plus GitHub OAuth2 login
- Hosting: Railway/Render for MVP, migrate to AWS/GCP at scale
- CI/CD: GitHub Actions

## 4. Database Schema Mapping

| Workbook Sheet | Database Table | Notes |
|---|---|---|
| Safety Evaluation Benchmarks (22 cols) | benchmarks | All 22 fields as typed columns |
| Evaluation Metrics Catalogue (9 cols) | eval_metrics | FK to benchmarks |
| Use-Case Quick Filter | benchmark_use_cases | Many-to-many join table |
| Research Gap Heatmap | materialized view | Aggregated over benchmarks |
| Repository Activity Statistics | repo_stats | FK to benchmarks, refreshed by scrapers |

KNOWN GAP (2026-07-12): several benchmarks columns that hold model-generated
prose (no_of_samples, and likely description, complexity_justification) are
currently declared VARCHAR(100) in orm.py. This is too narrow for
legitimately detailed extractions (e.g. multi-clause sample-count
descriptions like PluriHarms's own workbook entry). A pending migration
should widen these to VARCHAR(500) or TEXT. See Section 9.

KNOWN GAP (2026-07-12): the admin frontend has no page or route exposing
Sheet 2 (Evaluation Metrics Catalogue) records. /admin/benchmarks and its
edit page only surface Sheet 1 (benchmarks table) fields; the
evaluation_metrics field on that form is a comma-separated tag input for
metric NAMES only, not the full eval_metrics catalogue row (conceptual_
description, methodological_details, mathematical_definition, differences_
from_standard_definition, notes). agent_runner.py's persist_eval_metrics()
already writes these rows correctly into the eval_metrics table (FK to
benchmarks) during agent extraction, so the data exists and is not at risk
-- there is simply no confirmed UI to view or edit it. See Phase 2b below.

REPOSITORY ACTIVITY STATISTICS UPDATE (2026-07-26): repo_stats is now fully
live. Note that this table already existed in the database with a minimal
pre-Phase-4 schema before Phase 4's ORM model additions -- see Phase 4
below for how the resulting migration mismatch was diagnosed and fixed.

## 5. Phased Roadmap

### Phase 1 -- Foundation (Weeks 1-4) [CODE COMPLETE, needs re-verification]
- Design and migrate PostgreSQL schema from the Excel template; import all
  existing benchmark records
- Set up FastAPI project structure with routers matching module boundaries
- Wrap models.py as the shared schema contract between pipeline and API
- JWT auth with admin and researcher roles
- Monorepo layout: backend/, frontend/, pipeline/ (existing repo as a package)

### Phase 2 -- Admin CRUD Panel (Weeks 5-8) [VERIFIED WORKING, field-completeness gap fixed]
- Full CRUD UI for benchmarks and metrics with controlled-vocabulary dropdowns
  from the master prompt Appendix 1A
- Inline complexity classifier: auto-run the decision tree on save, with
  justification text appended automatically
- Audit log table for every create/update/delete
- Bulk import via CSV/JSON; export back to the canonical Excel template
- Live end-to-end verification (2026-07-05): docker compose build and run
  confirmed working after fixing an obsolete docker-compose.yml version key
  warning and a missing backend/.env file (copied from backend/.env.example)
- Field-completeness gap found and fixed (2026-07-05): Entry Modalities,
  Language Support, and Evaluation Metrics were present in BenchmarkBase
  but not exposed as proper controlled-vocabulary inputs in
  BenchmarkForm.tsx (they were rendered as free-text or number inputs).
  Fixed by:
  (1) typing entry_modalities as list[EntryModality] and language_support
      as list[LanguageSupport] in benchmark.py, using the enums already
      defined but previously unused in the orphaned BenchmarkEntry class,
  (2) removing the orphaned, unused BenchmarkEntry class from benchmark.py,
  (3) adding entry_modalities and language_support to the /vocab response
      in vocab.py (already correctly serving both keys),
  (4) updating the Vocab TypeScript interface in lib/api.ts to declare
      entry_modalities and language_support (missing declaration caused a
      Next.js build failure: "Property 'language_support' does not exist
      on type 'Vocab'"),
  (5) replacing the free-text/number inputs for Entry Modalities and
      Language Support with checkbox multi-select groups (same
      toggleMultiValue pattern used for Task Type), and keeping
      Evaluation Metrics as a comma-separated tag input since metric
      names must match paper terminology exactly, not a fixed vocabulary
- Bug fixed: editing an existing benchmark and clicking Save Benchmark
  returned 422 extra_forbidden errors for id, status, created_at, and
  updated_at. Root cause: BenchmarkUpdate has extra="forbid" but the form
  payload was built by spreading the full form state (which included the
  read-only fields carried over from the fetched BenchmarkOut record).
  Fixed by destructuring id, status, created_at, updated_at out of the
  payload in handleSubmit before calling updateBenchmark.
- Bug fixed: after the above fix, saving an edit threw
  "sqlalchemy.exc.StatementError: Object of type date is not JSON
  serializable" when writing to audit_log.diff (JSONB column). Root cause:
  the before/after diff dict was passed to json.dumps (or SQLAlchemy's
  JSON serializer) with raw Python date objects still in it. Fixed by
  wrapping the diff dict in FastAPI's jsonable_encoder before serializing,
  so date, UUID, and Enum values are converted to JSON-safe primitives
  first.

### Phase 2b -- Sheet 2 Evaluation Metrics Catalogue UI (SHIPPED, verified working)

Identified 2026-07-12 as a real gap during live Phase 3 verification: the
admin user asked where to review Sheet 2 metadata after approving an agent
extraction, and no such page exists. The eval_metrics table and its 9
columns (benchmark_name, paper_title, paper_link, metric_name, conceptual_
description, methodological_details, mathematical_definition, differences_
from_standard_definition, notes) are already populated correctly by
agent_runner.py's persist_eval_metrics() during Phase 3 extraction and by
the Excel-to-DB migration script for pre-existing benchmarks -- this is a
frontend/API exposure gap, not a data-loss or extraction-quality gap.

Scope:
- New backend endpoints: GET /benchmarks/{id}/metrics (list), plus standard
  create/update/delete routes for eval_metrics rows, mirroring the existing
  benchmarks CRUD router pattern and reusing the same JWT admin-role guard.
- New frontend: a "Metrics" tab or expandable section on the existing
  /admin/benchmarks/{id} edit page, listing each linked eval_metrics row
  with inline edit/delete, plus an "Add Metric" form for manually adding a
  Sheet 2 row (e.g. when a benchmark was entered before an agent extraction
  existed, or a metric was missed).
- Reuse the existing audit_log pattern (Section on Phase 2 non-negotiables)
  so metric-row create/update/delete is tracked the same way benchmark CUD
  operations already are.
- Surface a lightweight completeness check on the benchmark edit page: flag
  any metric name listed in the benchmark's evaluation_metrics field that
  has no corresponding eval_metrics row (mirrors the Sheet 1 <-> Sheet 2
  consistency rule already enforced server-side in agent_runner.py's
  _validate_eval_metrics_catalogue(), but currently invisible to a human
  reviewer editing a benchmark manually in the CRUD UI).
- Out of scope for this sub-phase: LaTeX/PDF catalogue export (already
  covered separately by eval_metrics_catalogue_prompt.md's workflow) and
  bulk metric import/export (defer to Phase 2's existing CSV/JSON bulk
  import, extended to cover eval_metrics once this UI exists).

Implemented and verified 2026-07-18. Delivered: GET/POST
/benchmarks/{id}/metrics, GET /benchmarks/{id}/metrics/completeness,
PATCH/DELETE /metrics/{metric_id} (audit-log integrated); new
EvalMetricsPanel.tsx on the /admin/benchmarks/{id} edit page with
inline edit/delete, Add Metric form, and a completeness warning banner
with one-click pre-fill for missing metric names. Verified with
npx tsc --noEmit (0 errors) and a full npx next build (production
build succeeded).

### Phase 3 -- Agent Orchestration Layer (Weeks 9-13) [LIVE, iterating on quality]
- Expose AISafety_Benchmark_Extraction_Master_Prompt.md as a configurable
  system prompt for a chosen backing model (Claude, GPT-4o, etc.) --
  DONE. agent_runner.py's SYSTEM_PROMPT_STUB condenses the master prompt's
  Role & Context, Phase 0 research steps, Phase 1 Sheet 1 fields and
  controlled vocabulary, Phase 2 Sheet 2 metric extraction, and the Phase 3
  complexity decision tree signals into a single-call system prompt.
- Admin submits a DOI, arXiv ID, or PDF and picks a model from a curated
  list -- DONE. Agent Extraction Panel live in the admin frontend
  (source_type dropdown, source_value input, model dropdown, Submit Job).
- Agent runs Phase 0-2 of the master prompt -- DONE as of 2026-07-26. Phase
  0.1 (fetch paper metadata: arXiv API, Crossref, Semantic Scholar citation
  count) runs as a deterministic tool (paper_fetcher.py) before the model
  is ever called. Phase 0.2 (GitHub repo, HuggingFace dataset, license,
  citation cross-check) now also runs as deterministic tool calls
  (github_scrapper.py / hf_scrapper.py via fetch_github_stats() /
  fetch_hf_dataset_stats(), wired directly into agent_runner.py's fetch
  and persist blocks) rather than the model's own agentic web_search tool
  -- see Phase 4 below and Section 9 item 10 (RESOLVED).
- Agent output validated against models.py (BenchmarkCreate) and
  complexity rules before landing in a Pending Review inbox -- DONE.
  ComplexitySignals + classify() run automatically on every job; results
  land with status="pending_review" and a computed quality_score.
- Track cost per run, run-to-run variance, and quality score -- PARTIALLY
  DONE. quality_score (8-field completeness heuristic) and
  requires_review flag are tracked per job; run-to-run cost/variance
  tracking is NOT yet implemented (see Section 9).
- Live end-to-end verification (2026-07-12): submitted multiple real DOI
  jobs (doi:10.1073/pnas.2416228122, arXiv:2406.18510) through the Agent
  Extraction Panel against anthropic/claude-sonnet-5 and openai/gpt-4o.
  Confirmed jobs complete, land in the Pending Review queue with
  Approve/Reject actions, and are visible under All Jobs with full status
  history (failed, needs_review, done).
- Four real bugs found and fixed in this verification pass (all in
  agent_runner.py unless noted):
  (1) Sheet 1 <-> Sheet 2 metric name mismatch crash: the validator
      required exact string equality between evaluation_metrics and
      evaluation_metrics_catalogue metric names, so a model writing
      "relative decision bias (LLM-RDT)" in one list and "relative
      decision bias" in the other raised ValueError and failed an
      otherwise-good extraction. Fixed with _metric_name_variants(),
      which strips trailing parenthetical abbreviations and punctuation
      before comparing; true structural defects (missing keys, empty
      metricname, duplicate rows, mismatched benchmark/paper identifiers)
      still raise, naming drift now only logs a warning.
  (2) Vague Phase 0.2 research instructions: the original system prompt
      only said "search for citation count, code repository, dataset
      availability, and license" with web_search max_uses capped at 5 --
      not enough budget to even complete that vague instruction, let
      alone follow-ups. Replaced with 5 explicitly named targeted queries
      ("<title>" citations semantic scholar; "<name>" github; "<name>"
      dataset huggingface; "<name>" license; huggingface.co/datasets
      cross-check), raised web_search max_uses from 5 to 12, and every
      dependent field (code_dataset, no_of_samples, license,
      code_repository, dataset_repository, integration_option) now names
      which search it must come from before defaulting to null/Unknown.
      NOTE: this web_search-based approach for Phase 0.2 has since been
      superseded by Phase 4's deterministic scraper tools -- see above.
  (3) VARCHAR(100) truncation crash: a real extraction for the PNAS
      implicit-bias paper produced a legitimately detailed no_of_samples
      value (253 characters) that exceeded the benchmarks table's
      VARCHAR(100) column width, causing a StringDataRightTruncation
      Postgres error that rolled back the entire INSERT and failed a
      good extraction. Fixed with a defensive _clamp_varchar_fields()
      guard that truncates any of the 14 single-value text fields to fit
      the current column width (with an ellipsis marker) before the
      INSERT, logs exactly which field(s) were clamped, and forces
      job.status="needs_review" so truncated data is never silently
      marked "done". The durable fix -- widening no_of_samples (and
      likely description, complexity_justification) via an Alembic
      migration -- was completed 2026-07-18; see Section 9 item 8.
  (4) Silent response truncation on Anthropic calls: a job for the same
      PNAS paper failed with "model returned no benchmark_name" because
      Claude's response hit stop_reason="max_tokens" and was cut off
      mid-key (literal `"metricname"` with no value or closing brace),
      leaving no valid JSON for _extract_last_balanced_json() to recover.
      Fixed by adding one automatic retry at double the token budget
      (16384 -> 32000, capped) whenever stop_reason="max_tokens" fires,
      implemented as _call_anthropic() recursively calling itself once
      with _retry_on_truncation=False to prevent infinite loops. Also
      made the JSON extractor strip markdown code fences defensively
      (```json ... ```) since Claude was observed wrapping output in
      fences despite instructions not to.
- Open question flagged by the admin user (2026-07-12, not yet resolved
  in code): does clicking "Reject" in the Pending Review queue re-run
  the extraction job, or does the admin need to resubmit a new job with
  the same source_value? Current agent_runner.py has no code path that
  re-triggers run_extraction() from a reject action -- rejecting most
  likely only changes benchmark.status and/or writes an audit log entry.
  Needs to be confirmed against the actual review/reject router code
  (not reviewed in this session) and documented here once confirmed.
  Still open as of 2026-07-26 -- see Section 9 item 11.
- Admin re-extraction uses benchmark update, not create: extend agent_runner.run_extraction() 
  and the /submissions/{id}/reextract-admin endpoint so that when a job is already linked to a benchmark id, 
  re-running extraction applies a BenchmarkUpdate to that same row (with full audit-log history) instead of 
  creating a duplicate benchmark record. This must preserve the Excel template compatibility and the existing 
  version history semantics.

### Phase 4 -- GitHub and HuggingFace Scraper Service (Weeks 14-17) [SHIPPED, verified end-to-end 2026-07-26]
- Wrap github_scrapper.py and hf_scrapper.py as scheduled Celery Beat tasks
  -- DONE. New celery_app.py (Redis broker/backend, weekly schedule via
  crontab) and tasks.py (refresh_repo_stats_for_benchmark for single/manual
  triggers, refresh_all_repo_stats for the weekly bulk job) delivered and
  verified live.
- Manual and bulk trigger options -- PARTIALLY DONE. Both Celery tasks are
  callable manually via .delay() and confirmed working from a shell; an
  admin-UI "Refresh Now" button calling these tasks through a new API route
  is not yet built (see Section 9, item 13).
- Repository Activity Statistics becomes a live DB view -- DONE via
  migrations 0003_add_repo_stats and 0004_add_repo_stats_cols (see below).
- Rate-limit-aware scraping with exponential backoff (tenacity) -- DONE.
  github_scrapper.py already retries on 403/429/5xx with exponential
  backoff; confirmed this correctly surfaces a clean
  "repo_fetch_failed: 403 rate limit exceeded" error (rather than crashing)
  when the unauthenticated GitHub quota was exhausted during today's
  verification pass -- see Change Log for the full incident.
- This phase formally closes Known Gap 10 (Phase 0.2's reliance on the
  model's own agentic web_search): agent_runner.py's fetch and persist
  blocks were wired to call fetch_github_stats() / fetch_hf_dataset_stats()
  directly during live extraction (verified with a real JailbreakBench job
  producing 2 correct RepoStat rows), matching Section 2's original
  Agent-as-Orchestrator architecture.
- Schema migrations: repo_stats already existed in the DB (from an earlier,
  minimal-schema migration) before Phase 4 columns were added to orm.py.
  0003_add_repo_stats.py's original op.create_table() call was neutralized
  to a no-op upgrade() (the table already existed) to preserve the
  migration chain; 0004_add_repo_stats_cols.py adds the 12 missing Phase 4
  columns (owner, name, forks, open_issues, contributors_count, downloads,
  days_since_last_activity, is_archived, is_private, is_gated, license_id,
  fetch_error) via op.add_column(), plus a repository_activity_statistics
  view joining repo_stats to benchmarks. Both applied cleanly
  (0002_widen_benchmark_cols -> 0003_add_repo_stats -> 0004_add_repo_stats_cols).
- Backfill: app/scripts/backfill_repo_stats.py added to populate RepoStat
  rows for benchmarks extracted before this phase shipped (idempotent,
  skips existing rows, supports --dry-run and --limit). Run against the 4
  pre-existing benchmarks with a code/dataset repository
  (POSTTRAINBENCH, ImplicitBias, WildTeaming/WildJailbreak, JailbreakBench);
  all 6 expected RepoStat rows (4 github + 2 hf_dataset) landed correctly.
- Live end-to-end verification (2026-07-26): confirmed the full chain --
  standalone scraper calls, schema migration, live extraction job persist,
  backfill script, and Celery Beat manual trigger -- all produce correct
  RepoStat rows with real data (e.g. JailbreakBench: 637 GitHub stars, MIT
  license, stale activity; 116 HuggingFace dataset likes).
- Two real bugs found and fixed during this verification pass:
  (1) agent_runner.py persist-block bugs (found before Celery work began):
      a syntax error (url=raw["code_repository",] -- trailing comma inside
      the subscript brackets), a field-name mismatch (last_activity_at used
      instead of the actual RepoStat.last_commit_at column), a second
      field-name mismatch on the HuggingFace branch (likes= used instead of
      stars_or_likes=), and a missing url= assignment on the HuggingFace
      branch (RepoStat.url is NOT NULL, so this would have crashed on
      insert). All four fixed directly in agent_runner.py's persist block.
  (2) tasks.py's _upsert_repo_stats() field-mapping bug (found during
      Celery Beat verification): the fields dict wrote stars=... to a
      RepoStat column that does not exist (the model only has
      stars_or_likes), and separately set
      stars_or_likes=getattr(stats, "likes", None) -- which is None for
      every GitHub-fetched result, since GitHubRepoStats has a .stars
      attribute, not .likes. Net effect: every GitHub-sourced RepoStat row
      silently had its star count overwritten to None on every
      Celery-triggered refresh, while HuggingFace rows were unaffected
      (their .likes attribute genuinely exists). Fixed by removing the
      dead stars=... line and changing stars_or_likes to prefer
      getattr(stats, "stars", None), falling back to
      getattr(stats, "likes", None) only when stars is not present.
- One real operational incident, not a code bug: after fixing bug (2) above
  and restarting the Celery worker to pick up the change, a full
  refresh_all_repo_stats() run returned stars_or_likes=0,
  activity_status="unknown" for all 4 GitHub-sourced rows. Root-caused to
  GitHub's unauthenticated API rate limit (60 requests/hour; each
  fetch_github_stats() call makes 3 requests) being exhausted by the day's
  cumulative manual testing, confirmed via fetch_error showing
  "repo_fetch_failed: 403 rate limit exceeded" on all four rows
  simultaneously. Resolved by setting GITHUB_TOKEN in backend/.env
  (raises the quota to 5000 requests/hour) and restarting backend,
  celery_worker, and celery_beat. Re-ran the refresh; all 4 GitHub rows
  returned to their correct real values with fetch_error=None.
- Unrelated local environment fix needed along the way: docker compose up
  initially failed with "Bind for 0.0.0.0:6379 failed: port is already
  allocated" because another process on the host already had port 6379
  bound. Not investigated further (root process was not identified); a
  subsequent docker compose up brought all containers up cleanly, so no
  code change was needed here -- flagged only so a repeat of this exact
  symptom does not need to be re-diagnosed from scratch.

### Phase 5 -- Researcher Dashboard (Weeks 18-22) [SUBSTANTIALLY COMPLETE 2026-08-26]
- Browse and filter by Task Type, Complexity Level, License, Language
  Support, Use Case, Release date -- DONE (2026-08-26). License,
  Language Support, and a Release Date range (release_date_from /
  release_date_to) are now real server-side query params on
  GET /benchmarks, closing the gap noted on 2026-08-23. There are no
  client-side-only filters left on /browse.
- Interactive Research Gap Heatmap (Plotly) replacing static Excel
  coloring -- DONE, but NOT with Plotly. /browse/heatmap ships as a
  plain HTML table with severity badges (GET /stats/research-gap-
  heatmap, computed live over published benchmarks), not an
  interactive Plotly chart as originally scoped -- revisit if a
  richer visualization is wanted later.
- Benchmark detail pages with linked metrics and repo activity stats
  -- DONE (2026-08-23). /browse/[id] shows full benchmark fields, the
  Evaluation Metrics Catalogue, and Repository Activity with a
  staleness badge built from is_archived/days_since_last_activity.
- CSV and template-compatible Excel export -- DONE (2026-08-26). New
  public, unauthenticated GET /export/public/xlsx and
  GET /export/public/csv, both scoped to status="published" only
  (the original admin-only GET /export/xlsx is unchanged and still
  exports every status for admin use). Both new routes are linked
  from a new Export section on /browse.
- Report builder for multi-benchmark comparison PDFs -- NOT STARTED.
- Public read-only REST API with rate limiting -- DONE (2026-08-26).
  Added slowapi (app/core/rate_limit.py), wired into main.py via
  app.state.limiter + SlowAPIMiddleware with a 100/minute global
  default_limits floor covering every route including ones without an
  explicit decorator. GET /benchmarks and GET /benchmarks/{id} carry
  an explicit 60/minute limit; GET /repo-stats/benchmarks/{id} carries
  60/minute; GET /stats/research-gap-heatmap carries 20/minute
  (tighter, since it aggregates over every published benchmark per
  call); the two new /export/public/* routes carry 10/minute (workbook
  /CSV generation is the most expensive operation of the group).
  GET /benchmarks/{id}/metrics (metrics.py) was not given an explicit
  decorator this session -- it still relies on the 100/minute global
  default via SlowAPIMiddleware. Still no dedicated API documentation/
  versioning for third-party consumption -- that remains open if ever
  needed.
- NOTE (2026-07-26, still accurate): repo_stats' activity_status/
  is_archived/license_id data is now surfaced via the staleness badge
  on /browse/[id] as of 2026-08-23 -- this NOTE's original concern is
  resolved.
- NEW (2026-08-23): use_cases and safety_dimensions are now real,
  queryable columns (see Section 8's 2026-08-23 entries), computed by
  new deterministic classifiers ported from the admin user's prior
  offline analysis scripts.
- RESOLVED (2026-08-26): the USE_CASE_CATEGORIES duplication (Known
  Gap item 19) is closed. app/core/controlled_vocab.py's USE_CASES
  now re-exports app/core/use_case_classifier.py's USE_CASE_CATEGORIES
  directly instead of maintaining a separate hand-copied list -- this
  also fixed a real, previously undetected bug: controlled_vocab.py's
  old USE_CASES list was missing "Customer Service Chatbots" entirely,
  meaning GET /vocab's use_cases key had been silently wrong since
  Phase 5 shipped. frontend/lib/api.ts's hardcoded USE_CASE_CATEGORIES
  constant was removed entirely; both /browse and
  /admin/benchmarks now read use_cases off GET /vocab like every other
  controlled-vocabulary dropdown (Task Type, Complexity Level,
  Language Support). /admin/benchmarks/page.tsx did not previously
  call fetchVocab() at all -- that call was added as part of this fix.

### Phase 6 -- Community and Governance (Weeks 23-26) [NOT STARTED]
- Weekly citation-count refresh feeding the Popular classification
  trigger -- DONE (2026-08-26). See Change Log.
- Full version history per benchmark record -- DONE (2026-08-26).
  Required no new backend endpoint; VersionHistoryPanel.tsx surfaces
  the existing audit_log table. See Change Log.
- Admin notifications for new submissions, failed jobs, or benchmarks
  crossing the Popular threshold -- DONE (2026-08-27), in-app only.
  New Notification model + GET/POST /notifications routes
  (app/routers/notifications.py), NotificationBell.tsx in the shared
  header. Best-effort email side channel exists (app/core/
  notifications.py, stdlib smtplib, no new dependency) but is inert
  until SMTP_HOST is set in backend/.env -- nothing breaks if it
  stays unconfigured.
- Community submission form feeding a review queue -- DONE
  (2026-08-27), gated behind signup. See "Community Submission
  Workflow" subsection below for full detail, including a security
  fix discovered while building this and a known extraction-quality
  limitation that is the top item for next session.
- Community submission form feeding a review queue
- Full version history per benchmark record (audit trail over time)
- Weekly Celery job to refresh citation counts from Semantic Scholar,
  feeding the Popular classification trigger automatically
- Admin notifications for new submissions, failed jobs, or benchmarks
  crossing the 100-citation Popular threshold

#### Community Submission Workflow (Phase 6 item 4 detail)

Gated behind signup: any authenticated "researcher" account (NOT
admin -- see security/role-separation notes below) can submit a DOI
via POST /submissions. Runs through the existing, UNMODIFIED
agent_runner.run_extraction() (app/core/submission_runner.py wraps it
rather than forking it), forced to COMMUNITY_SUBMISSION_MODEL
(app/core/config.py, currently ollama/gpt-oss:120b-cloud, a free-tier
Ollama Cloud model chosen specifically so community submissions never
consume paid OpenAI/Anthropic budget or hit the Known Gap 17
subscription wall) so a spam or off-topic submission never costs
real money.

Validation layers before a submission reaches the admin queue:
- Duplicate detection (same source_value already in flight or already
  catalogued) -- rejected before any model call.
- Consecutive-rejection guard: MAX_CONSECUTIVE_REJECTIONS (default 3)
  rejected/failed submissions in a row pauses new submissions from
  that account until one is approved or an admin intervenes.
- Domain relevance check (app/core/domain_relevance.py): extracted
  task_type checked against controlled_vocab.KNOWN_TASK_TYPES, split
  into strict/generic/no-match tiers plus a safety-keyword fallback on
  title/description, since several vocabulary entries (Benchmark,
  Evaluation, Language, Capabilities) are too generic to be meaningful
  alone.
- Quality-score floor (MIN_QUALITY_SCORE_FOR_REVIEW, default 0.5)
  combined with a failed domain check triggers auto-rejection with a
  reason sent to the submitter -- auto-reject only fires when BOTH
  signals fail, never on either alone.
- is_trusted_submitter (admin-togglable per user, POST
  /users/{id}/trust): a trusted submitter's failed domain check is
  downgraded to a flagged pending_review instead of auto-rejected.
  Does not bypass the consecutive-rejection guard.

Review outcomes (admin-only, POST /submissions/{id}/review): approve
(publishes the benchmark), reject (reason required, submitter
notified), or needs_better_extraction (reason required; admin then
calls POST /submissions/{id}/reextract with a paid model of their
choice -- openai/gpt-4o or an Anthropic model -- which supersedes the
original free-tier benchmark and re-queues for review). Admins cannot
review their own submissions (self-review guard added 2026-08-27).

SECURITY FIX (found and fixed while building this, 2026-08-27):
UserCreate previously had a client-settable `role` field, and
POST /auth/register wrote it directly -- meaning ANY anonymous caller
could self-register as role="admin". Fixed: UserCreate no longer has a
role field at all; every self-registered account is hardcoded to
role="researcher" server-side (app/schemas/user.py, app/routers/
auth.py). There is intentionally no self-service or API path to
becoming an admin. /auth/register also gained a 10/hour rate limit to
prevent mass account creation as a way to sidestep the
consecutive-rejection guard (which is keyed per-user).

ROLE-SEPARATION BUG (found and fixed during live testing, 2026-08-27):
POST /submissions originally accepted ANY authenticated user,
including admins. An admin testing the flow with their own account
received both admin-facing notifications (new submission to review)
and submitter-facing ones (approved/declined) on the same identity,
and could in principle review their own submission. Fixed with a new
require_researcher() dependency (app/core/deps.py) that structurally
excludes admins from POST /submissions -- not just a UI nicety, a real
403 at the endpoint. Frontend gained matching enforcement: a new
app/admin/layout.tsx gates EVERY /admin/* route (previously only nav
links were hidden, which did nothing to stop direct URL access), and
/submit proactively redirects admin accounts to /admin/benchmarks
instead of letting them hit the 403 only at submit time.
NotificationBell.tsx now also visually tags each notification "For
admins" vs. "For you (submitter)" so historical/mixed-role test
accounts (from before this fix existed) are at least legible. A
one-time cleanup script (app/scripts/cleanup_mismatched_notifications.py)
exists for purging pre-fix mismatched notification rows; running it in
dry-run mode on 2026-08-27 found 0 mismatched rows on the account
tested.

KNOWN LIMITATION, TOP PRIORITY FOR NEXT SESSION (found during live
testing, 2026-08-27): the free-tier Ollama model
(gpt-oss:120b-cloud) cannot reliably extract code_repository/
dataset_repository links from a paper, because it has no web search
capability -- unlike the Anthropic admin-panel path, which attaches a
real web_search tool. Four distinct bugs were found and fixed getting
extraction to run AT ALL on this model before this limitation became
visible (see Change Log for full detail): a JSON-parsing crash on
non-standard Ollama Cloud responses, an empty-response failure caused
by gpt-oss exhausting its token budget on internal chain-of-thought
reasoning before max_tokens was set explicitly, a shared prompt
instruction telling the model to "run searches" when no tool was ever
attached (causing gpt-oss specifically to emit pseudo-tool-call
narration instead of JSON), and a frontend crash from FastAPI
serializing Submission.quality_score (a Decimal) as a JSON string
instead of a number. With all four fixed, extraction now completes
successfully end-to-end, but without any real search capability the
model simply cannot find links the paper's abstract/excerpt doesn't
already contain verbatim.

RECOMMENDED FIX, NOT YET IMPLEMENTED: Ollama provides its own free,
separate web search API (POST https://ollama.com/api/web_search,
"generous free tier... higher rate limits via Ollama's cloud" per
Ollama's own blog/docs, confirmed 2026-08-27) plus native tool-calling
support for modern Ollama models including gpt-oss (tool-calling is
the actual design purpose of gpt-oss's Harmony format). This is a
credible, verified, free-tier path to give the community submission
model the same kind of grounded search capability
_call_anthropic() already gets from Claude's built-in web_search tool
-- NOT yet implemented. Would require: (1) defining a web_search tool
schema pointing at Ollama's /api/web_search endpoint, (2) implementing
a multi-turn tool-calling loop in _call_ollama() (unlike Anthropic's
server-side tool execution, Ollama's tool-calling requires the client
to execute the tool call and feed results back in a follow-up
message), (3) re-testing the max_tokens budget, since a multi-turn
tool-calling conversation will consume more tokens than a single-shot
call. This is real engineering work, not a config change -- scope for
a dedicated session, not a quick follow-up. Until then: the admin
user's stated plan is to keep gpt-oss:120b-cloud as the community
submission model as-is, relying on the existing
needs_better_extraction admin review path (POST
/submissions/{id}/reextract with a paid model) to backfill
code_repository/dataset_repository for any community submission that
needs them, rather than blocking the whole feature on this gap.

## 6. Non-Negotiable Principles

- Pipeline code is imported as a package, never rewritten from scratch
- All DB schema and exports remain 100% compatible with the Excel template
  so the workbook and web app can coexist during transition
- No non-printable Unicode characters in any DB field, API response, or
  frontend-rendered text; validation middleware enforces this on write
- No long dashes in any generated text or code within this project

## 7. Version Control Setup

- Web app repository: github.com/spyderweb-abdul/AISAFETYBENCHEXPLORER-WEB
  (separate from the pipeline repository, AISAFETYBENCHEXPLORER)
- Local remote authentication uses SSH
  (git@github.com:spyderweb-abdul/AISAFETYBENCHEXPLORER-WEB.git), not HTTPS,
  since GitHub no longer accepts password authentication for git operations
- .gitignore in place at the repo root covering: Python (__pycache__,
  .venv, *.egg-info), environment secrets (.env, backend/.env,
  frontend/.env), Node/Next.js (node_modules, .next, build, dist),
  database artifacts (pgdata, *.sqlite3), OS files, and IDE folders
- Incident (2026-07-05): a force-push was accidentally sent to the
  original AISAFETYBENCHEXPLORER pipeline repository instead of
  AISAFETYBENCHEXPLORER-WEB, overwriting its main branch. Recovered by
  pushing the original commit hash back to main before it could be
  garbage-collected, then correcting the local remote URL with
  git remote set-url to point at AISAFETYBENCHEXPLORER-WEB.
  LESSON LEARNED: always run git remote -v immediately before any
  git push --force, and double check the exact repo name in the URL,
  since AISAFETYBENCHEXPLORER and AISAFETYBENCHEXPLORER-WEB differ only
  by a suffix.

## 8. Change Log

- 2026-07-04: Initial roadmap created. Agent-as-orchestrator decision for
  Phase 3 incorporated, replacing a pure code-pipeline-only approach.
- 2026-07-04 (later): Phase 1 implemented. Delivered PostgreSQL schema
  (schema.sql), SQLAlchemy ORM models, Pydantic v2 schemas mirroring the
  workbook columns, FastAPI skeleton with JWT auth (admin/researcher
  roles), CRUD-ready benchmarks and metrics routers, Alembic migration
  scaffolding, Docker Compose setup, and a one-time Excel-to-DB migration
  script (scripts/migrate_excel_to_db.py) that imports Sheet 1 and Sheet 2
  from the existing workbook.
- 2026-07-04 (later): Phase 1 stood up live and verified end-to-end in a
  real sandbox: PostgreSQL 15 installed, schema applied (8 tables
  confirmed), FastAPI server started, full auth flow tested (register,
  login, /auth/me, role promotion to admin), full CRUD flow tested
  (create/get/filter/update a HarmBench benchmark record, create a linked
  eval_metrics row), and role enforcement confirmed (403 for non-admin
  writes). Two bugs found and fixed: missing email-validator dependency,
  and bcrypt/passlib version-detection warning (pinned bcrypt==4.0.1).
- 2026-07-04 (later): Phase 2 implemented -- complexity_classifier.py
  (codifies the complexity-methodology.md decision tree), audit.py logging
  wired into all benchmark CUD operations, controlled_vocab.py served via
  /vocab, Excel export endpoint (/export/xlsx), and a full Next.js admin
  frontend (login, benchmarks list with search/filter/export, create/edit
  form with inline complexity classifier UI, audit log viewer).
- 2026-07-04 (incident #1): mid-session sandbox reset wiped the backend/
  directory, the live PostgreSQL instance, installed packages, and this
  roadmap file. Only frontend/ files (written after the reset) survived.
  Rebuilt the entire backend/ directory and this roadmap from scratch,
  using conversation history as the source of truth. Re-validated via
  py_compile (no syntax errors). Could not re-run live PostgreSQL +
  FastAPI end-to-end verification due to environment constraints.
- 2026-07-04 (incident #2): the ENTIRE output/ directory (including the
  zip file, README, and roadmap from incident #1's rebuild) was wiped a
  second time before the zip could be delivered to the user. Rebuilt the
  complete project a second time in a single consolidated pass: backend
  (31 Python files, all py_compile clean), frontend (Next.js admin app),
  migration script, Docker files, a detailed README.md with step-by-step
  local setup instructions (Docker and native paths, Postgres setup,
  admin user creation, manual test checklist), and this roadmap file.
  Zipped immediately after writing all files to minimize risk of a third
  reset causing data loss before delivery.
  LESSON LEARNED: this Space's sandbox environment has now reset twice
  mid-session, including once after code was already zipped. Going
  forward: zip and hand off deliverables to the user as early as
  possible after each milestone, rather than batching multiple features
  before packaging, to minimize rework if a reset recurs.
- 2026-07-05: User stood up the project locally with docker compose
  up --build. Fixed the obsolete docker-compose.yml "version" attribute
  warning (informational only, no action needed) and a missing
  backend/.env file (resolved by copying backend/.env.example to
  backend/.env).
- 2026-07-05 (later): User created a sample benchmark entry and found
  that Entry Modalities, Language Support, and Evaluation Metrics were
  not properly exposed in the entry form despite existing in the
  BenchmarkBase schema. Diagnosed as a schema/UI mismatch: the fields
  existed as untyped list[str] in benchmark.py, and an orphaned
  BenchmarkEntry class had the correct EntryModality/LanguageSupport
  enums but was never wired into BenchmarkCreate/Update/Out. On the
  frontend, the three fields were rendered as free-text or number
  inputs instead of controlled-vocabulary checkbox groups. Fixed by
  retyping the fields with the existing enums, removing the orphaned
  class, adding both vocab keys to the /vocab endpoint response, and
  replacing the form inputs with checkbox multi-selects (Entry
  Modalities, Language Support) plus a tag-style comma-separated input
  (Evaluation Metrics, since metric names are free text matching paper
  terminology, not a fixed vocabulary).
- 2026-07-05 (later): Next.js build failed after the vocab.py fix with
  "Property 'language_support' does not exist on type 'Vocab'". Root
  cause: the Vocab TypeScript interface in lib/api.ts was never updated
  to declare the new field, even though the backend correctly returned
  it. Fixed by adding language_support: string[] (and confirming
  entry_modalities: string[]) to the Vocab interface.
- 2026-07-05 (later): Editing an existing benchmark and clicking Save
  Benchmark returned HTTP 422 with extra_forbidden errors for id, status,
  created_at, and updated_at. Root cause: BenchmarkUpdate uses
  extra="forbid", but the form's handleSubmit spread the entire form
  state (originally populated from a BenchmarkOut record, which includes
  those four read-only fields) directly into the update payload. Fixed
  by destructuring those four fields out of the payload before sending
  it to updateBenchmark.
- 2026-07-05 (later): After the above fix, saving an edit threw
  sqlalchemy.exc.StatementError: Object of type date is not JSON
  serializable while inserting into audit_log (JSONB diff column). Root
  cause: the before/after diff dict retained raw Python date objects
  when handed to the JSON serializer. Fixed by wrapping the diff dict in
  FastAPI's jsonable_encoder before serialization, which converts date,
  UUID, and Enum values to JSON-safe primitives.
- 2026-07-05 (later): Set up version control for the web app. Created
  .gitignore covering secrets, node_modules, __pycache__, and build
  artifacts. Initial push accidentally targeted the wrong GitHub repo
  (AISAFETYBENCHEXPLORER, the original pipeline repo, instead of
  AISAFETYBENCHEXPLORER-WEB) via a stale/incorrect remote URL, then via
  a force-push after switching to SSH auth. Recovered the original
  repo's history by pushing its prior commit hash back to main before
  garbage collection, then corrected the local remote with
  git remote set-url to point at AISAFETYBENCHEXPLORER-WEB. Documented
  the incident and a "check git remote -v before force-push" lesson in
  a new Version Control Setup section (Section 7) of this roadmap.
- 2026-07-12: Began live Phase 3 verification. Submitted a real DOI
  extraction job (doi:10.1073/pnas.2416228122, "Explicitly unbiased
  large language models still form biased associations") through the
  Agent Extraction Panel against anthropic/claude-sonnet-5. Extraction
  quality was judged good by the admin user, but the job failed with a
  Sheet 1 <-> Sheet 2 metric name mismatch (evaluation_metrics listed
  "relative decision bias (LLM-RDT)" while evaluation_metrics_catalogue
  used "relative decision bias"), crashing the validator's exact-match
  check. Rewrote agent_runner.py's _validate_eval_metrics_catalogue()
  with fuzzy metric-name reconciliation (_metric_name_variants(),
  stripping trailing parenthetical abbreviations and punctuation before
  comparing); structural defects still raise, naming drift now only
  warns. Also identified and fixed vague Phase 0.2 research instructions
  in the same pass: replaced a single generic "search for citation
  count/repo/dataset/license" bullet with 5 explicitly named targeted
  queries, raised Anthropic web_search max_uses from 5 to 12, and raised
  max_tokens from 8192 to 16384.
- 2026-07-12 (later): Re-ran the same PNAS extraction job. It failed
  again, this time with a Postgres StringDataRightTruncation error on
  INSERT: the model's no_of_samples value (253 characters, a
  legitimately detailed sample-count description) exceeded the
  benchmarks table's VARCHAR(100) column width, rolling back an
  otherwise-good extraction. Added a defensive _clamp_varchar_fields()
  guard in agent_runner.py that truncates any of 14 single-value text
  fields to fit the current column width before the INSERT, logs which
  field(s) were clamped, and forces job.status="needs_review" instead of
  "done" when truncation occurs. Flagged the real fix (widening
  no_of_samples, and likely description/complexity_justification, via
  an Alembic migration to VARCHAR(500) or TEXT) as still pending -- see
  Section 9 Known Gaps.
- 2026-07-12 (later): Re-ran the same PNAS extraction job a third time.
  It failed with "model returned no benchmark_name" -- diagnosed from
  backend logs as Claude's response hitting stop_reason="max_tokens" and
  being cut off mid-key (literal `"metricname"` with no closing brace),
  leaving no valid JSON object for the balanced-brace extractor to
  recover (correctly returned {} given a genuinely truncated stream).
  Separately, a Semantic Scholar 429 rate-limit was also logged in the
  same run but was non-fatal (already-handled fallback path). Fixed the
  truncation by adding one automatic retry in _call_anthropic() at
  double the token budget (16384 -> 32000, capped) whenever
  stop_reason="max_tokens" fires, using a _retry_on_truncation flag to
  cap retries at one. Also made _extract_last_balanced_json() strip
  markdown code fences defensively, since Claude was observed wrapping
  its JSON output in ```json fences despite the system prompt saying not
  to.
- 2026-07-12 (later): Re-ran the same job a fourth time; it completed
  successfully into needs_review status (100% quality score, with the
  no_of_samples truncation guard logged and visible). Confirmed via
  screenshot that the Agent Extraction Panel's Pending Review queue,
  Approve/Reject actions, and All Jobs status history (failed,
  needs_review, done across multiple runs) are all working end-to-end.
  Admin user raised two open questions, both logged under Phase 3 above
  and Section 9 below: (1) whether Reject re-runs the extraction job or
  requires a fresh resubmission (not yet confirmed against the actual
  review/reject router code), and (2) confirmed that full field-level
  editing before/after approval is only available via the /admin/
  benchmarks CRUD editor, not inline on the Agent Extraction Panel.

- 2026-07-12 (later): Admin user asked where to review/edit Sheet 2
  (Evaluation Metrics Catalogue) records after noticing /admin/benchmarks
  and its edit page only expose Sheet 1 (benchmarks table) fields.
  Confirmed via schema and change-log review that no such page or route
  currently exists, even though agent_runner.py's persist_eval_metrics()
  already writes complete, correct eval_metrics rows during extraction --
  this is a frontend/API exposure gap, not a data-loss risk. Added Phase
  2b (Sheet 2 Evaluation Metrics Catalogue UI) to the roadmap to close it:
  new /benchmarks/{id}/metrics CRUD endpoints, a Metrics tab on the
  benchmark edit page, audit-log integration matching the existing
  benchmarks pattern, and a Sheet 1<->Sheet 2 completeness flag surfaced
  to human reviewers (mirroring the server-side check already enforced in
  agent_runner.py).

- 2026-07-18: Phase 2b implemented and delivered: new
  /benchmarks/{id}/metrics CRUD endpoints (list, create, completeness
  check) plus PATCH/DELETE /metrics/{metric_id}, all audit-logged; new
  EvalMetricsPanel.tsx on the /admin/benchmarks/{id} edit page with
  inline edit/delete, an Add Metric form, and a completeness warning
  banner that flags any evaluation_metrics name missing a catalogue row.
  Verified with npx tsc --noEmit (0 errors) and a full production
  npx next build (succeeded).
- 2026-07-18 (later): Admin user tried to delete a benchmark via the
  DELETE button and got a 500 Internal Server Error / Postgres
  ForeignKeyViolation on extraction_jobs_result_benchmark_id_fkey,
  because extraction_jobs.result_benchmark_id had no ON DELETE
  behavior (defaulted to NO ACTION). Fixed with ON DELETE SET NULL
  (chosen over CASCADE to preserve the extraction job's own audit
  trail after its resulting benchmark is deleted) in schema.sql and
  models/orm.py, applied immediately to the running DB via a
  standalone quick_fix_extraction_jobs_fk.sql, and confirmed working.
- 2026-07-18 (later): Found and fixed a second, unrelated bug while
  investigating why /admin/audit-log showed no rows: app/core/audit.py's
  log_action() was double-encoding the audit_log.diff JSONB column
  (diff=json.dumps(jsonable_encoder(safe_diff)) on top of SQLAlchemy's
  own JSONB serialization). This regression was introduced by the
  2026-07-05 jsonable_encoder fix (see that entry above) and went
  unnoticed until now. Fixed by removing the outer json.dumps() call.
  User truncated the audit_log table to clear already-double-encoded
  test rows and confirmed new entries render correctly.
- 2026-07-18 (later): Closed Known Gap #1 (VARCHAR(100) truncation
  risk, open since 2026-07-12). Checked every field agent_runner.py's
  _clamp_varchar_fields() safety net covered against the live schema:
  description and complexity_justification were already TEXT (the
  gap's suspicion they were still narrow was incorrect); only
  no_of_samples and license were genuinely still narrow. Widened
  no_of_samples to TEXT and license to VARCHAR(300) in orm.py and
  schema.sql, trimmed agent_runner.py's _VARCHAR_100_FIELDS list to
  drop both (keeping the clamp guard for the remaining bounded fields),
  and wrote two chained Alembic migrations to formalize both this fix
  and the previous session's FK fix, since that FK migration file had
  never actually been committed to the repo (only its .pyc leftover
  existed locally -- discovered when re-cloning origin/main after the
  user's merge).
- 2026-07-18 (later): First Alembic run
  (docker compose exec backend alembic upgrade head) failed with
  "command not found: alembic" -- expected, since the user was running
  the command on the host shell (zsh, native Mac Python), not inside
  the backend container where Alembic is actually installed via
  requirements.txt.
- 2026-07-18 (later): Second attempt
  (docker compose exec backend alembic upgrade head, this time
  correctly inside the container) failed with
  ModuleNotFoundError: No module named 'app', because Alembic's
  installed console-script entry point does not add the current
  working directory to sys.path the way `python -m` does, and
  alembic/env.py imports app.core.config. Fixed for this run with
  `python -m alembic upgrade head` instead of the bare `alembic`
  binary, and added environment: PYTHONPATH: /app to the backend
  service in docker-compose.yml so the bare `alembic` command will
  also work after the next container rebuild.
- 2026-07-18 (later): Third attempt
  (docker compose exec backend python -m alembic upgrade head) failed
  with psycopg2.errors.StringDataRightTruncation: value too long for
  type character varying(32) while Alembic tried to INSERT its own
  bookkeeping row into alembic_version. Root cause: Alembic's
  alembic_version table has a hardcoded version_num VARCHAR(32)
  column, and the original revision IDs
  (0001_fix_extraction_jobs_fk_on_delete, 37 chars;
  0002_widen_benchmark_text_columns, 33 chars) both exceeded it. Fixed
  by shortening the revision strings to 0001_fix_extraction_fk (22
  chars) and 0002_widen_benchmark_cols (25 chars) while keeping the
  descriptive filenames unchanged; down_revision chaining updated to
  match. Confirmed no partial DDL had been applied before this failure
  (transaction rolled back cleanly).
- 2026-07-18 (later): Fourth attempt
  (docker compose exec backend python -m alembic upgrade head, with
  the shortened revision IDs) succeeded cleanly: both
  0001_fix_extraction_fk and 0002_widen_benchmark_cols applied in
  order with no errors. Known Gap #1 and the extraction_jobs FK
  ON DELETE fix are both now fully closed, migration history included.
  See Section 9, item 9.
- 2026-07-26: Began Phase 4 (GitHub/HuggingFace scraper service). Verified
  github_scrapper.py and hf_scrapper.py work standalone against live APIs
  (confirmed on HarmBench and JailbreakBench). Found and fixed 4 bugs in
  agent_runner.py's Phase 0.2 persist block (syntax error on a dict
  subscript with a trailing comma; last_activity_at vs. the real
  last_commit_at column name; likes= vs. the real stars_or_likes column
  name on the HuggingFace branch; missing url= on the HuggingFace branch,
  which would have violated RepoStat.url's NOT NULL constraint). Diagnosed
  and fixed a schema mismatch: repo_stats already existed in the DB with a
  minimal pre-Phase-4 schema, so the original 0003_add_repo_stats.py
  migration (written assuming the table did not exist) was neutralized to
  a no-op and a new 0004_add_repo_stats_cols.py migration was added using
  op.add_column() to add the 12 missing Phase 4 columns instead; both
  applied cleanly in sequence. Verified with a real live extraction job
  (JailbreakBench) that both scrapers now run automatically during
  extraction and persist correct RepoStat rows.
- 2026-07-26 (later): Wrote app/scripts/backfill_repo_stats.py to populate
  RepoStat rows for the 4 pre-existing benchmarks with a code_repository or
  dataset_repository (POSTTRAINBENCH, ImplicitBias, WildTeaming/
  WildJailbreak, JailbreakBench) that predated this phase's live wiring.
  Script is idempotent (skip-if-exists) and supports --dry-run/--limit.
  Ran successfully; all 6 expected rows (4 github + 2 hf_dataset) landed
  with correct real data.
- 2026-07-26 (later): Implemented Celery Beat scheduling (celery_app.py,
  tasks.py) for weekly automatic RepoStat refresh (Monday 03:00 UTC), plus
  a manually-triggerable refresh_all_repo_stats task for on-demand use.
  Hit and fixed a Docker port conflict (6379 already bound on the host) to
  get the redis container running; verified the worker registered both
  tasks and Beat started cleanly. Manual trigger initially reproduced the
  HuggingFace likes count correctly but returned None for all GitHub-
  sourced rows -- root-caused to a field-mapping bug in tasks.py's
  _upsert_repo_stats() (wrote to a non-existent stars column, and
  separately mapped stars_or_likes from a .likes attribute that only
  exists on HuggingFace stats objects, not GitHub ones). Fixed the mapping
  to prefer .stars and fall back to .likes; confirmed the fix loaded
  correctly on the worker via grep, then re-ran the refresh. Second run
  returned stars_or_likes=0 / activity_status=unknown for all GitHub rows
  -- diagnosed via fetch_error as GitHub's unauthenticated rate limit
  (60 req/hour) being exhausted by the day's cumulative testing (each
  fetch_github_stats() call makes 3 requests). Set GITHUB_TOKEN in
  backend/.env, restarted backend/celery_worker/celery_beat, and confirmed
  a clean re-run: all 4 GitHub rows and 2 HuggingFace rows now show
  correct real values (23/467/637/42 stars, 116/136 likes) with
  fetch_error=None across the board. Phase 4 is now considered fully
  shipped and verified end-to-end; see Section 9 for the resulting closed
  and newly-opened Known Gaps.

  2026-08-16: Fixed two live bugs in the already-scaffolded but never-
  wired repo_stats admin router (item 13). app/routers/repo_stats.py's
  GET /repo-stats/benchmarks/{id} referenced an undefined name
  (RepoStats instead of the imported RepoStat), a NameError on every
  call. app/schemas/repo_stats.py's RepoStatsOut declared fields (stars,
  likes, last_activity_at) that do not exist on the RepoStat ORM model
  at all (the model has a single stars_or_likes column and
  last_commit_at), which would have raised a Pydantic validation error
  on every response once the NameError was fixed. Both corrected. Added
  RepoStatsPanel.tsx to the admin benchmark edit page: a table of repo
  stats plus Reload / Refresh Now / Refresh All Benchmarks buttons
  wired to the existing (already-working) Celery tasks via the now-
  fixed router. Item 13 is closed.

  2026-08-16 (later): Resolved item 11 (Reject-action semantics) by
  reading the actual review_job() code in app/routers/extraction.py.
  Confirmed: rejecting in the Pending Review queue does NOT re-trigger
  run_extraction() -- it only sets benchmark.status="rejected" and
  job.status="failed". No new ExtractionJob row is created and nothing
  is re-queued. To retry, the admin must manually resubmit a new job via
  POST /extraction/jobs with the same source_type/source_value. This is
  a terminal action, not a retry trigger. Item 11 is closed
  (documentation only, no code change required).

  2026-08-16 (later): While confirming the above, found an undocumented
  gap: GET /benchmarks (app/routers/benchmarks.py's list_benchmarks) had
  no status filtering at all -- not even an optional parameter. A
  rejected benchmark's row is never deleted (only its status field
  changes), so it stayed visible in every list_benchmarks call
  indefinitely, mixed in with published entries, with no way to
  distinguish or exclude it. This also directly affects Phase 5, which
  is designed to reuse this same endpoint for its public browse view.
  Fixed: default behavior (no status param) now excludes status=
  "rejected" only, leaving pending_review visible by default since
  current admin workflows rely on seeing in-progress items in this
  list; an explicit ?status=published|pending_review|rejected filter
  is now available for any caller, including the future Phase 5
  dashboard. Frontend: added a Status column (colored badge) and a
  Status filter dropdown to /admin/benchmarks, matching the existing
  complexity_level filter pattern. This gap and its fix are not
  numbered in the "Still open" list below since they were opened and
  closed the same session -- noted here for the record.

  2026-08-16 (later): Implemented item 12 (per-run cost / run-to-run
  variance tracking), which had been called out as a Phase 3 goal but
  never built. Added input_tokens, output_tokens, and
  estimated_cost_usd columns to extraction_jobs (Alembic migration
  0005_add_extraction_cost_cols). Added app/core/cost_tracking.py: a
  pricing table (USD per 1M tokens) covering OpenAI (gpt-4o,
  gpt-4o-mini), Anthropic (claude-sonnet-5, both claude-3-5-sonnet
  snapshots, claude-haiku-4-5, claude-opus-5), Google Gemini, Moonshot
  Kimi, DeepSeek, and Alibaba Qwen, verified against each provider's
  pricing page on 2026-08-16; a model_used string not in the table
  returns None (rendered as "unpriced" in the UI) rather than a
  fabricated cost. Added GET /extraction/jobs/variance?source_value=
  returning run_count, mean/stddev quality_score, and total cost across
  every job sharing that source_value -- directly answers the kind of
  question this file's own Change Log needed to answer manually for the
  PNAS paper that took 4 attempts (see the 2026-07-12 entries above).
  agent_runner.py's _call_openai/_call_anthropic now capture and return
  token usage alongside the parsed extraction result; run_extraction()
  persists it on the job before its final commit. Frontend: added a
  cost/token readout to every job card on the Agent Extraction Panel,
  plus a "Check Prior Runs & Cost" button next to the submit form.
  NOTE: claude-sonnet-5's pricing entry is introductory ($2/$10 per 1M)
  through 2026-08-31; standard pricing ($3/$15) takes effect 2026-09-01
  and the pricing table will need updating then, or costs will be
  under-reported by ~50% for that model after that date.

  2026-08-16 (later): One live frontend bug found and fixed within the
  same session: estimated_cost_usd is a Decimal on the backend, and
  FastAPI/Pydantic serializes Decimal fields to JSON as strings, not
  numbers (the same reason quality_score is already wrapped in
  Number(...) everywhere it's used in this codebase). The new cost
  readout called cost.toFixed(4) directly on the raw API value, which
  threw "TypeError: cost.toFixed is not a function" the first time a
  real (non-null) cost value was returned. Fixed by coercing with
  Number(cost) before formatting, with a NaN guard; also fixed the same
  latent issue in the "Total estimated spend" summary line, which had
  been silently vulnerable to string concatenation instead of addition.

  2026-08-16 (later): Added Ollama Cloud as a third callable provider,
  per team preference to standardize on Ollama Cloud (over self-hosted
  Ollama) ahead of a production move. Ollama exposes an OpenAI-
  compatible /v1/chat/completions endpoint at https://ollama.com/v1,
  authenticated with an OLLAMA_API_KEY bearer token -- this lets
  agent_runner.py reuse the same openai SDK already used for
  _call_openai, just pointed at a different base_url, rather than
  needing a new client library. Added _call_ollama() and a third
  "ollama" branch in run_extraction()'s provider dispatch (reads
  settings.OLLAMA_BASE_URL_CLOUD / OLLAMA_API_KEY directly, so no
  changes were needed to run_extraction()'s signature or the
  submit_job() call site). Set OLLAMA_BASE_URL_CLOUD's default to
  https://ollama.com/v1 in config.py. Added six ollama/* model options
  to the Agent Extraction Panel's dropdown, using the plain (non-
  ":cloud"-suffixed) model tags Ollama's direct API expects: deepseek-
  v4-pro, deepseek-v4-flash, kimi-k3, kimi-k2.6, qwen3.5:397b, qwen3-
  coder:480b. cost_tracking.py's pricing table deliberately has no
  entries for these -- Ollama Cloud is a flat monthly subscription, not
  metered per-token billing, so "unpriced" is the correct, honest label
  for these jobs, not a bug.
  LIVE TEST RESULT: submitted a real job with model_used=
  "ollama/deepseek-v4-flash" and it failed with
  openai.PermissionDeniedError: 403 "this model requires a subscription,
  upgrade for access: https://ollama.com/upgrade". This confirms the
  integration code itself is working correctly -- the request
  authenticated successfully and Ollama returned a clean, well-formed
  API error, not a crash. The blocker is that the account used for
  testing does not have an active paid Ollama Cloud subscription tier
  that includes deepseek-v4-flash (or presumably the other 5 ollama/*
  models added). See Known Gaps item 17 below -- this needs a real
  subscription upgrade before it can be verified end-to-end, and it is
  NOT yet confirmed whether any ollama/* model works, since none has
  successfully completed a run.
  ALSO UNVERIFIED (flagged in the code's own docstring, repeating here
  for visibility): whether Ollama-hosted open-weight models honor
  OpenAI's response_format={"type": "json_object"} strict-JSON-mode
  parameter as reliably as gpt-4o does. This cannot be tested until the
  subscription blocker above is resolved.

  - 2026-08-16 (later): Closed items 14 and 15. Item 15 (repo_stats had no
  historical time series, only latest-value upserts): renamed
  app/core/tasks.py's _upsert_repo_stats() to
  _insert_repo_stats_snapshot() and changed it to always INSERT a new
  row instead of updating one in place -- repo_stats is now an
  append-only history table. Added Alembic migration
  0006_repo_stats_history_view.py: an index on (benchmark_id, source,
  fetched_at) for query performance, and a rewritten
  repository_activity_statistics view (originally from migration 0004)
  using ROW_NUMBER() OVER (PARTITION BY benchmark_id, source ORDER BY
  fetched_at DESC) so it continues to show exactly one row per
  benchmark+source (the latest) rather than duplicating as history
  accumulates. Updated GET /repo-stats/benchmarks/{id} to default to
  the same latest-only behavior (matching what RepoStatsPanel.tsx
  already expects, so no frontend change was needed), with a new
  ?history=true override for anyone who wants the full time series --
  e.g. a future star/like growth chart, which was the original
  motivation for wanting history at all.
  Item 14 (GitHub rate-limit headroom, unverified at scale): added
  app/core/github_rate_limit.py (check_github_rate_limit() /
  has_sufficient_quota(), calling GitHub's /rate_limit endpoint, which
  does not itself consume quota). refresh_all_repo_stats() now checks
  remaining quota before queuing anything -- if there isn't enough
  headroom for every benchmark with a code_repository (estimated at 3
  requests each, per the existing Phase 4 note), it aborts cleanly with
  a skipped_due_to_rate_limit result instead of repeating the original
  Phase 4 incident where most rows failed individually with scattered
  403s. Added GET /repo-stats/github-rate-limit (admin-only) for
  on-demand headroom visibility at any time, not just at bulk-refresh
  time.
  BUG FOUND AND FIXED DURING ROLLOUT: the first version of
  github_rate_limit.py imported requests, which is not a dependency of
  this project (confirmed against backend/requirements.txt) and broke
  celery_worker/celery_beat at import time with ModuleNotFoundError.
  This codebase already standardizes on httpx (paired with tenacity for
  retries) for HTTP calls elsewhere -- rewritten to use httpx instead,
  which was already installed, so no requirements.txt change or image
  rebuild was needed. LESSON NOTED: check requirements.txt before
  assuming a library is available in a new module, rather than
  assuming based on what's typical in similar codebases.
  TEST ARTIFACT, NOT A BUG: live testing produced two 401 Unauthorized
  responses on GET /repo-stats/github-rate-limit and POST .../refresh.
  Root-caused to testing methodology, not code: both calls were made
  directly through FastAPI's /docs Swagger UI without first using its
  Authorize button to attach a bearer token, so require_admin()'s
  underlying get_current_user() correctly rejected them as
  unauthenticated (401, not 403 -- confirming this is "no token
  presented" rather than "valid non-admin user rejected"). No code
  change was needed; noting this here only so the same false alarm
  isn't re-investigated from scratch in a future session. Neither
  endpoint has a frontend button yet (github-rate-limit was built
  API-only in this session) -- a natural small follow-up would be
  surfacing remaining quota somewhere on the admin UI, e.g. next to the
  existing Refresh Now / Refresh All Benchmarks buttons on
  RepoStatsPanel.tsx, but this was not requested or built this session.

- 2026-08-16 (later, evening): Closed the frontend gap on items 14/15 --
  both had shipped backend-only with no way to see them from the UI.
  Added a "Show full history" toggle to RepoStatsPanel.tsx (calls the
  existing GET /repo-stats/benchmarks/{id}?history=true), and a GitHub
  API Quota readout (remaining/limit/reset time, turning red under 50
  remaining) that also surfaces refresh_all_repo_stats()'s
  skipped_due_to_rate_limit result inline instead of a vague failure.
  No backend changes needed -- both endpoints already worked correctly.

- 2026-08-23: Began Phase 5 in earnest. Shipped the first deliverable:
  a public (no login required) /browse page and /browse/[id] detail
  page, reusing GET /benchmarks (status=published), GET /benchmarks/
  {id}/metrics, and GET /repo-stats/benchmarks/{id} -- all already had
  no auth dependency, so this was a pure frontend addition. Added
  RepoStaleness.tsx: a staleness badge built from is_archived/
  days_since_last_activity (unambiguous columns), displayed alongside
  the raw activity_status string rather than replacing it, since
  github_scrapper.py's/hf_scrapper.py's exact activity_status value set
  was never fully verified in this project. Two gaps flagged honestly
  rather than papered over: License/Language Support filters are
  client-side only (list_benchmarks has no query params for either;
  works today only because the catalogue fits in one limit=200 fetch --
  will not scale indefinitely); Use Case filtering was deferred entirely
  at this point, since no backend data model existed for it yet.

- 2026-08-23 (later): Integrated the admin user's prior offline analysis
  scripts (use_case_filter.py, research_gap_heatmap.py) as live,
  deterministic classifiers, closing the Use Case filter gap from
  earlier the same day and adding the Research Gap Heatmap (Phase 5).
  Following the same architectural principle Section 2 already applies
  to complexity_classifier.py -- reproducible/auditable classification
  must be a deterministic tool, not model recall -- added:
  app/core/use_case_classifier.py (ports use_case_filter.py's six-
  category keyword scoring: Medical AI, Financial Services, Customer
  Service Chatbots, Content Moderation, Education, General Purpose) and
  app/core/safety_dimension_classifier.py (ports research_gap_heatmap.py's
  ten safety-dimension keyword mapping plus its exact gap-severity rules:
  Critical Gap / Under-benchmarked / Limited Advanced / Well-covered).
  One deliberate cleanup during the port: the original script's Content
  Moderation keyword list had a literal duplicate ('moderation' twice) --
  a no-op typo, deduplicated with no behavior change.
  Added use_cases and safety_dimensions as new ARRAY(Text) columns on
  benchmarks (migration -- see length-limit note below), computed
  automatically on every create/update in app/routers/benchmarks.py and
  at extraction time in agent_runner.py (patched per
  agent_runner_use_case_patch.md), never user-settable directly
  (BenchmarkUpdate does not declare either field, and has extra="forbid").
  Added GET /stats/research-gap-heatmap (public, computed live in Python
  over published benchmarks rather than as a materialized SQL view,
  despite Section 4 naming one -- simpler to keep in sync with the
  classifier module at the catalogue's current size; revisit if it grows
  large). Added app/scripts/backfill_use_case_safety_dimensions.py
  (unconditionally safe to re-run, unlike backfill_repo_stats.py, since
  both classifiers are pure functions -- recomputing is never destructive).
  Frontend: Use Case became a real server-side filter on both /browse and
  /admin/benchmarks (Benchmark.use_cases.any(), mirroring task_type's
  existing pattern); added /browse/heatmap; BenchmarkForm.tsx gained a
  read-only info box showing the auto-classified values in edit mode.
  DESIGN NOTE: /vocab was NOT modified to serve use_cases (its full
  content was never verified in this session, so left untouched rather
  than blind-edited) -- the six category labels are instead a hardcoded
  USE_CASE_CATEGORIES constant in frontend/lib/api.ts, which must be kept
  in sync by hand with app/core/use_case_classifier.py's
  USE_CASE_MAPPING keys if either ever changes. This is a real, if
  narrow, maintenance seam -- see Known Gaps item 19.

- 2026-08-23 (later): Migration 0007 failed on first attempt with
  psycopg2.errors.StringDataRightTruncation: value too long for type
  character varying(32) -- the THIRD time this exact class of bug has
  hit this project (see the 2026-07-18 Change Log entries for migrations
  0001/0002). Root cause was identical: the revision id
  "0007_add_use_case_safety_dim_cols" (33 characters) exceeded Alembic's
  own hardcoded alembic_version.version_num VARCHAR(32) column, and this
  should have been checked before naming it, since the lesson was
  already written down in this very file. Since the failure happened on
  Alembic's own bookkeeping insert (not the op.add_column() calls
  themselves) and Alembic runs under transactional DDL, the whole
  transaction rolled back cleanly -- fixed by shortening to
  "0007_use_case_safety_dim_cols" (29 characters) and re-running with no
  other cleanup needed. PROCESS LESSON (stated plainly so it is not
  learned a fourth time): any new Alembic revision id must be checked
  against len(revision) <= 32 before the migration file is finalized,
  every time, not just recalled as a general risk.

- 2026-08-23 (later): A real extraction job submitted against
  anthropic/claude-3-5-sonnet-20241022 failed with
  anthropic.NotFoundError: 404 model not found. Verified against
  platform.claude.com/docs/en/about-claude/model-deprecations and
  endoflife.date/claude: this exact model was deprecated 2025-08-13 and
  fully retired 2025-10-28 -- it had been non-functional for roughly 10
  months, silently, since it was never actually invoked until this test.
  Removed both retired Claude 3.5 Sonnet snapshots (20241022 and
  20240620) from the Agent Extraction Panel's model dropdown; added
  anthropic/claude-opus-5, which had been priced in cost_tracking.py
  since the Ollama Cloud work but never actually exposed as a selectable
  option. Kept both retired snapshots' pricing entries in
  cost_tracking.py, clearly marked RETIRED, so re-running
  estimate_cost_usd() against any already-completed historical
  ExtractionJob row does not silently reinterpret its cost -- they must
  never be re-added to the dropdown. PROCESS LESSON: any model ID with a
  date suffix (e.g. -20241022) must be checked against the provider's
  own deprecation/lifecycle page specifically, not just its pricing
  page, before being added anywhere -- pricing pages do not reliably
  flag retirement.

- 2026-08-23 (later): Admin user reported benchmarks stuck at
  Benchmark.status="pending_review" indefinitely, with no way to filter/
  approve them on the Extraction Panel and no way to change status even
  when editing the benchmark directly. Root cause: two separate status
  fields had been conflated in the original design. Every extracted
  benchmark gets Benchmark.status="pending_review" unconditionally in
  agent_runner.py, but the linked ExtractionJob only gets
  job.status="needs_review" if quality_score < 0.75 -- a high-scoring
  run gets job.status="done" immediately, even though its benchmark is
  still pending_review. The Extraction Panel's Pending Review queue
  filtered on job.status=="needs_review" only, so every benchmark from a
  "done"-status job was invisible to it with zero admin-frontend path to
  approve. Separately confirmed BenchmarkForm.tsx never exposed status
  as an editable field at all (explicitly destructured out of the save
  payload), so there was never a manual escape hatch either -- this was
  a genuine dead end, not user error.
  Fixed two ways: (1) ExtractionJobOut gained a computed
  result_benchmark_status field (batch-joined in
  app/routers/extraction.py's list_jobs()/get_job(), not a real column),
  and the Pending Review queue now filters on the BENCHMARK's actual
  status instead of the job's, so every pending_review benchmark shows
  up regardless of its job's quality tier. (2) Added a new,
  benchmark-centric POST /benchmarks/{id}/review endpoint plus a
  ReviewPanel.tsx component directly on the benchmark edit page --
  reviewable without needing to know which job produced it, and updates
  the linked job's status too (if one exists) for consistency with the
  existing job-based review path. The review panel also surfaces
  complexity_level/complexity_justification inline so a reviewer can see
  the extraction's own stated uncertainty before deciding, addressing
  the admin user's request to "see the uncertainties" during review.
  No agent_runner.py changes were made -- the job.status="done" vs.
  "needs_review" split itself was left as-is (a job-level quality-run
  signal), since the fix above makes it irrelevant to whether a
  benchmark shows up for review, without touching that already
  partially-visible file further.

  - 2026-08-25/26: Phase 5 gap closure session. Added License,
  Language Support, and Release Date (release_date_from/
  release_date_to) as real server-side filters on GET /benchmarks;
  added public GET /export/public/xlsx and GET /export/public/csv
  (published-only, no auth); added slowapi rate limiting across all
  public endpoints (app/core/rate_limit.py, wired in main.py via
  app.state.limiter + SlowAPIMiddleware, 100/minute global default
  plus tighter explicit limits on GET /benchmarks,
  GET /benchmarks/{id}, GET /repo-stats/benchmarks/{id} at 60/minute,
  GET /stats/research-gap-heatmap at 20/minute, and both
  /export/public/* routes at 10/minute). Frontend: /browse gained
  server-side License/Language Support/Release Date filters (replacing
  the old client-side-only filtering) and an Export section; added
  frontend/.nvmrc pinning Node 20.14.2 after a local dev environment
  issue running Next.js 14.2.5 under Node 16.20.2 (Next.js requires
  Node >= 18.17, most current docs recommend >= 20.9); resolved a
  Docker-created root-owned node_modules permission issue on macOS via
  sudo rm -rf plus a documented docker-compose.yml user: UID/GID fix
  for future container runs.

  Ollama Cloud subscription blocker (Known Gap item 17) investigated:
  confirmed still blocked on account/billing tier, not code (Ollama's
  Free tier gates deepseek-v4-pro and the other five ollama/* models
  behind a paid Pro-or-higher plan; Max is currently paused for new
  subscriptions). Error handling improved: agent_runner.py's provider
  dispatch now catches this specific 403 PermissionDeniedError via a
  new _wrap_provider_error() helper and raises a clear, actionable
  message instead of a raw stack trace; ExtractionJob gained a new
  failure_reason column (migration
  0005_add_extraction_job_failure_reason.py) populated on any job
  failure, exposed via ExtractionJobOut. The subscription itself was
  not upgraded this session -- item 17 remains open pending that
  account decision.

  Known Gap item 19 (USE_CASE_CATEGORIES duplication) resolved:
  app/core/controlled_vocab.py's USE_CASES now re-exports
  app/core/use_case_classifier.py's USE_CASE_CATEGORIES directly
  instead of maintaining a separate hand-copied list. This also
  surfaced and fixed a real latent bug -- the old controlled_vocab.py
  list was missing "Customer Service Chatbots," meaning GET /vocab's
  use_cases key had been silently incomplete since Phase 5 shipped.
  frontend/lib/api.ts's hardcoded USE_CASE_CATEGORIES constant was
  removed; /browse and /admin/benchmarks (which previously had no
  vocab fetch at all) both now read use_cases from GET /vocab.

- 2026-08-26: Phase 6 items 1 and 2 shipped.
  (1) Weekly citation-count refresh: new Celery tasks
  refresh_citation_count_for_benchmark (manual/single trigger) and
  refresh_all_citation_counts (scheduled bulk trigger, Celery Beat,
  Sundays 04:00 UTC -- one hour after the existing weekly repo_stats
  job to avoid both jobs contending for a worker slot at the same
  instant). Reuses paper_fetcher.py's existing
  fetch_semantic_scholar_citation_count(), already proven during
  Phase 3 extraction. Deliberately processes benchmarks SEQUENTIALLY
  within a single task (1.1s delay between calls) rather than fanning
  out into per-benchmark delayed tasks the way refresh_all_repo_stats
  does for GitHub/HuggingFace, since Semantic Scholar's unauthenticated
  tier caps at 1 request/second and concurrent Celery workers could
  otherwise burst past that regardless of each call's internal retry
  logic. Automatically promotes complexity_level to "Popular" when a
  refreshed citation count crosses complexity_classifier.py's
  POPULAR_CITATION_THRESHOLD (100) and the benchmark isn't already
  Popular -- this only uses the citation_count OR-branch of classify()'s
  three Popular conditions (the other two,
  cited_as_baseline_in_3plus_papers and is_community_standard, and all
  High/Medium signal booleans, are not persisted on the Benchmark row
  today, so a full re-classification remains out of scope for this
  automated job); never demotes an existing classification. Every
  actual change is written to audit_log via the existing log_action()
  helper with changed_by=None, distinguishing system-triggered changes
  from human admin edits.
  (2) Full version history per benchmark: required NO backend changes
  -- GET /audit-log already supported table_name and record_id query
  params, and every benchmark create/update/delete/approve/reject
  action already wrote a row there since Phase 2. Added a new
  VersionHistoryPanel.tsx component (read-only, expandable per-entry
  diff view, generic JSON rendering since diff shape varies by action
  type) and wired it into the existing /admin/benchmarks/{id} edit
  page below RepoStatsPanel.

  Environment note: running `celery -A app.core.celery_app worker`
  directly on the host (outside Docker) failed to connect to Redis
  with "Cannot connect to redis://redis:6379/0: nodename nor servname
  provided, or not known" -- the hostname `redis` only resolves inside
  the Docker Compose network. Resolved by running Celery worker and
  Beat inside the backend container instead
  (docker compose exec backend celery -A app.core.celery_app worker /
  beat), which shares the Compose network with the redis service.
  LESSON LEARNED: local (non-Docker) Celery development needs
  REDIS_URL overridden to redis://localhost:6379/0 (with the redis
  service's port published to the host); running everything inside
  Docker avoids this entirely and is the path that was actually
  verified working this session.

## 9. Known Gaps (as of 2026-08-28)

  PICK UP HERE NEXT SESSION: Phase 6 items 1-4 are all now shipped and
  live-tested as of 2026-08-27 (weekly citation refresh, version
  history, in-app notifications, and the gated community submission
  workflow). The submission workflow's core plumbing, validation
  layers, review flow, and role/security boundaries are all verified
  working end-to-end. The one open, top-priority item is Known Gap
  NN (this session's numbering) -- giving the free-tier community
  extraction model real web search capability via Ollama's own free
  web_search API, so it can actually find code_repository/
  dataset_repository links instead of relying on whatever the paper's
  abstract happens to state verbatim. This is real engineering work
  (a multi-turn tool-calling loop, not a config change) and deserves
  a dedicated session rather than a quick patch. Other candidates, in
  rough priority order: (a) the Ollama Cloud subscription upgrade
  decision (Known Gap item 17) is still not made -- paid-tier models
  remain unverified in practice; (b) email notification channel
  activation (SMTP_HOST) if the admin user wants submitters/admins
  notified outside the in-app bell; (c) admin UI for managing
  is_trusted_submitter (currently API-only via POST
  /users/{id}/trust?trusted=true, no frontend page yet).
  Admin re-processing of agent extractions is not idempotent at the 
  benchmark level. Re-running the admin extraction pipeline for a 
  researcher submission currently inserts a new benchmark row instead 
  of updating the benchmark already associated with that job, despite 
  version history being available for CRUD updates.

Still open:

11. [RESOLVED 2026-08-16] Reject-action behavior was unconfirmed:
   does it re-trigger run_extraction(), or does the admin need to
   manually resubmit a new job with the same source_value? Confirmed
   by reading the actual review_job() code in
   app/routers/extraction.py: rejecting only sets
   benchmark.status="rejected" and job.status="failed" -- it does
   NOT re-trigger run_extraction() or create a new job. To retry, the
   admin must manually resubmit via POST /extraction/jobs with the
   same source_type/source_value. Documentation-only fix, no code
   change required. See 2026-08-16 Change Log entry above.
12. [RESOLVED 2026-08-16] No per-run cost or run-to-run variance
   tracking existed for agent extraction jobs, despite being called
   out as a goal in Phase 3's original scope. Fixed: added
   input_tokens/output_tokens/estimated_cost_usd columns to
   extraction_jobs (migration 0005_add_extraction_cost_cols),
   app/core/cost_tracking.py's pricing table (OpenAI, Anthropic,
   Gemini, Kimi, DeepSeek, Qwen), and GET
   /extraction/jobs/variance?source_value= for run-to-run stats.
   agent_runner.py's _call_openai/_call_anthropic now capture and
   persist token usage. Frontend: cost/token readout on every job
   card plus a "Check Prior Runs & Cost" button. See 2026-08-16
   Change Log entry above for full detail, including a Decimal-
   serialized-as-string frontend bug found and fixed the same
   session.
13. [RESOLVED 2026-08-16] Phase 4's Celery tasks
   (refresh_repo_stats_for_benchmark, refresh_all_repo_stats) were
   only triggerable via a Python shell (.delay() calls) or the weekly
   Beat schedule -- no admin-UI button or API route existed to
   manually trigger a refresh for one benchmark or all benchmarks.
   Fixed: repaired two live bugs in the already-scaffolded but never-
   wired app/routers/repo_stats.py (a NameError referencing an
   undefined RepoStats instead of RepoStat, and a RepoStatsOut schema
   that declared fields not present on the RepoStat ORM model at
   all), then added RepoStatsPanel.tsx to the admin benchmark edit
   page with Reload / Refresh Now / Refresh All Benchmarks buttons
   wired to the now-fixed router. See 2026-08-16 Change Log entry
   above.
14. [RESOLVED 2026-08-16] GitHub's unauthenticated rate limit
   headroom was previously unverified at scale and undiscoverable
   except by hitting it and seeing 403s. Fixed with
   app/core/github_rate_limit.py's pre-flight quota check (now run
   automatically before every bulk refresh) and a new admin-only
   GET /repo-stats/github-rate-limit endpoint for on-demand
   visibility. See 2026-08-16 Change Log entry above for full
   detail, including a requests-vs-httpx dependency bug found and
   fixed during rollout.
15. [RESOLVED 2026-08-16] repo_stats previously only ever held the
   latest fetched value per benchmark+source (update-in-place),
   with no historical time series. Fixed: app/core/tasks.py now
   always inserts a new snapshot row; the
   repository_activity_statistics view and the GET
   /repo-stats/benchmarks/{id} endpoint were both updated to keep
   showing only the latest row by default (via ROW_NUMBER()/subquery
   filtering) so nothing else broke, with a new ?history=true option
   to retrieve the full time series when actually wanted (e.g. a
   future star/like growth chart). See 2026-08-16 Change Log entry
   above.
16. [RESOLVED 2026-08-16] list_benchmarks (GET /benchmarks) had no
   status filter at all, so rejected benchmarks (status="rejected"
   is set on reject, but the row is never deleted) remained visible
   indefinitely with no way to exclude them -- a problem for both
   the admin list and the planned Phase 5 public browse view, which
   is designed to reuse this same endpoint. Fixed same-day: default
   excludes status="rejected" only; explicit ?status= filter added
   for any caller; admin frontend gained a Status column and filter
   dropdown. See 2026-08-16 Change Log entry above for full detail.
17. [STILL OPEN as of 2026-08-26, error handling improved] Ollama
   Cloud integration (_call_ollama(), the "ollama" provider branch,
   and six ollama/* dropdown options) is implemented and the code
   path is confirmed reachable (auth succeeds, requests land on
   Ollama's API), but EVERY live test so far has failed with a 403
   PermissionDeniedError: "this model requires a subscription,
   upgrade for access." This means no ollama/* model has actually
   completed an extraction end-to-end yet -- the integration remains
   unverified in practice, blocked purely on account/billing tier,
   not code. The underlying blocker is unchanged: Ollama Cloud's Free
   tier gates deepseek-v4-pro, deepseek-v4-flash, kimi-k3, kimi-k2.6,
   qwen3.5:397b, and qwen3-coder:480b behind a paid Pro ($20/mo) or
   higher plan; Max is currently paused for new subscriptions.

   IMPROVED 2026-08-26: this failure mode is no longer a raw,
   undiagnosable stack trace. agent_runner.py's provider dispatch in
   run_extraction() is now wrapped in a new _wrap_provider_error()
   helper that detects the ollama + openai.PermissionDeniedError
   combination specifically and raises a clear ValueError instead
   ("Ollama Cloud rejected model '<name>': the current account
   subscription tier does not include this model..."). Separately,
   ExtractionJob gained a new failure_reason Text column (migration
   0005_add_extraction_job_failure_reason.py) that the run_extraction()
   except block now populates on ANY job failure (not just this one),
   truncated to 2000 chars -- previously a failed job's cause was only
   visible in backend logs via logger.exception(), with nothing
   persisted for the admin frontend or GET /extraction/jobs to surface.
   ExtractionJobOut.failure_reason exposes this via the API.

   Still requires, before relying on any of the six gated models in
   real use: (1) upgrade the Ollama Cloud subscription at
   https://ollama.com/upgrade, (2) re-run a real test job per model
   actually intended for use, and (3) specifically check whether
   _extract_last_balanced_json() has to fall back more often than
   with gpt-4o/claude, since strict JSON mode reliability on
   open-weight models via Ollama's OpenAI-compatibility layer has not
   been verified either. The subscription upgrade itself was not
   performed this session -- this remains blocked on an account/
   billing decision, not code.
18. [RESOLVED 2026-08-23] Benchmarks could get stuck at
  status="pending_review" indefinitely: the Extraction Panel's
  Pending Review queue filtered on job.status=="needs_review" only,
  missing every benchmark whose job scored high enough to become
  job.status="done" immediately, and BenchmarkForm.tsx never
  exposed status as an editable field at all. Fixed with a computed
  result_benchmark_status field on ExtractionJobOut (the queue now
  filters on the benchmark's real status) and a new benchmark-
  centric POST /benchmarks/{id}/review endpoint plus ReviewPanel.tsx
  directly on the benchmark edit page. See 2026-08-23 Change Log
  entry above for full detail.
19. [NEW 2026-08-23, OPEN] USE_CASE_CATEGORIES is duplicated by hand
  between app/core/use_case_classifier.py (backend, source of truth
  for actual classification) and frontend/lib/api.ts (a hardcoded
  constant, used only for the filter dropdown). /vocab was
  deliberately not modified to serve this list, since its full
  content was never verified in this session and blind-editing an
  unseen file was judged riskier than a small, explicit duplication.
  If the six category labels ever change, both places must be
  updated by hand or the dropdown will silently drift from what the
  classifier actually produces.
20. [NEW 2026-08-23, OPEN] GET /stats/research-gap-heatmap computes
  its aggregation live in Python on every request, over every
  published benchmark, rather than as the materialized view Section
  4's original schema-mapping table named. Fine at the catalogue's
  current size (182+ benchmarks); revisit as a real materialized
  view (or at least a cached/scheduled aggregate) if the catalogue
  grows large enough for this to become a measurable per-request
  cost.
21. [NEW 2026-08-23, OPEN] /browse's License and Language Support
  filters remain client-side only (list_benchmarks has no query
  params for either), same limitation flagged when /browse first
  shipped -- unchanged since then. Works today only because the
  full catalogue fits in one limit=200 fetch.
22. [NEW 2026-08-23, OPEN] Every endpoint exposed for Phase 5's
  public dashboard (GET /benchmarks, /benchmarks/{id},
  /benchmarks/{id}/metrics, /repo-stats/benchmarks/{id},
  /stats/research-gap-heatmap) has no authentication requirement,
  which was always true and intentional for a public dashboard --
  but also no rate limiting of any kind, which Phase 5's own scope
  explicitly calls for ("Public read-only REST API with rate
  limiting") and which does not exist yet at all.
23. [NEW 2026-08-27, TOP PRIORITY] Community submission model
  (ollama/gpt-oss:120b-cloud) has no web search capability, so it
  cannot reliably populate code_repository/dataset_repository for a
  community submission -- confirmed via live testing after fixing
  four separate bugs that were blocking extraction from completing
  at all (JSON parsing, empty response/max_tokens, an impossible
  "you must search" instruction inherited from the shared Anthropic-
  oriented prompt code, and a frontend Decimal-serialization crash).
  See the "Community Submission Workflow" subsection under Phase 6
  for full detail and the recommended fix (Ollama's own free
  web_search API + a tool-calling loop in _call_ollama()). Workaround
  in the meantime: admins use POST /submissions/{id}/reextract with a
  paid model for any submission needing those fields filled in.

24. [NEW 2026-08-27, RESOLVED SAME SESSION] UserCreate previously
  allowed client-controlled self-registration as role="admin" via
  POST /auth/register. Fixed -- see "SECURITY FIX" in the Community
  Submission Workflow subsection above. Flagging here too since this
  was a pre-existing vulnerability unrelated to Phase 6, discovered
  only because Phase 6 required treating "researcher" as a real,
  trusted-boundary role for the first time.

25. [NEW 2026-08-27, RESOLVED SAME SESSION] POST /submissions
  accepted admin accounts, causing notification cross-contamination
  and a self-review risk. Fixed via require_researcher() plus
  frontend route guards (app/admin/layout.tsx). See "ROLE-SEPARATION
  BUG" in the Community Submission Workflow subsection above.
