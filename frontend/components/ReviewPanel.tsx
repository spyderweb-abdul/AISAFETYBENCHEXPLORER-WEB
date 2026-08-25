"use client";

import { useState } from "react";
import { Benchmark, reviewBenchmark } from "../lib/api";

interface Props {
  benchmark: Benchmark;
  onReviewed: (updated: Benchmark) => void;
}

/**
 * FIX (2026-08-23): benchmark-centric review panel, reachable directly
 * from the benchmark edit page. Closes a real dead end reported by the
 * admin user: benchmarks could get stuck at status="pending_review"
 * indefinitely with no way to change that from this page (status was
 * never an editable field on BenchmarkForm) and no guarantee of
 * appearing in the Extraction Panel's Pending Review queue either (a
 * high quality_score job's status becomes "done" immediately, which
 * that queue previously treated as "already handled").
 *
 * Shows quality_score and complexity_justification directly here too
 * ("seeing the uncertainties" the admin user asked for), rather than
 * making the reviewer cross-reference the Extraction Panel separately.
 */
export default function ReviewPanel({ benchmark, onReviewed }: Props) {
  const [reviewerNote, setReviewerNote] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (benchmark.status !== "pending_review") {
    return null;
  }

  async function handleReview(approve: boolean) {
    setSubmitting(true);
    setError(null);
    try {
      const updated = await reviewBenchmark(benchmark.id, approve, reviewerNote || undefined);
      onReviewed(updated);
    } catch (err: any) {
      setError(
        err?.response?.data?.detail
          ? JSON.stringify(err.response.data.detail)
          : "Review action failed."
      );
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="card" style={{ background: "#fefce8", border: "1px solid #fde68a" }}>
      <h3 style={{ marginTop: 0 }}>Pending Review</h3>
      <p style={{ fontSize: 13, color: "#666" }}>
        This benchmark was extracted and is awaiting approval before it
        becomes visible on the public /browse dashboard. Review the
        fields above (and the uncertainty signals below) before
        deciding.
      </p>

      <div className="form-grid">
        <div className="field">
          <label>Complexity Level</label>
          <p>{benchmark.complexity_level}</p>
        </div>
        <div className="field">
          <label>Complexity Justification</label>
          <p style={{ fontSize: 13 }}>{benchmark.complexity_justification || <em style={{ color: "#999" }}>None provided</em>}</p>
        </div>
      </div>

      <div className="field">
        <label>Reviewer Note (optional)</label>
        <input
          type="text"
          value={reviewerNote}
          onChange={(e) => setReviewerNote(e.target.value)}
          placeholder="e.g. verified license and repo links manually before approving"
        />
      </div>

      {error && <p className="error">{error}</p>}

      <div style={{ display: "flex", gap: 8 }}>
        <button type="button" onClick={() => handleReview(true)} disabled={submitting}>
          {submitting ? "Saving..." : "Approve -- Publish"}
        </button>
        <button type="button" className="danger" onClick={() => handleReview(false)} disabled={submitting}>
          {submitting ? "Saving..." : "Reject"}
        </button>
      </div>
    </div>
  );
}
