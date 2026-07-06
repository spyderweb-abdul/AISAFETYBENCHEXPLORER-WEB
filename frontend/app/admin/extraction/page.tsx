"use client";

import { useCallback, useEffect, useState } from "react";
import {
  ExtractionJob,
  listExtractionJobs,
  reviewExtractionJob,
  submitExtractionJob,
} from "../../../lib/api";

const MODEL_OPTIONS = [
  "openai/gpt-4o",
  "openai/gpt-4o-mini",
  "anthropic/claude-sonnet-5",
  "anthropic/claude-3-5-sonnet-20241022",
  "anthropic/claude-haiku-4-5-20251001",
];

const STATUS_COLORS: Record<string, string> = {
  queued: "bg-gray-200 text-gray-700",
  running: "bg-blue-100 text-blue-700",
  done: "bg-green-100 text-green-700",
  failed: "bg-red-100 text-red-700",
  needs_review: "bg-yellow-100 text-yellow-800",
};

export default function ExtractionPage() {
  const [jobs, setJobs] = useState<ExtractionJob[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [filterStatus, setFilterStatus] = useState<string>("");

  const [sourceType, setSourceType] = useState("doi");
  const [sourceValue, setSourceValue] = useState("");
  const [modelUsed, setModelUsed] = useState(MODEL_OPTIONS[0]);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  const [reviewNote, setReviewNote] = useState<Record<string, string>>({});
  const [reviewingId, setReviewingId] = useState<string | null>(null);

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

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setSubmitError(null);
    try {
      await submitExtractionJob({
        source_type: sourceType,
        source_value: sourceValue,
        model_used: modelUsed,
      });
      setSourceValue("");
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

  const pendingJobs = jobs.filter((j) => j.status === "needs_review");
  const otherJobs = jobs.filter((j) => j.status !== "needs_review");

  return (
    <div className="p-6 max-w-5xl mx-auto">
      <h1 className="text-2xl font-bold mb-6">Agent Extraction Panel</h1>

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
                onChange={(e) => setSourceValue(e.target.value)}
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
                className="border rounded px-3 py-2 text-sm"
              >
                {MODEL_OPTIONS.map((m) => (
                  <option key={m} value={m}>{m}</option>
                ))}
              </select>
            </div>
          </div>

          {submitError && (
            <p className="text-red-600 text-sm">{submitError}</p>
          )}

          <button
            type="submit"
            disabled={submitting}
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
                    <p className="text-xs text-gray-500 mt-1">Model: {job.model_used} | Quality: {job.quality_score !== null ? (Number(job.quality_score) * 100).toFixed(0) + "%" : "N/A"}</p>
                    {job.result_benchmark_id && (
                      <p className="text-xs text-gray-500">Benchmark ID: {job.result_benchmark_id}</p>
                    )}
                  </div>
                  <span className={`text-xs px-2 py-1 rounded font-medium ${STATUS_COLORS[job.status] ?? "bg-gray-100"}`}>
                    {job.status}
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

        <div className="divide-y">
          {otherJobs.map((job) => (
            <div key={job.id} className="py-3 flex justify-between items-start flex-wrap gap-2">
              <div>
                <p className="text-sm font-medium">{job.source_type}: {job.source_value}</p>
                <p className="text-xs text-gray-500 mt-0.5">
                  Model: {job.model_used ?? "N/A"} | Quality: {job.quality_score !== null ? (Number(job.quality_score) * 100).toFixed(0) + "%" : "N/A"} | Submitted: {new Date(job.created_at).toLocaleString()}
                </p>
                {job.result_benchmark_id && (
                  <p className="text-xs text-gray-400">Benchmark: {job.result_benchmark_id}</p>
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
