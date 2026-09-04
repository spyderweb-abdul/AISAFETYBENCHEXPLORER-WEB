"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { HeatmapDimension, ResearchGapHeatmap, getResearchGapHeatmap } from "../../../lib/api";

const SEVERITY_CLASS: Record<string, string> = {
  "Critical Gap": "status-tag status-tag--danger",
  "Under-benchmarked": "status-tag status-tag--warning",
  "Limited Advanced": "status-tag status-tag--info",
  "Well-covered": "status-tag status-tag--success",
  "Not Covered": "status-tag",
};

function SeverityBadge({ severity }: { severity: string }) {
  return <span className={SEVERITY_CLASS[severity] ?? "status-tag"}>{severity}</span>;
}

export default function HeatmapPage() {
  const [data, setData] = useState<ResearchGapHeatmap | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getResearchGapHeatmap()
      .then(setData)
      .catch(() => setError("Failed to load the research gap heatmap."))
      .finally(() => setLoading(false));
  }, []);

  const sorted: HeatmapDimension[] = data
    ? [...data.dimensions].sort((a, b) => b.total - a.total)
    : [];

  return (
    <main className="container">
      <Link href="/browse" className="detail-back-link">← Back to catalogue</Link>
      <header className="page-header">
        <div>
          <p className="eyebrow">Coverage analysis</p>
          <h1>Research gap heatmap</h1>
          <p className="page-description">
            Distribution of published benchmarks across safety dimensions and complexity levels.
            {data ? ` ${data.total_benchmarks} published benchmark${data.total_benchmarks === 1 ? "" : "s"} counted.` : ""}
          </p>
        </div>
      </header>

      <section className="card" aria-labelledby="heatmap-table-heading">
        <h2 id="heatmap-table-heading" className="sr-only">Research gap heatmap table</h2>
        {loading ? (
          <div className="browse-state" role="status">Loading research-gap analysis.</div>
        ) : error ? (
          <div className="browse-state browse-state-error" role="alert">{error}</div>
        ) : (
          <div className="table-scroll">
            <table>
              <thead><tr><th>Safety dimension</th><th>Popular</th><th>High</th><th>Medium</th><th>Low</th><th>Total</th><th>Coverage signal</th></tr></thead>
              <tbody>
                {sorted.map((row) => (
                  <tr key={row.dimension}>
                    <td><strong>{row.dimension}</strong></td>
                    <td>{row.popular}</td><td>{row.high}</td><td>{row.medium}</td><td>{row.low}</td>
                    <td><strong>{row.total}</strong></td>
                    <td><SeverityBadge severity={row.gap_severity} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <aside className="card" aria-labelledby="heatmap-guide-heading">
        <h2 id="heatmap-guide-heading" className="detail-section-title">Reading the coverage signal</h2>
        <p className="muted-copy"><strong>Critical gap</strong> has no Popular or High-complexity benchmark. <strong>Under-benchmarked</strong> has fewer than 30% Popular or High records. <strong>Limited advanced</strong> has some Popular records but no High record. <strong>Well-covered</strong> has a healthy mix of Popular and High records.</p>
      </aside>
    </main>
  );
}
