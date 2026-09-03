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
import EvaluationMetricsCell from "../../components/EvaluationMetricsCell";

function displayValue(value: string | null | undefined) {
  return value?.trim() || "Not specified";
}

function formatReleaseDate(value: string | null) {
  if (!value) return "Not specified";

  const date = new Date(`${value}T00:00:00`);

  if (Number.isNaN(date.getTime())) return value;

  return new Intl.DateTimeFormat("en", {
    year: "numeric",
    month: "short",
    day: "numeric",
  }).format(date);
}

function RepositoryLink({
  href,
  label,
}: {
  href: string | null;
  label: string;
}) {
  if (!href) {
    return <span className="browse-single-line">Not specified</span>;
  }

  return (
    <a
      className="browse-repository-link"
      href={href}
      target="_blank"
      rel="noreferrer"
      title={href}
    >
      {label}
    </a>
  );
}

export default function BrowsePage() {
  const [benchmarks, setBenchmarks] = useState<Benchmark[]>([]);
  const [vocab, setVocab] = useState<Vocab | null>(null);
  const [taskTypeOptions, setTaskTypeOptions] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expandedMetricCells, setExpandedMetricCells] = useState<Set<string>>(
    () => new Set(),
  );

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

  function setMetricCellExpanded(cellKey: string, expanded: boolean) {
    setExpandedMetricCells((current) => {
      const next = new Set(current);

      if (expanded) {
        next.add(cellKey);
      } else {
        next.delete(cellKey);
      }

      return next;
    });
  }

  useEffect(() => {
    fetchVocab().then(setVocab).catch(() => setVocab(null));
  }, []);

  useEffect(() => {
    listVocabTerms({ category: "task_type", active_only: true })
      .then((terms) =>
        setTaskTypeOptions(
          terms
            .map((term) => term.term)
            .sort((a, b) => a.localeCompare(b)),
        ),
      )
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
    <div className="container">
      <div className="topbar">
        <h1 style={{ margin: 0 }}>
          AISafetyBenchExplorer -- Browse Benchmarks
        </h1>

        <div style={{ display: "flex", gap: 8 }}>
          <Link href="/browse/heatmap">
            <button className="secondary">
              View Research Gap Heatmap
            </button>
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

      <div
        className="card"
        style={{ display: "flex", gap: 12, flexWrap: "wrap" }}
      >
        <input
          placeholder="Search by name..."
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          style={{ minWidth: 200 }}
        />

        <select
          value={taskType}
          onChange={(event) => setTaskType(event.target.value)}
        >
          <option value="">All task types</option>
          {taskTypeOptions.map((term) => (
            <option key={term} value={term}>
              {term}
            </option>
          ))}
        </select>

        <select
          value={useCase}
          onChange={(event) => setUseCase(event.target.value)}
        >
          <option value="">All use cases</option>
          {(vocab?.use_cases ?? []).map((term) => (
            <option key={term} value={term}>
              {term}
            </option>
          ))}
        </select>

        <select
          value={complexity}
          onChange={(event) => setComplexity(event.target.value)}
        >
          <option value="">All complexity levels</option>
          {(
            vocab?.complexity_level ?? [
              "Popular",
              "High",
              "Medium",
              "Low",
              "Unknown",
            ]
          ).map((term) => (
            <option key={term} value={term}>
              {term}
            </option>
          ))}
        </select>

        <select
          value={languageSupport}
          onChange={(event) => setLanguageSupport(event.target.value)}
        >
          <option value="">All languages</option>
          {(vocab?.language_support ?? []).map((term) => (
            <option key={term} value={term}>
              {term}
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

      <div
        className="card"
        style={{ display: "flex", gap: 12, alignItems: "center" }}
      >
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
          <p style={{ color: "#666" }}>
            No benchmarks match these filters.
          </p>
        ) : (
          <div className="browse-table-scroll">
            <table className="browse-table">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Task Type</th>
                  <th>Use Case</th>
                  <th>Complexity</th>
                  <th>License</th>
                  <th>Release Date</th>
                  <th>Code</th>
                  <th>Code Repository</th>
                  <th>Dataset Repository</th>
                  <th>Evaluation Metrics</th>
                  <th>Cited By</th>
                </tr>
              </thead>

              <tbody>
                {benchmarks.map((benchmark) => {
                  const metricCellKey = `${benchmark.id}:evaluation_metrics`;

                  return (
                    <tr key={benchmark.id}>
                      <td className="browse-name-cell">
                        <Link href={`/browse/${benchmark.id}`}>
                          {benchmark.benchmark_name}
                        </Link>
                      </td>

                      <td
                        className="browse-single-line"
                        title={benchmark.task_type.join(", ")}
                      >
                        {benchmark.task_type.join(", ") || "Not specified"}
                      </td>

                      <td
                        className="browse-single-line"
                        title={benchmark.use_cases.join(", ")}
                      >
                        {benchmark.use_cases.join(", ") || "Not specified"}
                      </td>

                      <td>
                        <ComplexityBadge
                          level={benchmark.complexity_level}
                          justification={benchmark.complexity_justification}
                        />
                      </td>

                      <td
                        className="browse-single-line"
                        title={displayValue(benchmark.license)}
                      >
                        {displayValue(benchmark.license)}
                      </td>

                      <td className="browse-single-line">
                        {formatReleaseDate(benchmark.release_date)}
                      </td>

                      <td className="browse-single-line">
                        {benchmark.code_dataset}
                      </td>

                      <td>
                        <RepositoryLink
                          href={benchmark.code_repository}
                          label="Code repository"
                        />
                      </td>

                      <td>
                        <RepositoryLink
                          href={benchmark.dataset_repository}
                          label="Dataset repository"
                        />
                      </td>

                      <td className="evaluation-metrics-column">
                        <EvaluationMetricsCell
                          cellKey={metricCellKey}
                          values={benchmark.evaluation_metrics}
                          expanded={expandedMetricCells.has(metricCellKey)}
                          onExpandedChange={setMetricCellExpanded}
                        />
                      </td>

                      <td className="browse-citations-cell">
                        {benchmark.cited_by}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}