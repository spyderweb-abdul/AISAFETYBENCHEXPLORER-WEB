// Destination path: frontend/lib/api.ts
// Replaces the existing file in full.
//
// CHANGE (Known Gap item 19 fix, this session): removed the hardcoded
// USE_CASE_CATEGORIES constant entirely. It was a manually-copied
// duplicate of app/core/use_case_classifier.py's real category list
// and had no mechanism to stay in sync with the backend -- the
// backend's own controlled_vocab.py copy had already drifted (missing
// "Customer Service Chatbots"), and this frontend copy only happened
// to still be correct by luck. Consumers (browse/page.tsx,
// admin/benchmarks/page.tsx) now read use_cases directly off the
// Vocab returned by fetchVocab() / GET /vocab, which is itself now
// re-exported from the classifier (see controlled_vocab.py), making
// it the single source of truth end to end. No other export,
// interface, or function changed from the previous version of this
// file (includes the exportPublicXlsxUrl/exportPublicCsvUrl additions
// from the earlier Phase 5 session).

import axios from "axios";
import Cookies from "js-cookie";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

export const api = axios.create({ baseURL: API_BASE_URL });

api.interceptors.request.use((config) => {
  const token = Cookies.get("access_token");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

export interface Benchmark {
  id: string;
  benchmark_name: string;
  task_type: string[];
  benchmark_paper_title: string;
  release_date: string | null;
  description: string | null;
  code_dataset: string;
  no_of_samples: string | null;
  created_by: string | null;
  entry_modalities: string[];
  dev_purpose: string | null;
  license: string | null;
  evaluation_metrics: string[];
  complexity_level: string;
  complexity_justification: string | null;
  language_support: string[];
  integration_option: string;
  citation_range: string | null;
  cited_by: number;
  code_repository: string | null;
  dataset_repository: string | null;
  paper_link: string | null;
  status: string;
  use_cases: string[];
  safety_dimensions: string[];
  created_at: string;
  updated_at: string;
}

export interface Vocab {
  task_type: string[];
  created_by: string[];
  dev_purpose: string[];
  integration_option: string[];
  complexity_level: string[];
  code_dataset: string[];
  use_cases: string[];
  entry_modalities: string[];
  language_support: string[];
}

export interface AuditLogEntry {
  id: string;
  table_name: string;
  record_id: string;
  action: string;
  changed_by: string | null;
  diff: Record<string, unknown> | null;
  created_at: string;
}

export interface ExtractionJob {
  id: string;
  source_type: string;
  source_value: string;
  model_used: string | null;
  status: string;
  quality_score: number | null;
  requires_review: boolean;
  result_benchmark_id: string | null;
  /** FIX (2026-08-23): the linked benchmark's actual status, since
   * job.status alone doesn't reveal whether the benchmark is still
   * pending_review -- a high quality_score job can be job.status=
   * "done" while its benchmark sits at pending_review indefinitely. */
  result_benchmark_status: string | null;
  submitted_by: string | null;
  input_tokens: number | null;
  output_tokens: number | null;
  estimated_cost_usd: number | null;
  /** Known Gap item 17 follow-up: human-readable reason for a
   * status="failed" job. Null for jobs that never failed. */
  failure_reason?: string | null;
  created_at: string;
  completed_at: string | null;
}

export interface JobVariance {
  source_value: string;
  run_count: number;
  mean_quality_score: number | null;
  stddev_quality_score: number | null;
  total_estimated_cost_usd: number | null;
  job_ids: string[];
}

export async function login(email: string, password: string) {
  const form = new URLSearchParams();
  form.append("username", email);
  form.append("password", password);
  const { data } = await api.post("/auth/login", form, {
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
  });
  return data as { access_token: string; token_type: string };
}

export async function fetchMe() {
  const { data } = await api.get("/auth/me");
  return data;
}

export async function listBenchmarks(params?: Record<string, string | number>) {
  const { data } = await api.get<Benchmark[]>("/benchmarks", { params });
  return data;
}

export async function getBenchmark(id: string) {
  const { data } = await api.get<Benchmark>(`/benchmarks/${id}`);
  return data;
}

export async function createBenchmark(payload: Partial<Benchmark>) {
  const { data } = await api.post<Benchmark>("/benchmarks", payload);
  return data;
}

export async function updateBenchmark(id: string, payload: Partial<Benchmark>) {
  const { data } = await api.patch<Benchmark>(`/benchmarks/${id}`, payload);
  return data;
}

export async function deleteBenchmark(id: string) {
  await api.delete(`/benchmarks/${id}`);
}

/** FIX (2026-08-23): benchmark-centric review, reachable directly from
 * the benchmark edit page -- see ReviewPanel.tsx. Backs
 * POST /benchmarks/{id}/review. */
export async function reviewBenchmark(id: string, approve: boolean, reviewer_note?: string) {
  const { data } = await api.post<Benchmark>(`/benchmarks/${id}/review`, {
    approve,
    reviewer_note,
  });
  return data;
}

export async function classifyComplexity(signals: Record<string, boolean | number>) {
  const { data } = await api.post("/complexity/classify", signals);
  return data as { complexity_level: string; justification: string };
}

export async function fetchVocab() {
  const { data } = await api.get<Vocab>("/vocab");
  return data;
}

export async function fetchAuditLog(params?: Record<string, string>) {
  const { data } = await api.get<AuditLogEntry[]>("/audit-log", { params });
  return data;
}

export function exportXlsxUrl() {
  return `${API_BASE_URL}/export/xlsx`;
}

/** Phase 5: public, unauthenticated, published-only Excel export used
 * by the /browse dashboard's Export section. Backs GET /export/public/xlsx. */
export function exportPublicXlsxUrl() {
  return `${API_BASE_URL}/export/public/xlsx`;
}

/** Phase 5: public, unauthenticated, published-only CSV export used
 * by the /browse dashboard's Export section. Backs GET /export/public/csv. */
export function exportPublicCsvUrl() {
  return `${API_BASE_URL}/export/public/csv`;
}

export async function submitExtractionJob(payload: {
  source_type: string;
  source_value: string;
  model_used: string;
}) {
  const { data } = await api.post<ExtractionJob>("/extraction/jobs", payload);
  return data;
}

export async function listExtractionJobs(statusFilter?: string) {
  const params = statusFilter ? { status: statusFilter } : {};
  const { data } = await api.get<ExtractionJob[]>("/extraction/jobs", { params });
  return data;
}

export async function getExtractionJob(id: string) {
  const { data } = await api.get<ExtractionJob>(`/extraction/jobs/${id}`);
  return data;
}

export async function reviewExtractionJob(
  id: string,
  approve: boolean,
  reviewer_note?: string
) {
  const { data } = await api.post<ExtractionJob>(`/extraction/jobs/${id}/review`, {
    approve,
    reviewer_note,
  });
  return data;
}

export async function getJobVariance(sourceValue: string) {
  const { data } = await api.get<JobVariance>("/extraction/jobs/variance", {
    params: { source_value: sourceValue },
  });
  return data;
}


export interface EvalMetric {
  id: string;
  benchmark_id: string;
  benchmark_name: string;
  paper_title: string;
  paper_link: string | null;
  metric_name: string;
  conceptual_description: string | null;
  methodological_details: string | null;
  mathematical_definition: string | null;
  differences_from_standard_definition: string | null;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface MetricsCompleteness {
  benchmark_id: string;
  missing_metric_names: string[];
  is_complete: boolean;
}

export async function listMetricsForBenchmark(benchmarkId: string) {
  const { data } = await api.get<EvalMetric[]>(`/benchmarks/${benchmarkId}/metrics`);
  return data;
}

export async function checkMetricsCompleteness(benchmarkId: string) {
  const { data } = await api.get<MetricsCompleteness>(
    `/benchmarks/${benchmarkId}/metrics/completeness`
  );
  return data;
}

export async function createMetric(
  benchmarkId: string,
  payload: Omit<EvalMetric, "id" | "benchmark_id" | "created_at" | "updated_at">
) {
  const { data } = await api.post<EvalMetric>(`/benchmarks/${benchmarkId}/metrics`, {
    ...payload,
    benchmark_id: benchmarkId,
  });
  return data;
}

export async function updateMetric(metricId: string, payload: Partial<EvalMetric>) {
  const { data } = await api.patch<EvalMetric>(`/metrics/${metricId}`, payload);
  return data;
}

export async function deleteMetric(metricId: string) {
  await api.delete(`/metrics/${metricId}`);
}


export interface RepoStat {
  id: string;
  benchmark_id: string;
  source: string;
  url: string;
  owner: string | null;
  name: string | null;
  stars_or_likes: number | null;
  forks: number | null;
  open_issues: number | null;
  contributors_count: number | null;
  downloads: number | null;
  last_commit_at: string | null;
  days_since_last_activity: number | null;
  activity_status: string | null;
  is_archived: boolean;
  is_private: boolean;
  is_gated: boolean;
  license_id: string | null;
  fetch_error: string | null;
  fetched_at: string;
}

export async function listRepoStatsForBenchmark(benchmarkId: string, history = false) {
  const { data } = await api.get<RepoStat[]>(`/repo-stats/benchmarks/${benchmarkId}`, {
    params: history ? { history: true } : {},
  });
  return data;
}

export async function triggerRepoStatsRefresh(benchmarkId: string) {
  const { data } = await api.post<{ task_id: string; benchmark_id: string }>(
    `/repo-stats/benchmarks/${benchmarkId}/refresh`
  );
  return data;
}

export async function triggerRepoStatsRefreshAll() {
  const { data } = await api.post<{ task_id: string }>(`/repo-stats/refresh-all`);
  return data;
}

export interface GithubRateLimit {
  limit: number;
  remaining: number;
  reset_at: string;
  authenticated: boolean;
}

export async function getGithubRateLimit() {
  const { data } = await api.get<GithubRateLimit>("/repo-stats/github-rate-limit");
  return data;
}

export interface HeatmapDimension {
  dimension: string;
  popular: number;
  high: number;
  medium: number;
  low: number;
  total: number;
  gap_severity: string;
}

export interface ResearchGapHeatmap {
  total_benchmarks: number;
  dimensions: HeatmapDimension[];
}

export async function getResearchGapHeatmap() {
  const { data } = await api.get<ResearchGapHeatmap>("/stats/research-gap-heatmap");
  return data;
}
