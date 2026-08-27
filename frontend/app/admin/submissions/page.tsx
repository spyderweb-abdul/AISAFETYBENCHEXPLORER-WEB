// Destination path: frontend/app/admin/submissions/page.tsx
// New file.
//
// Phase 6 item 4: admin review queue for community submissions,
// separate from the general extraction Pending Review queue so
// community submissions (which carry domain-check and quality-score
// context the admin-initiated flow doesn't need) are triaged in their
// own dedicated view. Each row exposes three review actions --
// Approve, Decline (reason required), and Request Better Extraction
// (reason required, then an inline paid-model picker appears once
// that decision is made and the re-extract action is triggered).

"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  Submission,
  listAllSubmissions,
  reextractSubmission,
  reviewSubmission,
} from "../../../lib/api";

const STATUS_BADGE_STYLE: Record<string, { background: string; color: string }> = {
  submitted: { background: "#e5e5e5", color: "#444" },
  extracting: { background: "#e0e7ff", color: "#3730a3" },
  pending_review: { background: "#fef3c7", color: "#92400e" },
  approved: { background: "#dcfce7", color: "#166534" },
  rejected: { background: "#fee2e2", color: "#991b1b" },
  failed: { background: "#fee2e2", color: "#991b1b" },
  needs_better_extraction: { background: "#fde68a", color: "#78350f" },
};

function StatusBadge({ status }: { status: string }) {
  const style = STATUS_BADGE_STYLE[status] || { background: "#e5e5e5", color: "#444" };
  return <span className="badge" style={style}>{status.replaceAll("_", " ")}</span>;
}

function DomainCheckBadge({ passed }: { passed: boolean | null }) {
  if (passed === true) return <span className="badge" style={{ background: "#dcfce7", color: "#166534" }}>Domain OK</span>;
  if (passed === false) return <span className="badge" style={{ background: "#fee2e2", color: "#991b1b" }}>Domain mismatch</span>;
  return <span className="badge" style={{ background: "#fef3c7", color: "#92400e" }}>Borderline</span>;
}

const PAID_MODELS = ["openai/gpt-4o", "anthropic/claude-3-5-sonnet-20241022"];

export default function AdminSubmissionsPage() {
  const [submissions, setSubmissions] = useState<Submission[]>([]);
  const [statusFilter, setStatusFilter] = useState("pending_review");
  const [loading, setLoading] = useState(true);
  const [notesById, setNotesById] = useState<Record<string, string>>({});
  const [reextractModelById, setReextractModelById] = useState<Record<string, string>>({});
  const [busyId, setBusyId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    setLoading(true);
    try {
      const data = await listAllSubmissions(statusFilter || undefined);
      setSubmissions(data);
    } catch {
      setError("Failed to load submissions.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, [statusFilter]);

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
    const model = reextractModelById[id] || PAID_MODELS[0];
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
    <div className="container">
      <div className="topbar">
        <h2>Community Submissions</h2>
      </div>

      <div className="card" style={{ display: "flex", gap: 12 }}>
        <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
          <option value="">All statuses</option>
          <option value="pending_review">Pending review</option>
          <option value="needs_better_extraction">Needs better extraction</option>
          <option value="approved">Approved</option>
          <option value="rejected">Rejected</option>
          <option value="failed">Failed</option>
        </select>
      </div>

      {error && <p className="error">{error}</p>}

      {loading ? (
        <p>Loading...</p>
      ) : submissions.length === 0 ? (
        <p style={{ color: "#666" }}>No submissions match this filter.</p>
      ) : (
        submissions.map((s) => (
          <div key={s.id} className="card">
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <div>
                <strong>{s.source_value}</strong>{" "}
                <StatusBadge status={s.status} />{" "}
                {s.domain_check_reason && <DomainCheckBadge passed={s.domain_check_passed} />}
              </div>
              {s.result_benchmark_id && (
                <Link href={`/admin/benchmarks/${s.result_benchmark_id}`}>View extracted benchmark &rarr;</Link>
              )}
            </div>

            <p style={{ fontSize: 13, color: "#666" }}>
              Model: {s.model_used} | Quality score: {s.quality_score != null ? s.quality_score.toFixed(2) : "-"} |
              Submitted: {new Date(s.created_at).toLocaleString()}
            </p>

            {s.domain_check_reason && (
              <p style={{ fontSize: 13, color: "#444", background: "#f9fafb", padding: 8, borderRadius: 6 }}>
                {s.domain_check_reason}
              </p>
            )}

            {s.admin_review_notes && (
              <p style={{ fontSize: 13, color: "#444" }}>
                <strong>Previous reviewer notes:</strong> {s.admin_review_notes}
              </p>
            )}

            {s.status === "pending_review" && (
              <div style={{ display: "flex", gap: 8, alignItems: "flex-start", flexWrap: "wrap", marginTop: 8 }}>
                <textarea
                  placeholder="Reviewer notes (required for decline / request better extraction, optional for approve)"
                  value={notesById[s.id] || ""}
                  onChange={(e) => setNotesById((prev) => ({ ...prev, [s.id]: e.target.value }))}
                  rows={2}
                  style={{ flex: 1, minWidth: 260 }}
                />
                <div style={{ display: "flex", gap: 8, flexDirection: "column" }}>
                  <button onClick={() => handleReview(s.id, "approve")} disabled={busyId === s.id}>Approve</button>
                  <button className="danger" onClick={() => handleReview(s.id, "reject")} disabled={busyId === s.id}>Decline</button>
                  <button className="secondary" onClick={() => handleReview(s.id, "needs_better_extraction")} disabled={busyId === s.id}>
                    Needs Better Extraction
                  </button>
                </div>
              </div>
            )}

            {s.status === "needs_better_extraction" && (
              <div style={{ display: "flex", gap: 8, alignItems: "center", marginTop: 8 }}>
                <select
                  value={reextractModelById[s.id] || PAID_MODELS[0]}
                  onChange={(e) => setReextractModelById((prev) => ({ ...prev, [s.id]: e.target.value }))}
                >
                  {PAID_MODELS.map((m) => <option key={m} value={m}>{m}</option>)}
                </select>
                <button onClick={() => handleReextract(s.id)} disabled={busyId === s.id}>
                  Run Re-extraction (Paid Model)
                </button>
              </div>
            )}
          </div>
        ))
      )}
    </div>
  );
}
