// Destination path: frontend/app/browse/[id]/page.tsx
// Replaces the existing file in full.
//
// CHANGE (2026-09-02): ComplexityBadge now receives
// justification={benchmark.complexity_justification}, so hovering the
// badge next to the benchmark name also shows the reason -- in
// addition to the existing "Complexity Justification" paragraph
// further down the page, which already displayed this field in full
// and is unchanged. No other logic on this page changed.

"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import {
  Benchmark,
  EvalMetric,
  RepoStat,
  getBenchmark,
  listMetricsForBenchmark,
  listRepoStatsForBenchmark,
} from "../../../lib/api";
import ComplexityBadge from "../../../components/ComplexityBadge";
import StalenessBadge from "../../../components/RepoStaleness";

/**
 * Phase 5, first deliverable: public benchmark detail page. Surfaces
 * repo_stats' activity_status/is_archived/staleness data, which the
 * roadmap's 2026-07-26 note explicitly flagged as populated by Phase 4
 * but "not currently exposed anywhere in the frontend or export layer
 * yet." Uses the default (history=false) repo-stats call, i.e. latest
 * snapshot per source, matching item 15's fix.
 */
export default function BrowseDetailPage() {
  const params = useParams();
  const id = params.id as string;

  const [benchmark, setBenchmark] = useState<Benchmark | null>(null);
  const [metrics, setMetrics] = useState<EvalMetric[]>([]);
  const [repoStats, setRepoStats] = useState<RepoStat[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    Promise.all([
      getBenchmark(id),
      listMetricsForBenchmark(id).catch(() => []),
      listRepoStatsForBenchmark(id, false).catch(() => []),
    ])
      .then(([b, m, r]) => {
        setBenchmark(b);
        setMetrics(m);
        setRepoStats(r);
      })
      .catch(() => setError("Failed to load this benchmark."))
      .finally(() => setLoading(false));
  }, [id]);

  if (loading) return <div className="container"><p>Loading...</p></div>;
  if (error || !benchmark) return <div className="container"><p className="error">{error ?? "Benchmark not found."}</p></div>;

  return (
    <div className="container">
      <p><Link href="/browse">&larr; Back to Browse</Link></p>

      <div className="topbar">
        <h1 style={{ margin: 0 }}>{benchmark.benchmark_name}</h1>
        <ComplexityBadge level={benchmark.complexity_level} justification={benchmark.complexity_justification} />
      </div>

      <div className="card">
        <p style={{ fontStyle: "italic", color: "#444" }}>{benchmark.benchmark_paper_title}</p>
        {benchmark.paper_link && (
          <p><a href={benchmark.paper_link} target="_blank" rel="noreferrer">View paper &rarr;</a></p>
        )}
        {benchmark.description && <p>{benchmark.description}</p>}

        <div className="form-grid" style={{ marginTop: 16 }}>
          <div className="field">
            <label>Task Type</label>
            <p>{benchmark.task_type.join(", ") || "-"}</p>
          </div>
          <div className="field">
            <label>Entry Modalities</label>
            <p>{benchmark.entry_modalities?.join(", ") || "-"}</p>
          </div>
          <div className="field">
            <label>Language Support</label>
            <p>{benchmark.language_support?.join(", ") || "-"}</p>
          </div>
          <div className="field">
            <label>License</label>
            <p>{benchmark.license ?? "-"}</p>
          </div>
          <div className="field">
            <label>No. of Samples</label>
            <p>{benchmark.no_of_samples ?? "-"}</p>
          </div>
          <div className="field">
            <label>Cited By</label>
            <p>{benchmark.cited_by} {benchmark.citation_range ? `(${benchmark.citation_range})` : ""}</p>
          </div>
          <div className="field">
            <label>Dev Purpose</label>
            <p>{benchmark.dev_purpose ?? "-"}</p>
          </div>
          <div className="field">
            <label>Integration Option</label>
            <p>{benchmark.integration_option}</p>
          </div>
          <div className="field">
            <label>Release Date</label>
            <p>{benchmark.release_date ?? "-"}</p>
          </div>
        </div>

        <div className="form-grid">
          <div className="field">
            <label>Code Repository</label>
            <p>{benchmark.code_repository ? <a href={benchmark.code_repository} target="_blank" rel="noreferrer">{benchmark.code_repository}</a> : "-"}</p>
          </div>
          <div className="field">
            <label>Dataset Repository</label>
            <p>{benchmark.dataset_repository ? <a href={benchmark.dataset_repository} target="_blank" rel="noreferrer">{benchmark.dataset_repository}</a> : "-"}</p>
          </div>
        </div>

        {benchmark.complexity_justification && (
          <div className="field">
            <label>Complexity Justification</label>
            <p style={{ fontSize: 13, color: "#444" }}>{benchmark.complexity_justification}</p>
          </div>
        )}
      </div>

      <div className="card">
        <h3 style={{ marginTop: 0 }}>Evaluation Metrics Catalogue</h3>
        {metrics.length === 0 ? (
          <p style={{ color: "#666", fontSize: 13 }}>No evaluation metrics catalogued for this benchmark yet.</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Metric Name</th>
                <th>Conceptual Description</th>
              </tr>
            </thead>
            <tbody>
              {metrics.map((m) => (
                <tr key={m.id}>
                  <td>{m.metric_name}</td>
                  <td>{m.conceptual_description ?? <em style={{ color: "#999" }}>None</em>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <div className="card">
        <h3 style={{ marginTop: 0 }}>Repository Activity</h3>
        {repoStats.length === 0 ? (
          <p style={{ color: "#666", fontSize: 13 }}>No repository activity statistics recorded yet for this benchmark.</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Source</th>
                <th>Owner / Name</th>
                <th>Stars / Likes</th>
                <th>Status</th>
                <th>Last Activity</th>
                <th>License</th>
              </tr>
            </thead>
            <tbody>
              {repoStats.map((stat) => (
                <tr key={stat.id}>
                  <td>{stat.source}</td>
                  <td>{stat.owner ? `${stat.owner}/${stat.name ?? ""}` : stat.name ?? "-"}</td>
                  <td>{stat.stars_or_likes ?? "-"}</td>
                  <td><StalenessBadge stat={stat} /> <span style={{ fontSize: 12, color: "#888" }}>({stat.activity_status ?? "unknown"})</span></td>
                  <td>{stat.days_since_last_activity != null ? `${stat.days_since_last_activity} days ago` : "-"}</td>
                  <td>{stat.license_id ?? "-"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
