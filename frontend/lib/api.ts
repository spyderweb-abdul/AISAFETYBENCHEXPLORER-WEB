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
  submitted_by: string | null;
  created_at: string;
  completed_at: string | null;
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
