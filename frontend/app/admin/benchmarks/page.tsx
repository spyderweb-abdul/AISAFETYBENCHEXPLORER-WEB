// Destination path: frontend/app/admin/benchmarks/page.tsx
// Replaces the existing file in full.
//
// CHANGE (Known Gap item 19 fix, this session): the Use Case filter
// dropdown previously imported the hardcoded USE_CASE_CATEGORIES
// constant from lib/api.ts (removed there in this same session). This
// page had no vocab fetch at all before now -- added the same
// fetchVocab()-on-mount pattern already used by BrowsePage and
// BenchmarkForm, and the dropdown now reads vocab.use_cases instead of
// a hardcoded list, closing the same drift risk fixed on the public
// /browse page. No other behavior (search, complexity/status filters,
// delete, export link) changed.

"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Benchmark, Vocab, deleteBenchmark, exportXlsxUrl, fetchVocab, listBenchmarks } from "../../../lib/api";
import ComplexityBadge from "../../../components/ComplexityBadge";

const STATUS_BADGE_CLASS: Record<string, string> = {
  published: "status-tag status-tag--success",
  pending_review: "status-tag status-tag--warning",
  rejected: "status-tag status-tag--danger",
};

function StatusBadge({ status }: { status: string }) {
  return (
    <span className={STATUS_BADGE_CLASS[status] ?? "status-tag"}>
      {status.replaceAll("_", " ")}
    </span>
  );
}

export default function BenchmarksListPage() {
  const [benchmarks, setBenchmarks] = useState<Benchmark[]>([]);
  const [vocab, setVocab] = useState<Vocab | null>(null);
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

  useEffect(() => {
    fetchVocab().then(setVocab).catch(() => setVocab(null));
  }, []);

  useEffect(() => { load(); }, [search, complexity, status, useCase]);

  async function handleDelete(id: string) {
    if (!confirm("Delete this benchmark record? This cannot be undone.")) return;
    await deleteBenchmark(id);
    load();
  }

  return (
    <main className="admin-page">
      <header className="page-header">
        <div>
          <p className="eyebrow">Catalogue administration</p>
          <h1>Benchmarks <span className="metadata-tags-empty">{benchmarks.length}</span></h1>
          <p className="page-description">Review, curate, publish, and export benchmark records.</p>
        </div>
        <div className="admin-actions">
          <a href={exportXlsxUrl()} className="button secondary">Export Excel</a>
          <Link href="/admin/benchmarks/new" className="button">New benchmark</Link>
        </div>
      </header>

      <section className="card" aria-label="Benchmark filters">
        <div className="admin-toolbar">
        <input aria-label="Search benchmarks by name" placeholder="Search benchmark name" value={search} onChange={(e) => setSearch(e.target.value)} />
        <select aria-label="Filter benchmarks by complexity" value={complexity} onChange={(e) => setComplexity(e.target.value)}>
          <option value="">All complexity levels</option>
          <option value="Popular">Popular</option>
          <option value="High">High</option>
          <option value="Medium">Medium</option>
          <option value="Low">Low</option>
          <option value="Unknown">Unknown</option>
        </select>
        <select aria-label="Filter benchmarks by use case" value={useCase} onChange={(e) => setUseCase(e.target.value)}>
          <option value="">All use cases</option>
          {(vocab?.use_cases ?? []).map((u) => (
            <option key={u} value={u}>{u}</option>
          ))}
        </select>
        <select aria-label="Filter benchmarks by status" value={status} onChange={(e) => setStatus(e.target.value)}>
          <option value="">Default (hides rejected)</option>
          <option value="published">Published only</option>
          <option value="pending_review">Pending review only</option>
          <option value="rejected">Rejected only</option>
        </select>
        </div>
      </section>

      <section className="card" aria-labelledby="benchmark-table-heading">
        <h2 id="benchmark-table-heading" className="sr-only">Benchmark records</h2>
        {loading ? <div className="browse-state" role="status">Loading benchmark records.</div> : (
          <div className="table-scroll"><table>
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
          </table></div>
        )}
      </section>
    </main>
  );
}
