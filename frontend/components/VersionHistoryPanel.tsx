// Destination path: frontend/components/VersionHistoryPanel.tsx
// New file. (Replaces the previous draft in this same session -- fixed
// a real bug: the shorthand <>...</> fragment used per table row in the
// .map() below cannot carry a `key` prop, which would have produced a
// React "each child in a list should have a unique key" warning and
// unreliable reconciliation when rows expand/collapse. Fixed by using
// <React.Fragment key={...}> instead, which is the only fragment form
// that accepts a key.)
//
// Phase 6 item 2: read-only version history for a single benchmark.
// No backend changes were needed for this -- GET /audit-log already
// supports table_name and record_id query params (see
// app/routers/audit.py), and every create/update/delete/approve/
// reject action on a benchmark already writes a row there via
// log_action() (see app/core/audit.py and app/routers/benchmarks.py).
// This panel is purely a new, filtered view over data that has
// existed since Phase 2.
//
// Each entry's diff is rendered as formatted JSON rather than a
// field-by-field table, since the diff shape varies by action
// (create logs the full payload; update logs {before, after}; the new
// Phase 6 citation_refresh / citation_refresh_promoted_to_popular
// actions log {before_cited_by, after_cited_by,
// before_complexity_level, after_complexity_level}; approve/reject
// logs {before, after, reviewer_note}) -- a generic JSON view avoids
// hardcoding assumptions about any one action's diff shape, and stays
// correct automatically if a future action type adds new diff keys.
//
// changed_by is rendered as "System" when null, since Phase 6's
// citation refresh job intentionally passes changed_by=None to
// distinguish automated changes from human admin actions in this
// same view.

"use client";

import { Fragment, useEffect, useState } from "react";
import { AuditLogEntry, fetchAuditLog } from "../lib/api";

interface Props {
  benchmarkId: string;
}

const ACTION_LABELS: Record<string, string> = {
  create: "Created",
  update: "Updated",
  delete: "Deleted",
  approve: "Approved",
  reject: "Rejected",
  citation_refresh: "Citation count refreshed",
  citation_refresh_promoted_to_popular: "Promoted to Popular (citation refresh)",
};

const ACTION_BADGE_STYLE: Record<string, { background: string; color: string }> = {
  create: { background: "#dcfce7", color: "#166534" },
  update: { background: "#e0e7ff", color: "#3730a3" },
  delete: { background: "#fee2e2", color: "#991b1b" },
  approve: { background: "#dcfce7", color: "#166534" },
  reject: { background: "#fee2e2", color: "#991b1b" },
  citation_refresh: { background: "#fef3c7", color: "#92400e" },
  citation_refresh_promoted_to_popular: { background: "#fef3c7", color: "#92400e" },
};

function ActionBadge({ action }: { action: string }) {
  const style = ACTION_BADGE_STYLE[action] || { background: "#e5e5e5", color: "#444" };
  return (
    <span className="badge" style={style}>
      {ACTION_LABELS[action] || action.replaceAll("_", " ")}
    </span>
  );
}

export default function VersionHistoryPanel({ benchmarkId }: Props) {
  const [entries, setEntries] = useState<AuditLogEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expandedId, setExpandedId] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    fetchAuditLog({ table_name: "benchmarks", record_id: benchmarkId })
      .then(setEntries)
      .catch(() => setError("Failed to load version history."))
      .finally(() => setLoading(false));
  }, [benchmarkId]);

  return (
    <div className="card">
      <h2 className="detail-section-title">Version history</h2>
      {loading ? (
        <p>Loading...</p>
      ) : error ? (
        <p className="error">{error}</p>
      ) : entries.length === 0 ? (
        <p className="muted-copy">No recorded changes for this benchmark yet.</p>
      ) : (
        <div className="table-scroll"><table>
          <thead>
            <tr>
              <th>When</th>
              <th>Action</th>
              <th>Changed By</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {entries.map((entry) => (
              <Fragment key={entry.id}>
                <tr>
                  <td>{new Date(entry.created_at).toLocaleString()}</td>
                  <td><ActionBadge action={entry.action} /></td>
                  <td className={entry.changed_by ? undefined : "metadata-tags-empty"}>
                    {entry.changed_by ?? "System"}
                  </td>
                  <td>
                    <button
                      className="secondary"
                      onClick={() => setExpandedId(expandedId === entry.id ? null : entry.id)}
                    >
                      {expandedId === entry.id ? "Hide details" : "Show details"}
                    </button>
                  </td>
                </tr>
                {expandedId === entry.id && (
                  <tr>
                    <td colSpan={4}>
                      <pre className="code-block">
                        {JSON.stringify(entry.diff, null, 2)}
                      </pre>
                    </td>
                  </tr>
                )}
              </Fragment>
            ))}
          </tbody>
        </table></div>
      )}
    </div>
  );
}
