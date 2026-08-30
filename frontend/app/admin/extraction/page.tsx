// Destination path: frontend/app/admin/extraction/page.tsx
// Replaces the existing file in full.
//
// CHANGE (2026-08-28): the model dropdown now fetches from GET /models
// (see backend/app/routers/models.py) instead of importing the static
// lib/modelOptions.ts array. Models are managed at /admin/models.
// lib/modelOptions.ts can now be deleted -- nothing imports it once
// this file and admin/submissions/page.tsx are both updated.

"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import {
  ExtractionJob,
  JobVariance,
  ModelOption,
  getJobVariance,
  listExtractionJobs,
  listModels,
  reviewExtractionJob,
  submitExtractionJob,
} from "../../../lib/api";

const STATUS_COLORS: Record<string, string> = {
  queued: "bg-gray-200 text-gray-700",
  running: "bg-blue-100 text-blue-700",
  done: "bg-green-100 text-green-700",
  failed: "bg-red-100 text-red-700",
  needs_review: "bg-yellow-100 text-yellow-800",
};

function formatCost(cost: number | string | null | undefined): string {
  if (cost === null || cost === undefined) return "unpriced";
  const n = Number(cost);
  if (Number.isNaN(n)) return "unpriced";
  return `$${n.toFixed(4)}`;
}

function formatTokens(input: number | null, output: number | null): string {
  if (input === null && output === null) return "N/A";
  return `${input ?? "?"} in / ${output ?? "?"} out`;
}

function sumCosts(jobs: ExtractionJob[]): number {
  return jobs.reduce((sum, j) => {
    const n = Number(j.estimated_cost_usd);
    return sum + (Number.isNaN(n) ? 0 : n);
  }, 0);
}

