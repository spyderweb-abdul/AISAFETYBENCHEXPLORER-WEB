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
  listVocabTerms,
} from "../../lib/api";
import ComplexityBadge from "../../components/ComplexityBadge";

function RepositoryLink({
  url,
  label,
}: {
  url: string | null;
  label: string;
}) {
  if (!url) {
    return (
      <span
        className="browse-link-unavailable"
        aria-label={`No ${label.toLowerCase()} available`}
        title={`No ${label.toLowerCase()} available`}
      >
        x
      </span>
    );
  }

  return (
    <a
      className="browse-repository-link"
      href={url}
      target="_blank"
      rel="noreferrer"
      aria-label={`Open ${label}`}
      title={`Open ${label}`}
    >
      <svg
        aria-hidden="true"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <path d="M10 13a5 5 0 0 0 7.07.07l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71" />
        <path d="M14 11a5 5 0 0 0-7.07-.07l-3 3A5 5 0 0 0 11 21l1.71-1.71" />
      </svg>
    </a>
  );
}

export default function BrowsePage() {
  const [benchmarks, setBenchmarks] = useState<Benchmark[]>([]);
  const [vocab, setVocab] = useState<Vocab | null>(null);
  const [taskTypeOptions, setTaskTypeOptions] = useState<string[]>([]);
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
      const params: Record<string, string | number> = {
        status: "published",
        limit: 200,
      };

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
    listVocabTerms({ category: "task_type", active_only: true })
      .then((terms) => {
        setTaskTypeOptions(
          terms.map((term) => term.term).sort((a, b) => a.localeCompare(b)),
        );
      })
      .catch(() => setTaskTypeOptions([]));
  }, []);

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    search,
    taskType,
    useCase,
    complexity,
    license,
    languageSupport,
    releaseDateFrom,
    releaseDateTo,
  ]);

  return (
    <div className="container browse-container">
      <div className="topbar">
        <h1 style={{ margin: 0 }}>AISafetyBenchExplorer - Browse Benchmarks</h1>
        <div style={{ display: "flex", gap: 8 }}>
          <Link href="/browse/heatmap">
            <button className="secondary">View Research Gap Heatmap</button>
          </Link>
        </div>
      </div>

      <p
        style={{
          color: "#666",
          fontSize: 13,
          marginTop: -8,
          marginBottom: 20,
        }}
      >
        {benchmarks.length} published benchmark
        {benchmarks.length === 1 ? "" : "s"} shown.
      </p>

      <div className="card" style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
        <input
          placeholder="Search by name..."
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          style={{ minWidth: 200 }}
        />

        <select value={taskType} onChange={(event) => setTaskType(event.target.value)}>
          <option value="">All task types</option>
          {taskTypeOptions.map((term) => (
            <option key={term} value={term}>
              {term}
            </option>
          ))}
        </select>

        <select value={useCase} onChange={(event) => setUseCase(event.target.value)}>
          <option value="">All use cases</option>
          {(vocab?.use_cases ?? []).map((item) => (
            <option key={item} value={item}>
              {item}
            </option>
          ))}
        </select>

        <select
          value={complexity}
          onChange={(event) => setComplexity(event.target.value)}
        >
          <option value="">All complexity levels</option>
          {(vocab?.complexity_level ?? [
            "Popular",
            "High",
            "Medium",
            "Low",
            "Unknown",
          ]).map((item) => (
            <option key={item} value={item}>
              {item}
            </option>
          ))}
        </select>

        <select
          value={languageSupport}
          onChange={(event) => setLanguageSupport(event.target.value)}
        >
          <option value="">All languages</option>
          {(vocab?.language_support ?? []).map((item) => (
            <option key={item} value={item}>
              {item}
            </option>
          ))}
        </select>

        <input
          placeholder="Filter by license..."
          value={license}
          onChange={(event) => setLicense(event.target.value)}
          style={{ minWidth: 160 }}
        />

        <label
          style={{
            display: "flex",
            alignItems: "center",
            gap: 6,
            fontSize: 13,
            color: "#666",
          }}
        >
          Released from
          <input
            type="date"
            value={releaseDateFrom}
            onChange={(event) => setReleaseDateFrom(event.target.value)}
          />
        </label>

        <label
          style={{
            display: "flex",
            alignItems: "center",
            gap: 6,
            fontSize: 13,
            color: "#666",
          }}
        >
          to
          <input
            type="date"
            value={releaseDateTo}
            onChange={(event) => setReleaseDateTo(event.target.value)}
          />
        </label>
      </div>

      <div className="card" style={{ display: "flex", gap: 12, alignItems: "center" }}>
        <span style={{ fontSize: 13, color: "#666" }}>
          Export published benchmarks:
        </span>
        <a href={exportPublicXlsxUrl()}>
          <button className="secondary">Download Excel (.xlsx)</button>
        </a>
        <a href={exportPublicCsvUrl()}>
          <button className="secondary">Download CSV</button>
        </a>
      </div>

      <div className="card browse-table-card">
        {loading ? (
          <p>Loading...</p>
        ) : error ? (
          <p className="error">{error}</p>
        ) : benchmarks.length === 0 ? (
          <p style={{ color: "#666" }}>No benchmarks match these filters.</p>
        ) : (
          <div className="browse-table-scroll">
            <table className="browse-table">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Task Type</th>
                  <th>Use Case</th>
                  <th>Complexity</th>
                  <th>Release Date</th>
                  <th>Code</th>
                  <th>Dataset</th>
                  <th>No. of Samples</th>
                  <th>Created By</th>
                  <th>Entry Modalities</th>
                  <th>Dev Purpose</th>
                  <th>Evaluation Metrics</th>
                  <th>Language Support</th>
                  <th>Integration Option</th>
                  <th>License</th>
                  <th>Cited By</th>
                </tr>
              </thead>

              <tbody>
                {benchmarks.map((benchmark) => (
                  <tr key={benchmark.id}>
                    <td className="browse-name-cell">
                      <Link href={`/browse/${benchmark.id}`}>
                        {benchmark.benchmark_name}
                      </Link>
                    </td>
                    <td>{benchmark.task_type.join(", ") || "-"}</td>
                    <td>{benchmark.use_cases?.join(", ") || "-"}</td>
                    <td>
                      <ComplexityBadge
                        level={benchmark.complexity_level}
                        justification={benchmark.complexity_justification}
                      />
                    </td>
                    <td>{benchmark.release_date ?? "-"}</td>
                    <td>
                      <RepositoryLink
                        url={benchmark.code_repository}
                        label={`${benchmark.benchmark_name} code repository`}
                      />
                    </td>
                    <td>
                      <RepositoryLink
                        url={benchmark.dataset_repository}
                        label={`${benchmark.benchmark_name} dataset repository`}
                      />
                    </td>
                    <td>{benchmark.no_of_samples ?? "-"}</td>
                    <td>{benchmark.created_by ?? "-"}</td>
                    <td>{benchmark.entry_modalities.join(", ") || "-"}</td>
                    <td>{benchmark.dev_purpose ?? "-"}</td>
                    <td>{benchmark.evaluation_metrics.join(", ") || "-"}</td>
                    <td>{benchmark.language_support.join(", ") || "-"}</td>
                    <td>{benchmark.integration_option ?? "-"}</td>
                    <td>{benchmark.license ?? "-"}</td>
                    <td>{benchmark.cited_by}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}