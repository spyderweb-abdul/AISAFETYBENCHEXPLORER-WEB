// Destination path: frontend/app/submit/page.tsx
// Replaces the existing file in full.
//
// FIX (2026-09-02): Next.js build failure -- "Error occurred
// prerendering page /submit" / build worker exited with code 1.
// Root cause: useSearchParams() (added in the previous session's
// notification-highlight fix) bails out of static rendering and MUST
// be wrapped in a <Suspense> boundary in the App Router, or `next
// build`'s prerender step fails outright. All component logic that
// reads searchParams (and therefore needs to live inside the Suspense
// boundary) is moved into a new inner component, SubmitPageInner;
// the default export is now a thin wrapper that renders
// <Suspense><SubmitPageInner /></Suspense>. No behavior changed --
// same highlight-and-scroll logic as before, just correctly wrapped.

"use client";

import { Suspense, useEffect, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Cookies from "js-cookie";
import { Submission, createSubmission, fetchMe, listMySubmissions } from "../../lib/api";

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

function SubmitPageInner() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const highlightId = searchParams.get("highlight");

  const [doi, setDoi] = useState("");
  const [submissions, setSubmissions] = useState<Submission[]>([]);
  const [checking, setChecking] = useState(true);
  const [allowed, setAllowed] = useState(false);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [highlightedId, setHighlightedId] = useState<string | null>(null);

  const rowRefs = useRef<Record<string, HTMLTableRowElement | null>>({});

  useEffect(() => {
    if (!Cookies.get("access_token")) {
      router.replace("/signup");
      return;
    }
    fetchMe()
      .then((u) => {
        if (u.role === "admin") {
          router.replace("/admin/benchmarks");
          return;
        }
        setAllowed(true);
        load();
      })
      .catch(() => {
        Cookies.remove("access_token");
        router.replace("/login");
      })
      .finally(() => setChecking(false));
  }, [router]);

  async function load() {
    setLoading(true);
    try {
      const data = await listMySubmissions();
      setSubmissions(data);
    } catch {
      setError("Failed to load your submission history.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (!highlightId || loading) return;
    const found = submissions.some((s) => s.id === highlightId);
    if (!found) return;

    setHighlightedId(highlightId);
    const el = rowRefs.current[highlightId];
    el?.scrollIntoView({ behavior: "smooth", block: "center" });

    const timer = setTimeout(() => setHighlightedId(null), 4000);
    return () => clearTimeout(timer);
  }, [highlightId, loading, submissions]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    setNotice(null);
    try {
      await createSubmission(doi.trim());
      setNotice(
        "Submission received and queued for extraction. This runs in the " +
        "background -- refresh this page in a minute to see its status."
      );
      setDoi("");
      load();
    } catch (err: any) {
      setError(err?.response?.data?.detail || "Submission failed.");
    } finally {
      setSubmitting(false);
    }
  }

  if (checking) return <div className="container"><p>Checking access...</p></div>;
  if (!allowed) return null;

  return (
    <div className="container">
      <h1>Submit a Benchmark</h1>
      <p style={{ color: "#666", fontSize: 13 }}>
        Submit a DOI for a paper describing an AI safety benchmark. It will be
        automatically extracted and checked for domain relevance and
        extraction quality, then queued for admin review. You'll be notified
        here and by email once a decision is made.
      </p>

      <form onSubmit={handleSubmit} className="card" style={{ display: "flex", gap: 12, alignItems: "flex-end", flexWrap: "wrap" }}>
        <div className="field" style={{ flex: 1, minWidth: 260 }}>
          <label>DOI</label>
          <input
            value={doi}
            onChange={(e) => setDoi(e.target.value)}
            placeholder="e.g. 10.1073/pnas.2416228122"
            required
            minLength={5}
          />
        </div>
        <button type="submit" disabled={submitting}>{submitting ? "Submitting..." : "Submit for Review"}</button>
      </form>
      {notice && <p style={{ color: "#166534", fontSize: 13 }}>{notice}</p>}
      {error && <p className="error">{error}</p>}

      <div className="card">
        <h3 style={{ marginTop: 0 }}>Your Submissions</h3>
        {loading ? (
          <p>Loading...</p>
        ) : submissions.length === 0 ? (
          <p style={{ color: "#666", fontSize: 13 }}>You haven't submitted any benchmarks yet.</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Source</th>
                <th>Status</th>
                <th>Quality Score</th>
                <th>Domain Check</th>
                <th>Reviewer Notes</th>
                <th>Submitted</th>
              </tr>
            </thead>
            <tbody>
              {submissions.map((s) => (
                <tr
                  key={s.id}
                  ref={(el) => { rowRefs.current[s.id] = el; }}
                  style={
                    highlightedId === s.id
                      ? { boxShadow: "inset 0 0 0 2px #6366f1", transition: "box-shadow 0.3s ease" }
                      : undefined
                  }
                >
                  <td>{s.source_value}</td>
                  <td><StatusBadge status={s.status} /></td>
                  <td>{s.quality_score != null ? s.quality_score.toFixed(2) : "-"}</td>
                  <td style={{ fontSize: 12, maxWidth: 240 }}>
                    {s.domain_check_passed === true ? "Passed" : s.domain_check_passed === false ? "Failed" : s.domain_check_passed === null && s.domain_check_reason ? "Borderline" : "-"}
                    {s.domain_check_reason && <div style={{ color: "#888" }}>{s.domain_check_reason}</div>}
                  </td>
                  <td style={{ fontSize: 12, maxWidth: 240 }}>{s.admin_review_notes || "-"}</td>
                  <td style={{ fontSize: 12 }}>{new Date(s.created_at).toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

export default function SubmitPage() {
  return (
    <Suspense fallback={<div className="container"><p>Loading...</p></div>}>
      <SubmitPageInner />
    </Suspense>
  );
}