export default function ExtractionPage() {
  const [jobs, setJobs] = useState<ExtractionJob[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [filterStatus, setFilterStatus] = useState<string>("");

  const [models, setModels] = useState<ModelOption[]>([]);
  const [modelsLoading, setModelsLoading] = useState(true);
  const [modelsError, setModelsError] = useState<string | null>(null);

  const [sourceType, setSourceType] = useState("doi");
  const [sourceValue, setSourceValue] = useState("");
  const [modelUsed, setModelUsed] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  const [reviewNote, setReviewNote] = useState<Record<string, string>>({});
  const [reviewingId, setReviewingId] = useState<string | null>(null);

  const [variance, setVariance] = useState<JobVariance | null>(null);
  const [varianceLoading, setVarianceLoading] = useState(false);
  const [varianceError, setVarianceError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await listExtractionJobs(filterStatus || undefined);
      setJobs(data);
    } catch {
      setError("Failed to load jobs.");
    } finally {
      setLoading(false);
    }
  }, [filterStatus]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    (async () => {
      setModelsLoading(true);
      setModelsError(null);
      try {
        const data = await listModels(true);
        setModels(data);
        if (data.length > 0) setModelUsed((prev) => prev || data[0].identifier);
      } catch {
        setModelsError(
          "Failed to load models -- add models at /admin/models, or check that the models API is reachable.",
        );
      } finally {
        setModelsLoading(false);
      }
    })();
  }, []);

  async function handleCheckVariance() {
    if (!sourceValue) return;
    setVarianceLoading(true);
    setVarianceError(null);
    try {
      const data = await getJobVariance(sourceValue);
      setVariance(data);
    } catch {
      setVarianceError("Could not load prior-run stats for this source value.");
      setVariance(null);
    } finally {
      setVarianceLoading(false);
    }
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!modelUsed) {
      setSubmitError("No model selected -- add at least one active model at /admin/models.");
      return;
    }
    setSubmitting(true);
    setSubmitError(null);
    try {
      await submitExtractionJob({
        source_type: sourceType,
        source_value: sourceValue,
        model_used: modelUsed,
      });
      setSourceValue("");
      setVariance(null);
      await load();
    } catch (err: unknown) {
      const msg =
        err &&
        typeof err === "object" &&
        "response" in err &&
        err.response &&
        typeof err.response === "object" &&
        "data" in err.response
          ? JSON.stringify((err.response as { data: unknown }).data)
          : "Submission failed.";
      setSubmitError(msg);
    } finally {
      setSubmitting(false);
    }
  }

  async function handleReview(jobId: string, approve: boolean) {
    setReviewingId(jobId);
    try {
      await reviewExtractionJob(jobId, approve, reviewNote[jobId]);
      await load();
    } catch {
      setError("Review action failed.");
    } finally {
      setReviewingId(null);
    }
  }

  const pendingJobs = jobs.filter((j) => j.result_benchmark_status === "pending_review");
  const otherJobs = jobs.filter((j) => j.result_benchmark_status !== "pending_review");

  return (
    <div className="p-6 max-w-5xl mx-auto">
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-2xl font-bold">Agent Extraction Panel</h1>
        <Link href="/admin/models" className="text-sm text-indigo-600 hover:underline">
          Manage models &rarr;
        </Link>
      </div>

      <section className="bg-white rounded-lg border p-5 mb-8 shadow-sm">
        <h2 className="text-lg font-semibold mb-4">Submit New Extraction Job</h2>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="flex gap-4 flex-wrap">
            <div className="flex flex-col gap-1">
              <label className="text-sm font-medium">Source Type</label>
              <select
                value={sourceType}
                onChange={(e) => setSourceType(e.target.value)}
                className="border rounded px-3 py-2 text-sm"
              >
                <option value="doi">DOI</option>
                <option value="arxiv_id">arXiv ID</option>
                <option value="pdf_url">PDF URL</option>
              </select>
            </div>

            <div className="flex flex-col gap-1 flex-1 min-w-48">
              <label className="text-sm font-medium">Source Value</label>
              <input
                type="text"
                value={sourceValue}
                onChange={(e) => {
                  setSourceValue(e.target.value);
                  setVariance(null);
                }}
                placeholder={sourceType === "doi" ? "10.1145/3442188.3445922" : sourceType === "arxiv_id" ? "2306.13213" : "https://..."}
                required
                className="border rounded px-3 py-2 text-sm"
              />
            </div>

            <div className="flex flex-col gap-1">
              <label className="text-sm font-medium">Model</label>
              <select
                value={modelUsed}
                onChange={(e) => setModelUsed(e.target.value)}
                disabled={modelsLoading || models.length === 0}
                className="border rounded px-3 py-2 text-sm"
              >
                {models.length === 0 && <option value="">No active models</option>}
                {models.map((m) => (
                  <option key={m.id} value={m.identifier}>
                    {m.display_name ? `${m.display_name} (${m.identifier})` : m.identifier}
                  </option>
                ))}
              </select>
              {modelsError && <span className="text-xs text-red-600">{modelsError}</span>}
            </div>
          </div>

          <div className="flex items-center gap-3 flex-wrap">
            <button
              type="button"
              onClick={handleCheckVariance}
              disabled={!sourceValue || varianceLoading}
              className="bg-gray-100 px-3 py-1.5 rounded text-xs font-medium hover:bg-gray-200 disabled:opacity-50"
            >
              {varianceLoading ? "Checking..." : "Check Prior Runs & Cost"}
            </button>
            {varianceError && <span className="text-xs text-red-600">{varianceError}</span>}
            {variance && (
              <span className="text-xs text-gray-700 bg-gray-50 border rounded px-3 py-1.5">
                {variance.run_count === 0 ? (
                  "No prior runs for this source value -- this will be run #1."
                ) : (
                  <>
                    {variance.run_count} prior run{variance.run_count === 1 ? "" : "s"} | mean quality{" "}
                    {variance.mean_quality_score !== null ? (Number(variance.mean_quality_score) * 100).toFixed(0) + "%" : "N/A"}
                    {" "}(&plusmn;{variance.stddev_quality_score !== null ? (Number(variance.stddev_quality_score) * 100).toFixed(1) + "%" : "N/A"})
                    {" "}| total spent so far {formatCost(variance.total_estimated_cost_usd)}
                  </>
                )}
              </span>
            )}
          </div>

          {submitError && (
            <p className="text-red-600 text-sm">{submitError}</p>
          )}

          <button
            type="submit"
            disabled={submitting || !modelUsed}
            className="bg-indigo-600 text-white px-5 py-2 rounded text-sm font-medium hover:bg-indigo-700 disabled:opacity-50"
          >
            {submitting ? "Submitting..." : "Submit Job"}
          </button>
        </form>
      </section>

      {pendingJobs.length > 0 && (
        <section className="bg-yellow-50 border border-yellow-200 rounded-lg p-5 mb-8 shadow-sm">
          <h2 className="text-lg font-semibold mb-4 text-yellow-900">Pending Review ({pendingJobs.length})</h2>
          <div className="space-y-4">
            {pendingJobs.map((job) => (
              <div key={job.id} className="bg-white rounded border p-4">
                <div className="flex justify-between items-start flex-wrap gap-2">
                  <div>
                    <p className="text-sm font-medium">{job.source_type}: {job.source_value}</p>
                    <p className="text-xs text-gray-500 mt-1">
                      Model: {job.model_used} | Quality: {job.quality_score !== null ? (Number(job.quality_score) * 100).toFixed(0) + "%" : "N/A"}
                      {" "}| {job.requires_review ? (
                        <span className="text-yellow-700 font-medium">Flagged for review (below 75% quality)</span>
                      ) : (
                        <span className="text-green-700">High quality -- review is a formality, not a correction</span>
                      )}
                    </p>
                    {job.result_benchmark_id && (
                      <p className="text-xs mt-1">
                        <Link href={`/admin/benchmarks/${job.result_benchmark_id}`} className="text-indigo-600 hover:underline">
                          Inspect full benchmark fields before deciding &rarr;
                        </Link>
                      </p>
                    )}
                  </div>
                  <span className={`text-xs px-2 py-1 rounded font-medium ${STATUS_COLORS[job.status] ?? "bg-gray-100"}`}>
                    job: {job.status}
                  </span>
                </div>
                <div className="mt-3 flex gap-2 flex-wrap items-center">
                  <input
                    type="text"
                    placeholder="Reviewer note (optional)"
                    value={reviewNote[job.id] || ""}
                    onChange={(e) => setReviewNote((prev) => ({ ...prev, [job.id]: e.target.value }))}
                    className="border rounded px-3 py-1.5 text-xs flex-1 min-w-40"
                  />
                  <button
                    onClick={() => handleReview(job.id, true)}
                    disabled={reviewingId === job.id}
                    className="bg-green-600 text-white px-4 py-1.5 rounded text-xs font-medium hover:bg-green-700 disabled:opacity-50"
                  >
                    Approve
                  </button>
                  <button
                    onClick={() => handleReview(job.id, false)}
                    disabled={reviewingId === job.id}
                    className="bg-red-600 text-white px-4 py-1.5 rounded text-xs font-medium hover:bg-red-700 disabled:opacity-50"
                  >
                    Reject
                  </button>
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      <section className="bg-white rounded-lg border p-5 shadow-sm">
        <div className="flex justify-between items-center mb-4 flex-wrap gap-2">
          <h2 className="text-lg font-semibold">All Jobs</h2>
          <div className="flex gap-2 items-center">
            <select
              value={filterStatus}
              onChange={(e) => setFilterStatus(e.target.value)}
              className="border rounded px-3 py-1.5 text-sm"
            >
              <option value="">All statuses</option>
              <option value="queued">queued</option>
              <option value="running">running</option>
              <option value="done">done</option>
              <option value="needs_review">needs_review</option>
              <option value="failed">failed</option>
            </select>
            <button
              onClick={load}
              className="bg-gray-100 px-3 py-1.5 rounded text-sm hover:bg-gray-200"
            >
              Refresh
            </button>
          </div>
        </div>

        {loading && <p className="text-sm text-gray-500">Loading...</p>}
        {error && <p className="text-sm text-red-600">{error}</p>}

        {!loading && jobs.length === 0 && (
          <p className="text-sm text-gray-500">No jobs found.</p>
        )}

        {!loading && jobs.length > 0 && (
          <p className="text-xs text-gray-500 mb-2">
            Total estimated spend across listed jobs: {formatCost(sumCosts(jobs))}
          </p>
        )}

        <div className="divide-y">
          {otherJobs.map((job) => (
            <div key={job.id} className="py-3 flex justify-between items-start flex-wrap gap-2">
              <div>
                <p className="text-sm font-medium">{job.source_type}: {job.source_value}</p>
                <p className="text-xs text-gray-500 mt-0.5">
                  Model: {job.model_used ?? "N/A"} | Quality: {job.quality_score !== null ? (Number(job.quality_score) * 100).toFixed(0) + "%" : "N/A"} | Submitted: {new Date(job.created_at).toLocaleString()}
                </p>
                <p className="text-xs text-gray-400">
                  Tokens: {formatTokens(job.input_tokens, job.output_tokens)} | Est. cost: {formatCost(job.estimated_cost_usd)}
                </p>
                {job.result_benchmark_id && (
                  <p className="text-xs text-gray-400">
                    Benchmark:{" "}
                    <Link href={`/admin/benchmarks/${job.result_benchmark_id}`} className="text-indigo-600 hover:underline">
                      {job.result_benchmark_id}
                    </Link>
                    {job.result_benchmark_status ? ` (${job.result_benchmark_status})` : ""}
                  </p>
                )}
              </div>
              <span className={`text-xs px-2 py-1 rounded font-medium ${STATUS_COLORS[job.status] ?? "bg-gray-100"}`}>
                {job.status}
              </span>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
