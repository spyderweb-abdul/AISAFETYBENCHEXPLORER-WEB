// Destination path: frontend/app/browse/page.tsx
// Replaces the existing file in full.
//
// CHANGES in this version (Known Gap item 19 fix, this session):
// The Use Case dropdown no longer imports the hardcoded
// USE_CASE_CATEGORIES constant from lib/api.ts (removed there in this
// same session). It now reads vocab.use_cases, same as every other
// controlled-vocabulary dropdown on this page (Task Type, Complexity
// Level, Language Support) -- closing the drift risk where the
// frontend's own copy of the category list could silently diverge
// from app/core/use_case_classifier.py's real output space.
//
// This build also carries forward the earlier Phase 5 session's
// changes: License and Language Support as real server-side filters,
// a Release Date range filter, and the published-only CSV/Excel
// export section.

"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  Benchmark,
  Vocab,
  exportPublicCsvUrl,
  exportPublicXlsxUrl,
  fetchVocab,
  listBenchmarks,
} from "../../lib/api";
import ComplexityBadge from "../../components/ComplexityBadge";

/**
 * Phase 5 browse/filter page. Task Type, Complexity Level, Use Case,
 * Search, License, Language Support, and Release Date are all real
 * server-side query params against GET /benchmarks. Every
 * controlled-vocabulary dropdown (Task Type, Use Case, Complexity
 * Level, Language Support) is driven by GET /vocab -- there is no
 * hardcoded category list left in this component.
 */
export default function BrowsePage() {
  const [benchmarks, setBenchmarks] = useState<Benchmark[]>([]);
  const [vocab, setVocab] = useState<Vocab | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [search, setSearch] = useState("");
  const [taskType, setTaskType] = useState("");
  const [useCase, setUseCase] = useState("");
  const [complexity, setComplexity] = useState("");
  const [license, setLicense] = useState("");
  const [languageSupport, setLanguageSupport] = useState("");
  const [releaseDateFrom, setReleaseDateFrom] = useState("");
  const [releaseDateTo, setReleaseDateTo] = useState("");

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const params: Record<string, string | number> = { status: "published", limit: 200 };
      if (search) params.search = search;
      if (taskType) params.task_type = taskType;
      if (useCase) params.use_case = useCase;
      if (complexity) params.complexity_level = complexity;
      if (license) params.license = license;
      if (languageSupport) params.language_support = languageSupport;
      if (releaseDateFrom) params.release_date_from = releaseDateFrom;
      if (releaseDateTo) params.release_date_to = releaseDateTo;
      const data = await listBenchmarks(params);
      setBenchmarks(data);
    } catch {
      setError("Failed to load benchmarks.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    fetchVocab().then(setVocab).catch(() => setVocab(null));
  }, []);

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [search, taskType, useCase, complexity, license, languageSupport, releaseDateFrom, releaseDateTo]);

  return (
    <div className="container">
      <div className="topbar">
        <h1 style={{ margin: 0 }}>AISafetyBenchExplorer -- Browse Benchmarks</h1>
        <div style={{ display: "flex", gap: 8 }}>
          <Link href="/browse/heatmap"><button className="secondary">View Research Gap Heatmap</button></Link>
        </div>
      </div>
      <p style={{ color: "#666", fontSize: 13, marginTop: -8, marginBottom: 20 }}>
        {benchmarks.length} published benchmark{benchmarks.length === 1 ? "" : "s"} shown.
      </p>

      <div className="card" style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
        <input
          placeholder="Search by name..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          style={{ minWidth: 200 }}
        />
        <select value={taskType} onChange={(e) => setTaskType(e.target.value)}>
          <option value="">All task types</option>
          {(vocab?.task_type ?? []).map((t) => (
            <option key={t} value={t}>{t}</option>
          ))}
        </select>
        <select value={useCase} onChange={(e) => setUseCase(e.target.value)}>
          <option value="">All use cases</option>
          {(vocab?.use_cases ?? []).map((u) => (
            <option key={u} value={u}>{u}</option>
          ))}
        </select>
        <select value={complexity} onChange={(e) => setComplexity(e.target.value)}>
          <option value="">All complexity levels</option>
          {(vocab?.complexity_level ?? ["Popular", "High", "Medium", "Low", "Unknown"]).map((c) => (
            <option key={c} value={c}>{c}</option>
          ))}
        </select>
        <select value={languageSupport} onChange={(e) => setLanguageSupport(e.target.value)}>
          <option value="">All languages</option>
          {(vocab?.language_support ?? []).map((l) => (
            <option key={l} value={l}>{l}</option>
          ))}
        </select>
        <input
          placeholder="Filter by license..."
          value={license}
          onChange={(e) => setLicense(e.target.value)}
          style={{ minWidth: 160 }}
        />
        <label style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 13, color: "#666" }}>
          Released from
          <input
            type="date"
            value={releaseDateFrom}
            onChange={(e) => setReleaseDateFrom(e.target.value)}
          />
        </label>
        <label style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 13, color: "#666" }}>
          to
          <input
            type="date"
            value={releaseDateTo}
            onChange={(e) => setReleaseDateTo(e.target.value)}
          />
        </label>
      </div>

      <div className="card" style={{ display: "flex", gap: 12, alignItems: "center" }}>
        <span style={{ fontSize: 13, color: "#666" }}>Export published benchmarks:</span>
        <a href={exportPublicXlsxUrl()}><button className="secondary">Download Excel (.xlsx)</button></a>
        <a href={exportPublicCsvUrl()}><button className="secondary">Download CSV</button></a>
      </div>

      <div className="card">
        {loading ? (
          <p>Loading...</p>
        ) : error ? (
          <p className="error">{error}</p>
        ) : benchmarks.length === 0 ? (
          <p style={{ color: "#666" }}>No benchmarks match these filters.</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Name</th>
                <th>Task Type</th>
                <th>Use Case</th>
                <th>Complexity</th>
                <th>License</th>
                <th>Cited By</th>
              </tr>
            </thead>
            <tbody>
              {benchmarks.map((b) => (
                <tr key={b.id}>
                  <td><Link href={`/browse/${b.id}`}>{b.benchmark_name}</Link></td>
                  <td>{b.task_type.join(", ")}</td>
                  <td>{b.use_cases?.join(", ") || "-"}</td>
                  <td><ComplexityBadge level={b.complexity_level} /></td>
                  <td>{b.license ?? "-"}</td>
                  <td>{b.cited_by}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
