// Destination path: frontend/lib/api.ts
// Replaces the existing file in full.
//
// BUG FIX (this session): TypeError: s.quality_score.toFixed is not a
// function, thrown on /submit and /admin/submissions. Root cause:
// FastAPI/Pydantic serializes Decimal columns (Submission.quality_score
// is a Postgres Numeric(3,2), see models/orm.py) as JSON STRINGS (e.g.
// "0.75"), not numbers -- but the Submission TypeScript interface
// declared quality_score as `number | null`, so every consumer
// trusted a type the API never actually provided. The existing admin
// Extraction Panel (app/admin/extraction/page.tsx) already works
// around this same class of bug defensively at each render site via
// Number(job.quality_score); this fix instead normalizes ONCE at the
// API boundary via normalizeSubmission(), applied to every function
// that returns a Submission or Submission[], so every current and
// future consumer of this type can trust quality_score is a real
// number (or null) without needing its own defensive Number() call.
// No other type, function, or behavior in this file changed.

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
  submission_source?: string;
  submitted_by_user_id?: string | null;
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
  result_benchmark_status: string | null;
  submitted_by: string | null;
  input_tokens: number | null;
  output_tokens: number | null;
  estimated_cost_usd: number | null;
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

export interface UserOut {
  id: string;
  email: string;
  role: "admin" | "researcher";
  is_trusted_submitter: boolean;
  created_at: string;
}

export async function registerUser(email: string, password: string) {
  const { data } = await api.post<UserOut>("/auth/register", { email, password });
  return data;
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
  const { data } = await api.get<UserOut>("/auth/me");
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

export function exportPublicXlsxUrl() {
  return `${API_BASE_URL}/export/public/xlsx`;
}

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

export async function reviewExtractionJob(id: string, approve: boolean, reviewer_note?: string) {
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
  const { data } = await api.get<MetricsCompleteness>(`/benchmarks/${benchmarkId}/metrics/completeness`);
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

// ---- Phase 6: community submissions ----

export interface Submission {
  id: string;
  submitter_user_id: string;
  source_type: string;
  source_value: string;
  model_used: string;
  status: string;
  extraction_job_id: string | null;
  result_benchmark_id: string | null;
  domain_check_passed: boolean | null;
  domain_check_reason: string | null;
  quality_score: number | null;
  admin_reviewer_id: string | null;
  admin_review_notes: string | null;
  created_at: string;
  updated_at: string;
  reviewed_at: string | null;
}

/** BUG FIX: FastAPI serializes Submission.quality_score (a Postgres
 * Numeric(3,2) / Python Decimal) as a JSON STRING, not a number --
 * e.g. "0.75" rather than 0.75. Every function below that returns a
 * Submission or Submission[] passes its raw response through this
 * normalizer so every consumer of the Submission type can trust
 * quality_score really is `number | null`, matching the interface
 * above, instead of needing its own defensive Number(...) call at
 * every render site (which is how this bug slipped through -- the
 * interface claimed a type the API never actually provided). */
function normalizeSubmission(raw: any): Submission {
  return {
    ...raw,
    quality_score: raw.quality_score !== null && raw.quality_score !== undefined
      ? Number(raw.quality_score)
      : null,
  };
}

export async function createSubmission(source_value: string) {
  const { data } = await api.post<Submission>("/submissions", { source_value });
  return normalizeSubmission(data);
}

export async function listMySubmissions() {
  const { data } = await api.get<Submission[]>("/submissions/mine");
  return data.map(normalizeSubmission);
}

export async function listAllSubmissions(statusFilter?: string) {
  const params = statusFilter ? { status: statusFilter } : {};
  const { data } = await api.get<Submission[]>("/submissions", { params });
  return data.map(normalizeSubmission);
}

export async function getSubmission(id: string) {
  const { data } = await api.get<Submission>(`/submissions/${id}`);
  return normalizeSubmission(data);
}

export async function reviewSubmission(
  id: string,
  decision: "approve" | "reject" | "needs_better_extraction",
  reviewer_notes?: string
) {
  const { data } = await api.post<Submission>(`/submissions/${id}/review`, {
    decision,
    reviewer_notes,
  });
  return normalizeSubmission(data);
}

export async function reextractSubmission(id: string, model_used: string) {
  const { data } = await api.post<Submission>(`/submissions/${id}/reextract`, { model_used });
  return normalizeSubmission(data);
}

// ---- Phase 6: notifications ----

export interface AppNotification {
  id: string;
  notification_type: string;
  title: string;
  body: string | null;
  link_path: string | null;
  is_read: boolean;
  created_at: string;
}

export async function listNotifications(unreadOnly = false) {
  const { data } = await api.get<AppNotification[]>("/notifications", {
    params: unreadOnly ? { unread_only: true } : {},
  });
  return data;
}

export async function getUnreadNotificationCount() {
  const { data } = await api.get<{ unread_count: number }>("/notifications/unread-count");
  return data.unread_count;
}

export async function markNotificationRead(id: string) {
  const { data } = await api.post<AppNotification>(`/notifications/${id}/read`);
  return data;
}

export async function markAllNotificationsRead() {
  const { data } = await api.post<{ marked_read: number }>("/notifications/read-all");
  return data;
}

// ---- Phase 6: admin user management ----

export async function listUsers(params?: { search?: string; role?: string }) {
  const { data } = await api.get<UserOut[]>("/users", { params });
  return data;
}

export async function setTrustedSubmitter(userId: string, trusted: boolean) {
  const { data } = await api.post<UserOut>(`/users/${userId}/trust`, null, {
    params: { trusted },
  });
  return data;
}
