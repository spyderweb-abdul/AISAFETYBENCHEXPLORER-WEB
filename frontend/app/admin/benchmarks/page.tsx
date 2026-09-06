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
// /browse page.

"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  Benchmark,
  BenchmarkPage,
  ModelOption,
  Vocab,
  deleteBenchmark,
  exportXlsxUrl,
  fetchVocab,
  listAdminBenchmarkPage,
  listModels,
  reextractBenchmark,
} from "../../../lib/api";
import ComplexityBadge from "../../../components/ComplexityBadge";

const PAGE_SIZE = 50;

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
  const [pageInfo, setPageInfo] = useState<Omit<BenchmarkPage, "items">>({ total: 0, page: 1, page_size: PAGE_SIZE, total_pages: 1 });
  const [vocab, setVocab] = useState<Vocab | null>(null);
  const [models, setModels] = useState<ModelOption[]>([]);
  const [modelsLoading, setModelsLoading] = useState(true);
  const [modelsError, setModelsError] = useState<string | null>(null);
  const [reextractModel, setReextractModel] = useState("");
  const [search, setSearch] = useState("");
  const [complexity, setComplexity] = useState("");
  const [status, setStatus] = useState("");
  const [useCase, setUseCase] = useState("");
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [reextractingId, setReextractingId] = useState<string | null>(null);

  async function load() {
    setLoading(true);
    setError(null);
    const params: Record<string, string> = {};
    if (search) params.search = search;
    if (complexity) params.complexity_level = complexity;
    if (status) params.status = status;
    if (useCase) params.use_case = useCase;
    params.page = String(page);
    params.page_size = String(PAGE_SIZE);
    try {
      const data = await listAdminBenchmarkPage(params);
      setBenchmarks(data.items);
      setPageInfo({ total: data.total, page: data.page, page_size: data.page_size, total_pages: data.total_pages });
      if (data.page !== page) setPage(data.page);
    } catch {
      setError("Failed to load benchmark records.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    fetchVocab().then(setVocab).catch(() => setVocab(null));
  }, []);

  useEffect(() => {
    listModels(true)
      .then(setModels)
      .catch(() => setModelsError("Unable to load active extraction models."))
      .finally(() => setModelsLoading(false));
  }, []);

  useEffect(() => { setPage(1); }, [search, complexity, status, useCase]);

  useEffect(() => { load(); }, [search, complexity, status, useCase, page]);

  async function handleDelete(id: string) {
    if (!confirm("Delete this benchmark record? This cannot be undone.")) return;
    try {
      await deleteBenchmark(id);
      if (benchmarks.length === 1 && page > 1) setPage((current) => current - 1);
      else await load();
    } catch {
      setError("Failed to delete benchmark.");
    }
  }

  async function handleReextract(benchmark: Benchmark) {
    if (!confirm(`Re-extract ${benchmark.benchmark_name}? The returned fields will update this existing record and move it to pending review.`)) return;
    setReextractingId(benchmark.id);
    setError(null);
    setNotice(null);
    try {
      const job = await reextractBenchmark(benchmark.id, reextractModel);
      setNotice(`Re-extraction queued (job ${job.id}). This record will update in place when processing completes.`);
    } catch (err: any) {
      setError(err?.response?.data?.detail ?? "Failed to queue re-extraction.");
    } finally {
      setReextractingId(null);
    }
  }

  return (
    <main className="admin-page">
      <header className="page-header">
        <div>
          <p className="eyebrow">Catalogue administration</p>
          <h1>Benchmarks <span className="metadata-tags-empty">{pageInfo.total}</span></h1>
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
        <label className="reextract-model-control">
          <span>Re-extraction model</span>
          <select
            aria-label="Model used for benchmark re-extraction"
            value={reextractModel}
            onChange={(e) => setReextractModel(e.target.value)}
            disabled={modelsLoading || Boolean(modelsError)}
          >
            <option value="">{modelsLoading ? "Loading models..." : "Select a model"}</option>
            {models.map((model) => (
              <option key={model.id} value={model.identifier}>
                {model.display_name ? `${model.display_name} — ${model.identifier}` : model.identifier}
              </option>
            ))}
          </select>
        </label>
        </div>
        {modelsError && <p className="error">{modelsError}</p>}
        {!modelsLoading && !modelsError && models.length === 0 && (
          <p className="muted-copy">No active extraction models are available. <Link href="/admin/models">Manage models</Link></p>
        )}
      </section>

      <section className="card" aria-labelledby="benchmark-table-heading">
        <h2 id="benchmark-table-heading" className="sr-only">Benchmark records</h2>
        {notice && <div className="notice" role="status">{notice}</div>}
        {error && <p className="error" role="alert">{error}</p>}
        {loading ? <div className="browse-state" role="status">Loading benchmark records.</div> : benchmarks.length === 0 ? (
          <div className="browse-state">No benchmark records match these filters.</div>
        ) : (
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
                  <td className="table-row-actions">
                    <button
                      className="secondary"
                      onClick={() => handleReextract(b)}
                      disabled={reextractingId === b.id || !reextractModel}
                      title={!reextractModel ? "Select a re-extraction model first" : undefined}
                    >
                      {reextractingId === b.id ? "Queuing..." : "Re-extract"}
                    </button>
                    <button className="danger" onClick={() => handleDelete(b.id)}>Delete</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table></div>
        )}
        {!loading && pageInfo.total_pages > 1 && (
          <div className="catalogue-pagination">
            <span>Page {pageInfo.page} of {pageInfo.total_pages} · {pageInfo.total} records</span>
            <div>
              <button type="button" className="secondary" disabled={pageInfo.page <= 1} onClick={() => setPage((current) => current - 1)}>Previous</button>
              <button type="button" className="secondary" disabled={pageInfo.page >= pageInfo.total_pages} onClick={() => setPage((current) => current + 1)}>Next</button>
            </div>
          </div>
        )}
      </section>
    </main>
  );
}
