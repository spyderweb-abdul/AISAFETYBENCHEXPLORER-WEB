// Destination path: frontend/lib/api.ts
// Replaces the existing file in full.
//
// CHANGE (2026-09-01): added VocabTerm type and listVocabTerms/
// createVocabTerm/updateVocabTerm/deleteVocabTerm functions, backing
// the new /admin/vocab CRUD page and backend/app/routers/vocab_terms.py.
// Appended after the ModelOption block added last session; everything
// else in this file is unchanged.

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
  const { data } = await api.post("/auth/register", { email, password });
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
  const { data } = await api.get("/auth/me");
  return data;
}

export async function listBenchmarks(params?: Record<string, unknown>) {
  const { data } = await api.get("/benchmarks", { params });
  return data;
}

export interface BenchmarkPage {
  items: Benchmark[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export async function listAdminBenchmarkPage(params?: Record<string, unknown>) {
  const { data } = await api.get<BenchmarkPage>("/benchmarks/admin/page", { params });
  return data;
}

export async function getBenchmark(id: string) {
  const { data } = await api.get(`/benchmarks/${id}`);
  return data;
}

export async function createBenchmark(payload: Partial<Benchmark>) {
  const { data } = await api.post("/benchmarks", payload);
  return data;
}

export async function updateBenchmark(id: string, payload: Partial<Benchmark>) {
  const { data } = await api.patch(`/benchmarks/${id}`, payload);
  return data;
}

export async function deleteBenchmark(id: string) {
  await api.delete(`/benchmarks/${id}`);
}

export async function reviewBenchmark(id: string, approve: boolean, reviewer_note?: string) {
  const { data } = await api.post(`/benchmarks/${id}/review`, {
    approve,
    reviewer_note,
  });
  return data;
}

export async function reextractBenchmark(id: string, modelUsed: string) {
  const { data } = await api.post<ExtractionJob>(`/benchmarks/${id}/reextract`, {
    model_used: modelUsed,
  });
  return data;
}

export async function classifyComplexity(signals: Record<string, unknown>) {
  const { data } = await api.post("/complexity/classify", signals);
  return data as { complexity_level: string; justification: string };
}

export async function fetchVocab() {
  const { data } = await api.get("/vocab");
  return data as Vocab;
}

export async function fetchAuditLog(params?: Record<string, unknown>) {
  const { data } = await api.get("/audit-log", { params });
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
  const { data } = await api.post("/extraction/jobs", payload);
  return data;
}

export async function listExtractionJobs(statusFilter?: string) {
  const params = statusFilter ? { status: statusFilter } : {};
  const { data } = await api.get("/extraction/jobs", { params });
  return data;
}

export async function getExtractionJob(id: string) {
  const { data } = await api.get(`/extraction/jobs/${id}`);
  return data;
}

export async function reviewExtractionJob(id: string, approve: boolean, reviewer_note?: string) {
  const { data } = await api.post(`/extraction/jobs/${id}/review`, {
    approve,
    reviewer_note,
  });
  return data;
}

export async function getJobVariance(sourceValue: string) {
  const { data } = await api.get("/extraction/jobs/variance", {
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
  const { data } = await api.get(`/benchmarks/${benchmarkId}/metrics`);
  return data;
}

export async function checkMetricsCompleteness(benchmarkId: string) {
  const { data } = await api.get(`/benchmarks/${benchmarkId}/metrics/completeness`);
  return data;
}

export async function createMetric(
  benchmarkId: string,
  payload: Omit<EvalMetric, "id" | "benchmark_id" | "created_at" | "updated_at">,
) {
  const { data } = await api.post(`/benchmarks/${benchmarkId}/metrics`, {
    ...payload,
    benchmark_id: benchmarkId,
  });
  return data;
}

export async function updateMetric(metricId: string, payload: Partial<EvalMetric>) {
  const { data } = await api.patch(`/metrics/${metricId}`, payload);
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
  const { data } = await api.get(`/repo-stats/benchmarks/${benchmarkId}`, {
    params: history ? { history: true } : {},
  });
  return data;
}

export async function triggerRepoStatsRefresh(benchmarkId: string) {
  const { data } = await api.post<{ task_id: string; citation_task_id: string; benchmark_id: string }>(
    `/repo-stats/benchmarks/${benchmarkId}/refresh`,
  );
  return data;
}

export async function triggerRepoStatsRefreshAll() {
  const { data } = await api.post<{ task_id: string; citation_task_id: string }>(`/repo-stats/refresh-all`);
  return data;
}

export interface PaperMetadata {
  id: string;
  benchmark_id: string;
  doi: string | null;
  arxiv_id: string | null;
  semantic_scholar_paper_id: string | null;
  canonical_title: string | null;
  authors: string | null;
  venue: string | null;
  publication_date: string | null;
  is_open_access: boolean | null;
  open_access_url: string | null;
  metadata_source: string | null;
  citation_count: number | null;
  citation_source: string | null;
  citation_checked_at: string | null;
  last_refreshed_at: string | null;
  last_error: string | null;
}

export interface CitationSnapshot {
  id: string;
  benchmark_id: string;
  citation_count: number;
  source: string;
  fetched_at: string;
}

export async function getPaperMetadata(benchmarkId: string) {
  const { data } = await api.get<PaperMetadata | null>(`/paper-metadata/benchmarks/${benchmarkId}`);
  return data;
}

export async function listCitationHistory(benchmarkId: string) {
  const { data } = await api.get<CitationSnapshot[]>(`/paper-metadata/benchmarks/${benchmarkId}/citation-history`);
  return data;
}

export interface GithubRateLimit {
  limit: number;
  remaining: number;
  reset_at: string;
  authenticated: boolean;
}

export async function getGithubRateLimit() {
  const { data } = await api.get("/repo-stats/github-rate-limit");
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

export interface CatalogueSummary {
  total_benchmarks: number;
  popular: number;
  high: number;
  medium: number;
  average_metrics_per_benchmark: number;
  average_citations: number;
  code_and_data_coverage_percent: number;
}

export interface CategoryCount {
  label: string;
  count: number;
  share_percent: number;
}

export interface PublicationYear {
  year: number;
  count: number;
  year_over_year_percent: number | null;
}

export interface CitationLeader {
  benchmark_id: string;
  benchmark_name: string;
  citations: number;
  complexity_level: string;
}

export interface RepositoryHealth {
  status: string;
  github: number;
  hugging_face: number;
}

export interface CatalogueReportsData {
  total_benchmarks: number;
  undated_benchmarks: number;
  publication_trend: PublicationYear[];
  complexity_distribution: CategoryCount[];
  task_types: CategoryCount[];
  evaluation_metrics: CategoryCount[];
  citation_leaders: CitationLeader[];
  repository_health: RepositoryHealth[];
  github_star_distribution: CategoryCount[];
  language_coverage: CategoryCount[];
  modality_coverage: CategoryCount[];
  license_distribution: CategoryCount[];
  creation_methodology: CategoryCount[];
  development_purpose: CategoryCount[];
  use_case_distribution: CategoryCount[];
  research_gaps: HeatmapDimension[];
}

export async function getCatalogueSummary() {
  const { data } = await api.get<CatalogueSummary>("/stats/catalogue-summary");
  return data;
}

export async function getCatalogueReports() {
  const { data } = await api.get<CatalogueReportsData>("/stats/catalogue-reports");
  return data;
}

export async function getResearchGapHeatmap() {
  const { data } = await api.get("/stats/research-gap-heatmap");
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

function normalizeSubmission(raw: any): Submission {
  return {
    ...raw,
    quality_score: raw.quality_score !== null && raw.quality_score !== undefined
      ? Number(raw.quality_score)
      : null,
  };
}

export async function createSubmission(source_value: string) {
  const { data } = await api.post("/submissions", { source_value });
  return normalizeSubmission(data);
}

export async function listMySubmissions() {
  const { data } = await api.get("/submissions/mine");
  return data.map(normalizeSubmission);
}

export async function listAllSubmissions(statusFilter?: string) {
  const params = statusFilter ? { status: statusFilter } : {};
  const { data } = await api.get("/submissions", { params });
  return data.map(normalizeSubmission);
}

export async function getSubmission(id: string) {
  const { data } = await api.get(`/submissions/${id}`);
  return normalizeSubmission(data);
}

export async function reviewSubmission(
  id: string,
  decision: "approve" | "reject" | "needs_better_extraction",
  reviewer_notes?: string,
) {
  const { data } = await api.post(`/submissions/${id}/review`, {
    decision,
    reviewer_notes,
  });
  return normalizeSubmission(data);
}

export async function reextractSubmission(id: string, model_used: string) {
  const { data } = await api.post(`/submissions/${id}/reextract`, { model_used });
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

export interface NotificationPage {
  items: AppNotification[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export async function listNotifications(unreadOnly = false, limit = 50) {
  const { data } = await api.get("/notifications", {
    params: { ...(unreadOnly ? { unread_only: true } : {}), limit },
  });
  return data;
}

export async function listNotificationPage(page = 1, pageSize = 20, unreadOnly = false) {
  const { data } = await api.get<NotificationPage>("/notifications/page", {
    params: { page, page_size: pageSize, ...(unreadOnly ? { unread_only: true } : {}) },
  });
  return data;
}

export async function getUnreadNotificationCount() {
  const { data } = await api.get<{ unread_count: number }>("/notifications/unread-count");
  return data.unread_count;
}

export async function markNotificationRead(id: string) {
  const { data } = await api.post(`/notifications/${id}/read`);
  return data;
}

export async function markAllNotificationsRead() {
  const { data } = await api.post<{ marked_read: number }>("/notifications/read-all");
  return data;
}

// ---- Phase 6: admin user management ----

export async function listUsers(params?: { search?: string; role?: string }) {
  const { data } = await api.get("/users", { params });
  return data;
}

export async function setTrustedSubmitter(userId: string, trusted: boolean) {
  const { data } = await api.post(`/users/${userId}/trust`, null, {
    params: { trusted },
  });
  return data;
}

// ---- Admin model catalogue ----

export interface ModelOption {
  id: string;
  identifier: string;
  provider: string;
  display_name: string | null;
  is_active: boolean;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface ModelOptionInput {
  identifier: string;
  provider: string;
  display_name?: string | null;
  is_active?: boolean;
  notes?: string | null;
}

export async function listModels(activeOnly = true) {
  const { data } = await api.get("/models", { params: { active_only: activeOnly } });
  return data as ModelOption[];
}

export async function createModel(payload: ModelOptionInput) {
  const { data } = await api.post("/models", payload);
  return data as ModelOption;
}

export async function updateModel(id: string, payload: Partial<ModelOptionInput>) {
  const { data } = await api.patch(`/models/${id}`, payload);
  return data as ModelOption;
}

export async function deleteModel(id: string) {
  await api.delete(`/models/${id}`);
}

// ---- NEW (2026-09-01): admin vocabulary catalogue (task types + eval metrics) ----
// Backs backend/app/routers/vocab_terms.py and frontend/app/admin/vocab/page.tsx.

export interface VocabTerm {
  id: string;
  category: "task_type" | "evaluation_metric";
  term: string;
  normalized_term: string;
  is_active: boolean;
  is_canonical: boolean;
  canonical_term_id: string | null;
  usage_count: number;
  source: "agent" | "admin";
  first_seen_benchmark_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface VocabTermInput {
  category: "task_type" | "evaluation_metric";
  term: string;
  is_active?: boolean;
  is_canonical?: boolean;
  canonical_term_id?: string | null;
}

export async function listVocabTerms(params?: {
  category?: "task_type" | "evaluation_metric";
  active_only?: boolean;
  canonical_only?: boolean;
  unreviewed_only?: boolean;
}) {
  const { data } = await api.get("/vocab-terms", { params });
  return data as VocabTerm[];
}

export async function createVocabTerm(payload: VocabTermInput) {
  const { data } = await api.post("/vocab-terms", payload);
  return data as VocabTerm;
}

export async function updateVocabTerm(
  id: string,
  payload: Partial<Omit<VocabTermInput, "category">>,
) {
  const { data } = await api.patch(`/vocab-terms/${id}`, payload);
  return data as VocabTerm;
}

export async function deleteVocabTerm(id: string) {
  await api.delete(`/vocab-terms/${id}`);
}
