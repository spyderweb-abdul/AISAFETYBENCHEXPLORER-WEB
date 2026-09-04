"use client";

import { Suspense, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import {
  ModelOption,
  Submission,
  listAllSubmissions,
  listModels,
  reextractSubmission,
  reviewSubmission,
} from "../../../lib/api";

const STATUS_BADGE_CLASS: Record<string, string> = {
  submitted: "status-tag",
  extracting: "status-tag status-tag--info",
  pending_review: "status-tag status-tag--warning",
  approved: "status-tag status-tag--success",
  rejected: "status-tag status-tag--danger",
  failed: "status-tag status-tag--danger",
  needs_better_extraction: "status-tag status-tag--warning",
};

function StatusBadge({ status }: { status: string }) {
  return <span className={STATUS_BADGE_CLASS[status] ?? "status-tag"}>{status.replaceAll("_", " ")}</span>;
}

function DomainCheckBadge({ passed }: { passed: boolean | null }) {
  if (passed === true) return <span className="status-tag status-tag--success">Domain OK</span>;
  if (passed === false) return <span className="status-tag status-tag--danger">Domain mismatch</span>;
  return <span className="status-tag status-tag--warning">Borderline</span>;
}

function AdminSubmissionsPageInner() {
  const searchParams = useSearchParams();
  const highlightId = searchParams.get("highlight");

  const [submissions, setSubmissions] = useState<Submission[]>([]);
  const [statusFilter, setStatusFilter] = useState("pending_review");
  const [loading, setLoading] = useState(true);
  const [notesById, setNotesById] = useState<Record<string, string>>({});
  const [reextractModelById, setReextractModelById] = useState<Record<string, string>>({});
  const [busyId, setBusyId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [highlightedId, setHighlightedId] = useState<string | null>(null);
  const [models, setModels] = useState<ModelOption[]>([]);
  const [modelsError, setModelsError] = useState<string | null>(null);
  const rowRefs = useRef<Record<string, HTMLElement | null>>({});

  useEffect(() => {
    if (highlightId) setStatusFilter("");
  }, [highlightId]);

  async function load() {
    setLoading(true);
    try {
      setSubmissions(await listAllSubmissions(statusFilter || undefined));
    } catch {
      setError("Failed to load submissions.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, [statusFilter]);

  useEffect(() => {
    listModels(true)
      .then(setModels)
      .catch(() => setModelsError("Failed to load models. Add a model at /admin/models, or check that the models API is reachable."));
  }, []);

  useEffect(() => {
    if (!highlightId || loading || !submissions.some((submission) => submission.id === highlightId)) return;

    setHighlightedId(highlightId);
    rowRefs.current[highlightId]?.scrollIntoView({ behavior: "smooth", block: "center" });
    const timer = setTimeout(() => setHighlightedId(null), 4000);
    return () => clearTimeout(timer);
  }, [highlightId, loading, submissions]);

  async function handleReview(id: string, decision: "approve" | "reject" | "needs_better_extraction") {
    const notes = notesById[id] || "";
    if (decision !== "approve" && !notes.trim()) {
      setError("Reviewer notes are required when declining or requesting a better extraction.");
      return;
    }
    setBusyId(id);
    setError(null);
    try {
      await reviewSubmission(id, decision, notes || undefined);
      load();
    } catch (err: any) {
      setError(err?.response?.data?.detail || "Review action failed.");
    } finally {
      setBusyId(null);
    }
  }

  async function handleReextract(id: string) {
    const model = reextractModelById[id] || models[0]?.identifier;
    if (!model) {
      setError("No active model is available. Add one at /admin/models before re-extracting.");
      return;
    }
    setBusyId(id);
    setError(null);
    try {
      await reextractSubmission(id, model);
      load();
    } catch (err: any) {
      setError(err?.response?.data?.detail || "Re-extraction request failed.");
    } finally {
      setBusyId(null);
    }
  }

  return (
    <main className="admin-page">
      <header className="page-header">
        <div>
          <p className="eyebrow">Community governance</p>
          <h1>Community submissions</h1>
          <p className="page-description">Review researcher-submitted benchmark papers and direct re-extraction when needed.</p>
        </div>
        <Link href="/admin/models" className="button secondary">Manage models</Link>
      </header>

      <section className="card" aria-label="Submission filters">
        <div className="admin-toolbar">
          <label htmlFor="submission-status-filter" className="sr-only">Filter submissions by status</label>
          <select id="submission-status-filter" value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}>
            <option value="">All statuses</option>
            <option value="pending_review">Pending review</option>
            <option value="needs_better_extraction">Needs better extraction</option>
            <option value="approved">Approved</option>
            <option value="rejected">Rejected</option>
            <option value="failed">Failed</option>
          </select>
          <button className="secondary" type="button" onClick={load}>Refresh</button>
        </div>
      </section>

      {error && <p className="error">{error}</p>}
      {modelsError && <p className="error">{modelsError}</p>}

      {loading ? (
        <div className="browse-state" role="status">Loading submissions.</div>
      ) : submissions.length === 0 ? (
        <div className="card"><p className="muted-copy">No submissions match this filter.</p></div>
      ) : (
        <section className="submission-list" aria-label="Community submissions">
          {submissions.map((submission) => (
            <article
              key={submission.id}
              ref={(element) => { rowRefs.current[submission.id] = element; }}
              className={highlightedId === submission.id ? "card submission-card submission-highlighted" : "card submission-card"}
            >
              <header className="submission-card-header">
                <div>
                  <h2 className="submission-source">{submission.source_value}</h2>
                  <div className="submission-badges">
                    <StatusBadge status={submission.status} />
                    {submission.domain_check_reason && <DomainCheckBadge passed={submission.domain_check_passed} />}
                  </div>
                </div>
                {submission.result_benchmark_id && <Link href={`/admin/benchmarks/${submission.result_benchmark_id}`} className="button secondary">View benchmark</Link>}
              </header>

              <p className="submission-meta">
                Model: {submission.model_used} · Quality score: {submission.quality_score != null ? submission.quality_score.toFixed(2) : "Not available"} · Submitted: {new Date(submission.created_at).toLocaleString()}
              </p>

              {submission.domain_check_reason && <p className="submission-domain-note">{submission.domain_check_reason}</p>}
              {submission.admin_review_notes && <p className="submission-review-note"><strong>Previous reviewer notes:</strong> {submission.admin_review_notes}</p>}

              {submission.status === "pending_review" && (
                <div className="submission-review-actions">
                  <textarea
                    aria-label={`Reviewer notes for ${submission.source_value}`}
                    placeholder="Reviewer notes: required for decline or a better extraction request"
                    value={notesById[submission.id] || ""}
                    onChange={(event) => setNotesById((current) => ({ ...current, [submission.id]: event.target.value }))}
                    rows={2}
                  />
                  <div className="submission-action-buttons">
                    <button type="button" onClick={() => handleReview(submission.id, "approve")} disabled={busyId === submission.id}>Approve</button>
                    <button type="button" className="danger" onClick={() => handleReview(submission.id, "reject")} disabled={busyId === submission.id}>Decline</button>
                    <button type="button" className="secondary" onClick={() => handleReview(submission.id, "needs_better_extraction")} disabled={busyId === submission.id}>Request better extraction</button>
                  </div>
                </div>
              )}

              {submission.status === "needs_better_extraction" && (
                <div className="submission-reextract-actions">
                  <select
                    aria-label={`Model for re-extracting ${submission.source_value}`}
                    value={reextractModelById[submission.id] || models[0]?.identifier || ""}
                    onChange={(event) => setReextractModelById((current) => ({ ...current, [submission.id]: event.target.value }))}
                    disabled={models.length === 0}
                  >
                    {models.length === 0 && <option value="">No active models</option>}
                    {models.map((model) => <option key={model.id} value={model.identifier}>{model.display_name ? `${model.display_name} (${model.identifier})` : model.identifier}</option>)}
                  </select>
                  <button type="button" onClick={() => handleReextract(submission.id)} disabled={busyId === submission.id || models.length === 0}>Run re-extraction</button>
                </div>
              )}
            </article>
          ))}
        </section>
      )}
    </main>
  );
}

export default function AdminSubmissionsPage() {
  return <Suspense fallback={<main className="admin-page"><div className="browse-state" role="status">Loading submissions.</div></main>}><AdminSubmissionsPageInner /></Suspense>;
}
