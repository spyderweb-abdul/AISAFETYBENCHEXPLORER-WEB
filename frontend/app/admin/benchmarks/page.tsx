"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Benchmark, deleteBenchmark, exportXlsxUrl, listBenchmarks } from "../../../lib/api";
import ComplexityBadge from "../../../components/ComplexityBadge";

export default function BenchmarksListPage() {
  const [benchmarks, setBenchmarks] = useState<Benchmark[]>([]);
  const [search, setSearch] = useState("");
  const [complexity, setComplexity] = useState("");
  const [loading, setLoading] = useState(true);

  async function load() {
    setLoading(true);
    const params: Record<string, string> = {};
    if (search) params.search = search;
    if (complexity) params.complexity_level = complexity;
    const data = await listBenchmarks(params);
    setBenchmarks(data);
    setLoading(false);
  }

  useEffect(() => { load(); }, [search, complexity]);

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

      <div className="card" style={{ display: "flex", gap: 12 }}>
        <input placeholder="Search by name..." value={search} onChange={(e) => setSearch(e.target.value)} />
        <select value={complexity} onChange={(e) => setComplexity(e.target.value)}>
          <option value="">All complexity levels</option>
          <option value="Popular">Popular</option>
          <option value="High">High</option>
          <option value="Medium">Medium</option>
          <option value="Low">Low</option>
          <option value="Unknown">Unknown</option>
        </select>
      </div>

      <div className="card">
        {loading ? <p>Loading...</p> : (
          <table>
            <thead>
              <tr>
                <th>Name</th><th>Task Type</th><th>Complexity</th><th>Cited By</th><th>License</th><th></th>
              </tr>
            </thead>
            <tbody>
              {benchmarks.map((b) => (
                <tr key={b.id}>
                  <td><Link href={`/admin/benchmarks/${b.id}`}>{b.benchmark_name}</Link></td>
                  <td>{b.task_type.join(", ")}</td>
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
