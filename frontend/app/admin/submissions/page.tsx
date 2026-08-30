// Destination path: frontend/app/admin/submissions/page.tsx
// Replaces the existing file in full.
//
// CHANGE (2026-08-28): the re-extract model dropdown now fetches from
// GET /models (see backend/app/routers/models.py) instead of the
// hardcoded PAID_MODELS array. Models are managed at /admin/models.

"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  ModelOption,
  Submission,
  listAllSubmissions,
  listModels,
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

export default function AdminSubmissionsPage() {
  const [submissions, setSubmissions] = useState<Submission[]>([]);
  const [statusFilter, setStatusFilter] = useState("pending_review");
  const [loading, setLoading] = useState(true);
  const [notesById, setNotesById] = useState<Record<string, string>>({});
  const [reextractModelById, setReextractModelById] = useState<Record<string, string>>({});
  const [busyId, setBusyId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [models, setModels] = useState<ModelOption[]>([]);
  const [modelsError, setModelsError] = useState<string | null>(null);

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

  useEffect(() => {
    (async () => {
      try {
        const data = await listModels(true);
        setModels(data);
      } catch {
        setModelsError(
          "Failed to load models -- add models at /admin/models, or check that the models API is reachable.",
        );
      }
    })();
  }, []);

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
      setError("No active model available -- add one at /admin/models before re-extracting.");
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
    <div className="container">
      <div className="topbar" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <h2>Community Submissions</h2>
        <Link href="/admin/models" style={{ fontSize: 13 }}>Manage models &rarr;</Link>
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
      {modelsError && <p className="error">{modelsError}</p>}

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
                  value={reextractModelById[s.id] || models[0]?.identifier || ""}
                  onChange={(e) => setReextractModelById((prev) => ({ ...prev, [s.id]: e.target.value }))}
                  disabled={models.length === 0}
                >
                  {models.length === 0 && <option value="">No active models</option>}
                  {models.map((m) => (
                    <option key={m.id} value={m.identifier}>
                      {m.display_name ? `${m.display_name} (${m.identifier})` : m.identifier}
                    </option>
                  ))}
                </select>
                <button onClick={() => handleReextract(s.id)} disabled={busyId === s.id || models.length === 0}>
                  Run Re-extraction
                </button>
              </div>
            )}
          </div>
        ))
      )}
    </div>
  );
}
