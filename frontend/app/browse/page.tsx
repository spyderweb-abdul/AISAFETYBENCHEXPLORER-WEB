"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { Benchmark, USE_CASE_CATEGORIES, Vocab, fetchVocab, listBenchmarks } from "../../lib/api";
import ComplexityBadge from "../../components/ComplexityBadge";

/**
 * Phase 5 browse/filter page. Updated (2026-08-23) to add a real,
 * server-side Use Case filter now that use_cases is a first-class
 * array column (app/core/use_case_classifier.py), closing the gap
 * flagged when this page first shipped -- Use Case filtering was
 * deferred entirely back then since no backend data model existed for
 * it. License and Language Support remain client-side filters (see
 * note below); Task Type, Complexity Level, Use Case, and Search are
 * all real server-side query params today.
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

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const params: Record<string, string | number> = { status: "published", limit: 200 };
      if (search) params.search = search;
      if (taskType) params.task_type = taskType;
      if (useCase) params.use_case = useCase;
      if (complexity) params.complexity_level = complexity;
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
  }, [search, taskType, useCase, complexity]);

  const filtered = useMemo(() => {
    return benchmarks.filter((b) => {
      if (license && !(b.license ?? "").toLowerCase().includes(license.toLowerCase())) return false;
      if (languageSupport && !b.language_support?.includes(languageSupport)) return false;
      return true;
    });
  }, [benchmarks, license, languageSupport]);

  return (
    <div className="container">
      <div className="topbar">
        <h1 style={{ margin: 0 }}>AISafetyBenchExplorer -- Browse Benchmarks</h1>
        <Link href="/browse/heatmap"><button className="secondary">View Research Gap Heatmap</button></Link>
      </div>
      <p style={{ color: "#666", fontSize: 13, marginTop: -8, marginBottom: 20 }}>
        {filtered.length} published benchmark{filtered.length === 1 ? "" : "s"} shown
        {benchmarks.length !== filtered.length ? ` (filtered from ${benchmarks.length} loaded)` : ""}.
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
          {USE_CASE_CATEGORIES.map((u) => (
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
      </div>

      <div className="card">
        {loading ? (
          <p>Loading...</p>
        ) : error ? (
          <p className="error">{error}</p>
        ) : filtered.length === 0 ? (
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
              {filtered.map((b) => (
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
