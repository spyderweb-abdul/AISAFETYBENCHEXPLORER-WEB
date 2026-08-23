"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Benchmark, USE_CASE_CATEGORIES, deleteBenchmark, exportXlsxUrl, listBenchmarks } from "../../../lib/api";
import ComplexityBadge from "../../../components/ComplexityBadge";

const STATUS_BADGE_STYLE: Record<string, { background: string; color: string }> = {
  published: { background: "#dcfce7", color: "#166534" },
  pending_review: { background: "#fef3c7", color: "#92400e" },
  rejected: { background: "#fee2e2", color: "#991b1b" },
};

function StatusBadge({ status }: { status: string }) {
  const style = STATUS_BADGE_STYLE[status] || { background: "#e5e5e5", color: "#444" };
  return (
    <span className="badge" style={style}>
      {status.replaceAll("_", " ")}
    </span>
  );
}

export default function BenchmarksListPage() {
  const [benchmarks, setBenchmarks] = useState<Benchmark[]>([]);
  const [search, setSearch] = useState("");
  const [complexity, setComplexity] = useState("");
  const [status, setStatus] = useState("");
  const [useCase, setUseCase] = useState("");
  const [loading, setLoading] = useState(true);

  async function load() {
    setLoading(true);
    const params: Record<string, string> = {};
    if (search) params.search = search;
    if (complexity) params.complexity_level = complexity;
    if (status) params.status = status;
    if (useCase) params.use_case = useCase;
    const data = await listBenchmarks(params);
    setBenchmarks(data);
    setLoading(false);
  }

  useEffect(() => { load(); }, [search, complexity, status, useCase]);

  async function handleDelete(id: string) {
    if (!confirm("Delete this benchmark record? This cannot be undone.")) return;
    await deleteBenchmark(id);
    load();
  }

  return (
    <div className="container">
      <div className="topbar">
        <h2>Benchmarks ({benchmarks.length})</h2>
        <div style={{ display: "flex", gap: 8 }}>
          <a href={exportXlsxUrl()}><button className="secondary">Export to Excel</button></a>
          <Link href="/admin/benchmarks/new"><button>+ New Benchmark</button></Link>
        </div>
      </div>

      <div className="card" style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
        <input placeholder="Search by name..." value={search} onChange={(e) => setSearch(e.target.value)} />
        <select value={complexity} onChange={(e) => setComplexity(e.target.value)}>
          <option value="">All complexity levels</option>
          <option value="Popular">Popular</option>
          <option value="High">High</option>
          <option value="Medium">Medium</option>
          <option value="Low">Low</option>
          <option value="Unknown">Unknown</option>
        </select>
        <select value={useCase} onChange={(e) => setUseCase(e.target.value)}>
          <option value="">All use cases</option>
          {USE_CASE_CATEGORIES.map((u) => (
            <option key={u} value={u}>{u}</option>
          ))}
        </select>
        <select value={status} onChange={(e) => setStatus(e.target.value)}>
          <option value="">Default (hides rejected)</option>
          <option value="published">Published only</option>
          <option value="pending_review">Pending review only</option>
          <option value="rejected">Rejected only</option>
        </select>
      </div>

      <div className="card">
        {loading ? <p>Loading...</p> : (
          <table>
            <thead>
              <tr>
                <th>Name</th><th>Task Type</th><th>Use Case</th><th>Status</th><th>Complexity</th><th>Cited By</th><th>License</th><th></th>
              </tr>
            </thead>
            <tbody>
              {benchmarks.map((b) => (
                <tr key={b.id}>
                  <td><Link href={`/admin/benchmarks/${b.id}`}>{b.benchmark_name}</Link></td>
                  <td>{b.task_type.join(", ")}</td>
                  <td>{b.use_cases?.join(", ") || "-"}</td>
                  <td><StatusBadge status={b.status} /></td>
                  <td><ComplexityBadge level={b.complexity_level} /></td>
                  <td>{b.cited_by}</td>
                  <td>{b.license}</td>
                  <td>
                    <button className="danger" onClick={() => handleDelete(b.id)}>Delete</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
