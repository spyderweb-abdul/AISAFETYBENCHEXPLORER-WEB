// Destination path: frontend/app/admin/extraction/page.tsx
// Replaces the existing file in full.
//
// CHANGE (2026-08-28): the model dropdown now fetches from GET /models
// (see backend/app/routers/models.py) instead of importing the static
// lib/modelOptions.ts array. Models are managed at /admin/models.
// lib/modelOptions.ts can now be deleted -- nothing imports it once
// this file and admin/submissions/page.tsx are both updated.

"use client";

import { Fragment, useCallback, useEffect, useState } from "react";
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

const STATUS_CLASS: Record<string, string> = {
  queued: "extraction-status extraction-status--queued",
  running: "extraction-status extraction-status--running",
  done: "extraction-status extraction-status--done",
  failed: "extraction-status extraction-status--failed",
  needs_review: "extraction-status extraction-status--needs_review",
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

  const PAGE_SIZE = 15;

  const [historyPage, setHistoryPage] = useState(1);
  const [expandedJobId, setExpandedJobId] = useState<string | null>(null);
  const [showSubmissionForm, setShowSubmissionForm] = useState(true);

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
    setHistoryPage(1);
  }, [filterStatus]);

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
  const historyPageCount = Math.max(1, Math.ceil(otherJobs.length / PAGE_SIZE),);
  
  const safeHistoryPage = Math.min(historyPage, historyPageCount);  
  const paginatedJobs = otherJobs.slice((safeHistoryPage - 1) * PAGE_SIZE, safeHistoryPage * PAGE_SIZE,);

  return (
    <div className="extraction-page">
      <header className="page-header">
        <div>
          <p className="eyebrow">Agent operations</p>
          <h1>Agent extraction</h1>
          <p className="page-description">Create, review, and cost-check benchmark extraction jobs.</p>
        </div>
        <Link href="/admin/models" className="button secondary">Manage models</Link>
      </header>

      <section className="card">
        <div className="extraction-section-header">
          <div>
            <h2>Submit New Extraction Job</h2>
            <p>Create a DOI, arXiv ID, or PDF URL extraction request.</p>
          </div>
          <button
            className="secondary"
            onClick={() => setShowSubmissionForm((value) => !value)}
            type="button"
            aria-expanded={showSubmissionForm}
          >
            {showSubmissionForm ? "Collapse" : "New Extraction"}
          </button>
        </div>

        {showSubmissionForm && (
          <form onSubmit={handleSubmit}>
            <div className="model-create-row extraction-create-row">
              <div className="model-create-field extraction-field--type">
                <label htmlFor="source-type">Source Type</label>
                <select
                  id="source-type"
                  value={sourceType}
                  onChange={(e) => setSourceType(e.target.value)}
                >
                  <option value="doi">DOI</option>
                  <option value="arxiv_id">arXiv ID</option>
                  <option value="pdf_url">PDF URL</option>
                </select>
              </div>

              <div className="model-create-field extraction-field--source">
                <label htmlFor="source-value">Source Value</label>
                <input
                  id="source-value"
                  type="text"
                  value={sourceValue}
                  onChange={(e) => {
                    setSourceValue(e.target.value);
                    setVariance(null);
                  }}
                  placeholder={
                    sourceType === "doi"
                      ? "10.1145/3442188.3445922"
                      : sourceType === "arxiv_id"
                        ? "2306.13213"
                        : "https://..."
                  }
                  required
                />
              </div>

              <div className="model-create-field extraction-field--model">
                <label htmlFor="extraction-model">Model</label>
                <select
                  id="extraction-model"
                  value={modelUsed}
                  onChange={(e) => setModelUsed(e.target.value)}
                  disabled={modelsLoading || models.length === 0}
                >
                  {models.length === 0 && <option value="">No active models</option>}
                  {models.map((model) => (
                    <option key={model.id} value={model.identifier}>
                      {model.display_name
                        ? `${model.display_name} (${model.identifier})`
                        : model.identifier}
                    </option>
                  ))}
                </select>
              </div>

              <div className="model-create-field extraction-field--action">
                <span className="model-create-action-label">Action</span>
                <div className="extraction-submit-actions">
                  <button
                    className="secondary"
                    type="button"
                    onClick={handleCheckVariance}
                    disabled={!sourceValue || varianceLoading}
                  >
                    {varianceLoading ? "Checking..." : "Check Cost"}
                  </button>

                  <button type="submit" disabled={submitting || !modelUsed}>
                    {submitting ? "Submitting..." : "Submit"}
                  </button>
                </div>
              </div>
            </div>
            {submitError && (
              <p className="error">{submitError}</p>
            )}
          </form>
        )}
      </section>

      {pendingJobs.length > 0 && (
        <section className="card extraction-review-queue">
          <h2 className="detail-section-title">Pending review <span className="metadata-tags-empty">{pendingJobs.length}</span></h2>
          <div className="extraction-review-list">
            {pendingJobs.map((job) => (
              <article key={job.id} className="extraction-review-item">
                <div className="extraction-review-item-header">
                  <div>
                    <p className="extraction-review-source">{job.source_type}: {job.source_value}</p>
                    <p className="extraction-review-meta">
                      Model: {job.model_used} | Quality: {job.quality_score !== null ? (Number(job.quality_score) * 100).toFixed(0) + "%" : "N/A"}
                      {" "}| {job.requires_review ? (
                        <span className="extraction-review-warning">Flagged for review (below 75% quality)</span>
                      ) : (
                        <span className="extraction-review-positive">High quality: review is a formality, not a correction</span>
                      )}
                    </p>
                    {job.result_benchmark_id && (
                      <p className="extraction-review-link">
                        <Link href={`/admin/benchmarks/${job.result_benchmark_id}`}>
                          Inspect benchmark fields before deciding →
                        </Link>
                      </p>
                    )}
                  </div>
                  <span className={STATUS_CLASS[job.status] ?? "extraction-status"}>
                    job: {job.status}
                  </span>
                </div>
                <div className="extraction-review-actions">
                  <input
                    type="text"
                    placeholder="Reviewer note (optional)"
                    value={reviewNote[job.id] || ""}
                    onChange={(e) => setReviewNote((prev) => ({ ...prev, [job.id]: e.target.value }))}
                  />
                  <button
                    type="button"
                    onClick={() => handleReview(job.id, true)}
                    disabled={reviewingId === job.id}
                    className="success"
                  >
                    Approve
                  </button>
                  <button
                    type="button"
                    onClick={() => handleReview(job.id, false)}
                    disabled={reviewingId === job.id}
                    className="danger"
                  >
                    Reject
                  </button>
                </div>
              </article>
            ))}
          </div>
        </section>
      )}

      <section className="card extraction-history-card">
        <div className="extraction-section-header">
          <div>
            <h2>Extraction History</h2>
            <p>
              {otherJobs.length} job{otherJobs.length === 1 ? "" : "s"} shown.
              {" "}Estimated listed spend: {formatCost(sumCosts(otherJobs))}
            </p>
          </div>

          <div className="extraction-history-controls">
            <select
              value={filterStatus}
              onChange={(event) => setFilterStatus(event.target.value)}
              aria-label="Filter extraction jobs by status"
            >
              <option value="">All statuses</option>
              <option value="queued">Queued</option>
              <option value="running">Running</option>
              <option value="done">Done</option>
              <option value="needs_review">Needs review</option>
              <option value="failed">Failed</option>
            </select>

            <button className="secondary" onClick={load} type="button">
              Refresh
            </button>
          </div>
        </div>

        {loading && <p>Loading...</p>}
        {error && <p className="error">{error}</p>}

        {!loading && otherJobs.length === 0 && (
          <p className="empty-state">No extraction jobs match this filter.</p>
        )}

        {!loading && otherJobs.length > 0 && (
          <>
            <div className="extraction-table-scroll">
              <table className="extraction-history-table">
                <thead>
                  <tr>
                    <th>Source</th>
                    <th>Model</th>
                    <th>Status</th>
                    <th>Quality</th>
                    <th>Cost</th>
                    <th>Submitted</th>
                    <th aria-label="Details" />
                  </tr>
                </thead>

                <tbody>
                  {paginatedJobs.map((job) => {
                    const isExpanded = expandedJobId === job.id;

                    return (
                      <Fragment key={job.id}>
                        <tr>
                          <td>
                            <strong>{job.source_type}</strong>
                            <span className="extraction-source-value">
                              {job.source_value}
                            </span>
                          </td>

                          <td>{job.model_used ?? "N/A"}</td>

                          <td>
                            <span className={`extraction-status extraction-status--${job.status}`}>
                              {job.status.replaceAll("_", " ")}
                            </span>
                          </td>

                          <td>
                            {job.quality_score !== null
                              ? `${(Number(job.quality_score) * 100).toFixed(0)}%`
                              : "N/A"}
                          </td>

                          <td>{formatCost(job.estimated_cost_usd)}</td>

                          <td>{new Date(job.created_at).toLocaleString()}</td>

                          <td>
                            <button
                              className="secondary extraction-details-button"
                              onClick={() =>
                                setExpandedJobId(isExpanded ? null : job.id)
                              }
                              type="button"
                              aria-expanded={isExpanded}
                            >
                              {isExpanded ? "Hide" : "Details"}
                            </button>
                          </td>
                        </tr>
                      
                        {isExpanded && (
                          <tr className="extraction-details-row">
                            <td colSpan={7}>
                              <div className="extraction-details-grid">
                                <div>
                                  <span>Input tokens</span>
                                  <strong>{job.input_tokens ?? "N/A"}</strong>
                                </div>

                                <div>
                                  <span>Output tokens</span>
                                  <strong>{job.output_tokens ?? "N/A"}</strong>
                                </div>

                                <div>
                                  <span>Token summary</span>
                                  <strong>
                                    {formatTokens(job.input_tokens, job.output_tokens)}
                                  </strong>
                                </div>

                                <div>
                                  <span>Benchmark result</span>
                                  {job.result_benchmark_id ? (
                                    <Link href={`/admin/benchmarks/${job.result_benchmark_id}`}>
                                      View benchmark
                                    </Link>
                                  ) : (
                                    <strong>Not created</strong>
                                  )}
                                </div>

                                <div>
                                  <span>Benchmark status</span>
                                  <strong>{job.result_benchmark_status ?? "N/A"}</strong>
                                </div>

                                <div>
                                  <span>Review required</span>
                                  <strong>{job.requires_review ? "Yes" : "No"}</strong>
                                </div>
                              </div>
                            </td>
                          </tr>
                        )}
                      </Fragment>
                    );
                  })}
                </tbody>
              </table>
            </div>

            <div className="extraction-pagination">
              <span>
                Page {safeHistoryPage} of {historyPageCount}
              </span>

              <div>
                <button
                  className="secondary"
                  disabled={safeHistoryPage === 1}
                  onClick={() => setHistoryPage((page) => page - 1)}
                  type="button"
                >
                  Previous
                </button>

                <button
                  className="secondary"
                  disabled={safeHistoryPage === historyPageCount}
                  onClick={() => setHistoryPage((page) => page + 1)}
                  type="button"
                >
                  Next
                </button>
              </div>
            </div>
          </>
        )}
      </section>
    </div>
  );
}
