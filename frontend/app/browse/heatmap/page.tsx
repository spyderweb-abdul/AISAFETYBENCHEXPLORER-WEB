"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { HeatmapDimension, ResearchGapHeatmap, getResearchGapHeatmap } from "../../../lib/api";

const SEVERITY_STYLE: Record<string, { background: string; color: string }> = {
  "Critical Gap": { background: "#fee2e2", color: "#991b1b" },
  "Under-benchmarked": { background: "#fef3c7", color: "#92400e" },
  "Limited Advanced": { background: "#e0e7ff", color: "#3730a3" },
  "Well-covered": { background: "#dcfce7", color: "#166534" },
  "Not Covered": { background: "#e5e5e5", color: "#444" },
};

function SeverityBadge({ severity }: { severity: string }) {
  const style = SEVERITY_STYLE[severity] || { background: "#e5e5e5", color: "#444" };
  return <span className="badge" style={style}>{severity}</span>;
}

/**
 * Phase 5: public Research Gap Heatmap, replicating
 * research_gap_heatmap.py's exact severity rules server-side (see
 * app/core/safety_dimension_classifier.py). Table replaces the
 * original script's static Excel coloring with a live, DB-backed view.
 */
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
    <div className="container">
      <p><Link href="/browse">&larr; Back to Browse</Link></p>
      <div className="topbar">
        <h1 style={{ margin: 0 }}>Research Gap Heatmap</h1>
      </div>
      <p style={{ color: "#666", fontSize: 13, marginTop: -8, marginBottom: 20 }}>
        Distribution of published benchmarks across safety dimensions and complexity
        levels, with a gap-severity assessment per dimension.
        {data ? ` ${data.total_benchmarks} published benchmark${data.total_benchmarks === 1 ? "" : "s"} counted.` : ""}
      </p>

      <div className="card">
        {loading ? (
          <p>Loading...</p>
        ) : error ? (
          <p className="error">{error}</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Safety Dimension</th>
                <th>Popular</th>
                <th>High</th>
                <th>Medium</th>
                <th>Low</th>
                <th>Total</th>
                <th>Gap Severity</th>
              </tr>
            </thead>
            <tbody>
              {sorted.map((row) => (
                <tr key={row.dimension}>
                  <td>{row.dimension}</td>
                  <td>{row.popular}</td>
                  <td>{row.high}</td>
                  <td>{row.medium}</td>
                  <td>{row.low}</td>
                  <td><strong>{row.total}</strong></td>
                  <td><SeverityBadge severity={row.gap_severity} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <div className="card">
        <h3 style={{ marginTop: 0 }}>How to Read This</h3>
        <ul style={{ fontSize: 13, color: "#444" }}>
          <li><strong>Critical Gap</strong>: no Popular or High-complexity benchmarks exist for this dimension yet.</li>
          <li><strong>Under-benchmarked</strong>: fewer than 30% of this dimension&apos;s benchmarks are Popular or High complexity.</li>
          <li><strong>Limited Advanced</strong>: some Popular benchmarks exist, but none reach High complexity.</li>
          <li><strong>Well-covered</strong>: a healthy mix of Popular and High-complexity benchmarks exists.</li>
        </ul>
      </div>
    </div>
  );
}
