"use client";

import { useEffect, useState } from "react";
import {
  GithubRateLimit,
  RepoStat,
  getGithubRateLimit,
  listRepoStatsForBenchmark,
  triggerRepoStatsRefresh,
  triggerRepoStatsRefreshAll,
} from "../lib/api";

interface Props {
  benchmarkId: string;
  codeRepository?: string | null;
  datasetRepository?: string | null;
}

/**
 * Roadmap item 13: admin-UI manual trigger for the Phase 4 scraper
 * Celery tasks. Extended (2026-08-16) to close items 14 and 15, which
 * had shipped as backend-only additions with no way to see them from
 * the UI:
 * - Item 15: a History toggle, switching between the default
 *   latest-only view and the full time series via ?history=true.
 * - Item 14: a GitHub API Quota readout, so remaining headroom is
 *   visible here instead of only discoverable via /docs or a failed
 *   bulk refresh.
 */
export default function RepoStatsPanel({
  benchmarkId,
  codeRepository,
  datasetRepository,
}: Props) {
  const [stats, setStats] = useState<RepoStat[]>([]);
  const [showHistory, setShowHistory] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [refreshingAll, setRefreshingAll] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);

  const [quota, setQuota] = useState<GithubRateLimit | null>(null);
  const [quotaLoading, setQuotaLoading] = useState(false);
  const [quotaError, setQuotaError] = useState<string | null>(null);

  async function refresh() {
    setLoading(true);
    setError(null);
    try {
      const data = await listRepoStatsForBenchmark(benchmarkId, showHistory);
      setStats(data);
    } catch (err: any) {
      setError("Failed to load repository activity statistics.");
    } finally {
      setLoading(false);
    }
  }

  async function loadQuota() {
    setQuotaLoading(true);
    setQuotaError(null);
    try {
      const data = await getGithubRateLimit();
      setQuota(data);
    } catch (err: any) {
      setQuotaError(
        err?.response?.status === 401
          ? "Not authorized -- make sure you're logged in as admin."
          : "Failed to check GitHub API quota."
      );
    } finally {
      setQuotaLoading(false);
    }
  }

  useEffect(() => {
    refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [benchmarkId, showHistory]);

  useEffect(() => {
    loadQuota();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function handleRefreshNow() {
    setRefreshing(true);
    setNotice(null);
    setError(null);
    try {
      const result = await triggerRepoStatsRefresh(benchmarkId);
      setNotice(`Refresh queued (task ${result.task_id}). Click Reload in a few seconds to see updated values.`);
    } catch (err: any) {
      setError(err?.response?.data?.detail ? JSON.stringify(err.response.data.detail) : "Failed to queue refresh.");
    } finally {
      setRefreshing(false);
    }
  }

  async function handleRefreshAll() {
    if (!confirm("Queue a repository stats refresh for every benchmark? This runs on the weekly schedule too, so only do this if you need updated numbers right now.")) return;
    setRefreshingAll(true);
    setNotice(null);
    setError(null);
    try {
      const result = await triggerRepoStatsRefreshAll();
      if ((result as any).skipped_due_to_rate_limit) {
        setNotice(
          `Bulk refresh skipped -- not enough GitHub API quota remaining ` +
          `(needed ~${(result as any).estimated_github_requests_needed}, ` +
          `${(result as any).github_rate_limit_status?.remaining ?? "?"} left). ` +
          `Check the quota panel below or wait for it to reset.`
        );
      } else {
        setNotice(`Bulk refresh queued for all benchmarks (task ${result.task_id}).`);
      }
      loadQuota();
    } catch (err: any) {
      setError(err?.response?.data?.detail ? JSON.stringify(err.response.data.detail) : "Failed to queue bulk refresh.");
    } finally {
      setRefreshingAll(false);
    }
  }

  const hasAnyRepo = Boolean(codeRepository || datasetRepository);
  const quotaLow = quota ? quota.remaining < 50 : false;

  return (
    <div className="card">
      <div className="topbar">
        <h3 style={{ margin: 0 }}>Repository Activity Statistics</h3>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <label style={{ fontWeight: 400, fontSize: 12, display: "flex", alignItems: "center", gap: 4 }}>
            <input
              type="checkbox"
              checked={showHistory}
              onChange={(e) => setShowHistory(e.target.checked)}
            />
            Show full history
          </label>
          <button type="button" className="secondary" onClick={refresh} disabled={loading}>
            Reload
          </button>
          <button type="button" onClick={handleRefreshNow} disabled={refreshing || !hasAnyRepo}>
            {refreshing ? "Queuing..." : "Refresh Now"}
          </button>
          <button type="button" className="secondary" onClick={handleRefreshAll} disabled={refreshingAll}>
            {refreshingAll ? "Queuing..." : "Refresh All Benchmarks"}
          </button>
        </div>
      </div>

      {/* Roadmap item 14: GitHub API quota readout */}
      <div
        style={{
          marginBottom: 12,
          padding: "8px 12px",
          borderRadius: 6,
          fontSize: 12,
          background: quotaLow ? "#fee2e2" : "#f3f4f6",
          color: quotaLow ? "#991b1b" : "#444",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
        }}
      >
        {quotaLoading ? (
          <span>Checking GitHub API quota...</span>
        ) : quotaError ? (
          <span>{quotaError}</span>
        ) : quota ? (
          <span>
            GitHub API quota: <strong>{quota.remaining}</strong> / {quota.limit} remaining
            {quotaLow ? " -- running low" : ""}
            {" "}(resets {new Date(quota.reset_at).toLocaleString()})
            {!quota.authenticated && " -- unauthenticated (set GITHUB_TOKEN for a higher limit)"}
          </span>
        ) : (
          <span>GitHub API quota unknown.</span>
        )}
        <button type="button" className="secondary" onClick={loadQuota} disabled={quotaLoading} style={{ fontSize: 12, padding: "2px 8px" }}>
          Recheck
        </button>
      </div>

      {!hasAnyRepo && (
        <p style={{ color: "#666", fontSize: 13 }}>
          This benchmark has no code_repository or dataset_repository set, so there is nothing to refresh.
        </p>
      )}

      {notice && (
        <div className="badge badge-medium" style={{ display: "block", marginBottom: 12, padding: "8px 10px" }}>
          {notice}
        </div>
      )}

      {error && <p className="error">{error}</p>}

      {loading ? (
        <p>Loading repository activity statistics...</p>
      ) : stats.length === 0 ? (
        <p style={{ color: "#666", fontSize: 13 }}>
          No repository activity statistics recorded yet for this benchmark.
        </p>
      ) : (
        <table>
          <thead>
            <tr>
              <th>Source</th>
              <th>Owner / Name</th>
              <th>Stars / Likes</th>
              <th>Activity</th>
              <th>Archived</th>
              <th>License</th>
              <th>Fetched At</th>
              <th>Error</th>
            </tr>
          </thead>
          <tbody>
            {stats.map((row) => (
              <tr key={row.id}>
                <td>{row.source}</td>
                <td>{row.owner ? `${row.owner}/${row.name ?? ""}` : row.name ?? "-"}</td>
                <td>{row.stars_or_likes ?? "-"}</td>
                <td>
                  {row.activity_status ?? "unknown"}
                  {row.days_since_last_activity != null ? ` (${row.days_since_last_activity}d)` : ""}
                </td>
                <td>{row.is_archived ? "Yes" : "No"}</td>
                <td>{row.license_id ?? "-"}</td>
                <td>{new Date(row.fetched_at).toLocaleString()}</td>
                <td style={{ color: row.fetch_error ? "#b91c1c" : "#999" }}>
                  {row.fetch_error ?? "-"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {showHistory && stats.length > 0 && (
        <p style={{ color: "#666", fontSize: 12, marginTop: 8 }}>
          Showing full history ({stats.length} snapshot{stats.length === 1 ? "" : "s"} across all sources). Uncheck &quot;Show full history&quot; to see only the latest per source.
        </p>
      )}
    </div>
  );
}
