"use client";

import { useEffect, useState, type ReactNode } from "react";
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
import { MetadataTag } from "../../../components/MetadataTags";
import StalenessBadge from "../../../components/RepoStaleness";

function TagList({ values }: { values?: string[] | null }) {
  const cleanedValues = (values ?? []).map((value) => value.trim()).filter(Boolean);

  if (cleanedValues.length === 0) {
    return <span className="metadata-tags-empty">Not specified</span>;
  }

  return (
    <div className="metadata-tags-list">
      {cleanedValues.map((value) => <MetadataTag key={value} value={value} />)}
    </div>
  );
}

function DetailItem({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="detail-item">
      <span className="detail-item-label">{label}</span>
      <div className="detail-item-value">{children}</div>
    </div>
  );
}

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
      .then(([loadedBenchmark, loadedMetrics, loadedRepoStats]) => {
        setBenchmark(loadedBenchmark);
        setMetrics(loadedMetrics);
        setRepoStats(loadedRepoStats);
      })
      .catch(() => setError("Failed to load this benchmark."))
      .finally(() => setLoading(false));
  }, [id]);

  if (loading) {
    return <main className="container"><div className="browse-state" role="status">Loading benchmark record.</div></main>;
  }

  if (error || !benchmark) {
    return <main className="container"><div className="browse-state browse-state-error" role="alert">{error ?? "Benchmark not found."}</div></main>;
  }

  return (
    <main className="container">
      <Link href="/browse" className="detail-back-link">← Back to catalogue</Link>

      <header className="detail-header">
        <div>
          <p className="eyebrow">Benchmark record</p>
          <h1>{benchmark.benchmark_name}</h1>
        </div>
        <ComplexityBadge level={benchmark.complexity_level} justification={benchmark.complexity_justification} />
      </header>

      <section className="card" aria-labelledby="benchmark-overview-heading">
        <h2 id="benchmark-overview-heading" className="sr-only">Benchmark overview</h2>
        <p className="detail-paper-title">{benchmark.benchmark_paper_title}</p>
        {benchmark.description && <p className="detail-summary">{benchmark.description}</p>}

        <div className="detail-links">
          {benchmark.paper_link && <a href={benchmark.paper_link} target="_blank" rel="noreferrer">Paper ↗</a>}
          {benchmark.code_repository && <a href={benchmark.code_repository} target="_blank" rel="noreferrer">Code repository ↗</a>}
          {benchmark.dataset_repository && <a href={benchmark.dataset_repository} target="_blank" rel="noreferrer">Dataset repository ↗</a>}
        </div>

        <div className="detail-grid">
          <DetailItem label="Task type"><TagList values={benchmark.task_type} /></DetailItem>
          <DetailItem label="Entry modalities"><TagList values={benchmark.entry_modalities} /></DetailItem>
          <DetailItem label="Language support"><TagList values={benchmark.language_support} /></DetailItem>
          <DetailItem label="License"><MetadataTag value={benchmark.license} /></DetailItem>
          <DetailItem label="Samples">{benchmark.no_of_samples ?? "Not specified"}</DetailItem>
          <DetailItem label="Citations">{benchmark.cited_by} {benchmark.citation_range ? `(${benchmark.citation_range})` : ""}</DetailItem>
          <DetailItem label="Development purpose"><MetadataTag value={benchmark.dev_purpose} /></DetailItem>
          <DetailItem label="Integration"><MetadataTag value={benchmark.integration_option} /></DetailItem>
          <DetailItem label="Release date">{benchmark.release_date ?? "Not specified"}</DetailItem>
        </div>

        {benchmark.complexity_justification && (
          <div className="detail-justification">
            <span className="detail-item-label">Complexity rationale</span>
            <p className="detail-item-value">{benchmark.complexity_justification}</p>
          </div>
        )}
      </section>

      <section className="card" aria-labelledby="metrics-heading">
        <h2 id="metrics-heading" className="detail-section-title">Evaluation metrics catalogue</h2>
        {metrics.length === 0 ? (
          <p className="muted-copy">No evaluation metrics have been catalogued for this benchmark yet.</p>
        ) : (
          <div className="table-scroll">
            <table>
              <thead><tr><th>Metric name</th><th>Conceptual description</th></tr></thead>
              <tbody>
                {metrics.map((metric) => (
                  <tr key={metric.id}>
                    <td><MetadataTag value={metric.metric_name} /></td>
                    <td>{metric.conceptual_description ?? <span className="metadata-tags-empty">Not specified</span>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section className="card" aria-labelledby="repository-activity-heading">
        <h2 id="repository-activity-heading" className="detail-section-title">Repository activity</h2>
        {repoStats.length === 0 ? (
          <p className="muted-copy">No repository activity statistics are recorded for this benchmark yet.</p>
        ) : (
          <div className="table-scroll">
            <table>
              <thead><tr><th>Source</th><th>Owner / name</th><th>Stars / likes</th><th>Status</th><th>Last activity</th><th>License</th></tr></thead>
              <tbody>
                {repoStats.map((stat) => (
                  <tr key={stat.id}>
                    <td>{stat.source}</td>
                    <td>{stat.owner ? `${stat.owner}/${stat.name ?? ""}` : stat.name ?? "Not specified"}</td>
                    <td>{stat.stars_or_likes ?? "Not specified"}</td>
                    <td><StalenessBadge stat={stat} /> <span className="metadata-tags-empty">{stat.activity_status ?? "unknown"}</span></td>
                    <td>{stat.days_since_last_activity != null ? `${stat.days_since_last_activity} days ago` : "Not specified"}</td>
                    <td>{stat.license_id ?? "Not specified"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </main>
  );
}
