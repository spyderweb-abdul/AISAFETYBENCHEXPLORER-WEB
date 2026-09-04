"use client";

import { useEffect, useMemo, useState } from "react";
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
import MetadataTags, { MetadataTag,} from "../../components/MetadataTags";


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
        Not available
      </span>
    );
  }

  return (
    <a
      className="browse-repository-link"
      href={url}
      target="_blank"
      rel="noreferrer"
      aria-label={`Open ${label} in a new tab`}
      title={`Open ${label} in a new tab`}
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
      <span className="sr-only">{label}</span>
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

  const [expandedTagCells, setExpandedTagCells] = useState<Record<string, boolean>>({});

  const hasActiveFilters = useMemo(
    () =>
      Boolean(
        search ||
          taskType ||
          useCase ||
          complexity ||
          license ||
          languageSupport ||
          releaseDateFrom ||
          releaseDateTo,
      ),
    [
      complexity,
      languageSupport,
      license,
      releaseDateFrom,
      releaseDateTo,
      search,
      taskType,
      useCase,
    ],
  );

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
      setError("The benchmark catalogue could not be loaded.");
    } finally {
      setLoading(false);
    }
  }

  function clearFilters() {
    setSearch("");
    setTaskType("");
    setUseCase("");
    setComplexity("");
    setLicense("");
    setLanguageSupport("");
    setReleaseDateFrom("");
    setReleaseDateTo("");
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

  function handleExpandedTagCell(cellKey: string, expanded: boolean) {
    setExpandedTagCells((current) => ({
      ...current,
      [cellKey]: expanded,
    }));
  }

  return (
    <main className="container browse-container">
      <header className="browse-page-header">
        <div>
          <p className="eyebrow">Public catalogue</p>
          <h1>AISafetyBenchExplorer</h1>
          <p className="browse-page-description">
            Explore published AI safety evaluation benchmarks and their metadata.
          </p>
        </div>

        <Link className="button secondary browse-heatmap-link" href="/browse/heatmap">
          View research gap heatmap
        </Link>
      </header>

      <section className="browse-filter-panel" aria-labelledby="browse-filters-heading">
        <div className="browse-section-heading">
          <div>
            <h2 id="browse-filters-heading">Filter benchmarks</h2>
            <p>Results update as filters change.</p>
          </div>

          {hasActiveFilters && (
            <button className="text-button" type="button" onClick={clearFilters}>
              Clear all filters
            </button>
          )}
        </div>

        <div className="browse-filter-grid">
          <label className="browse-filter browse-filter-search">
            <span>Search</span>
            <input
              placeholder="Benchmark name"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
            />
          </label>

          <label className="browse-filter">
            <span>Task type</span>
            <select value={taskType} onChange={(event) => setTaskType(event.target.value)}>
              <option value="">All task types</option>
              {taskTypeOptions.map((term) => (
                <option key={term} value={term}>
                  {term}
                </option>
              ))}
            </select>
          </label>

          <label className="browse-filter">
            <span>Use case</span>
            <select value={useCase} onChange={(event) => setUseCase(event.target.value)}>
              <option value="">All use cases</option>
              {(vocab?.use_cases ?? []).map((item) => (
                <option key={item} value={item}>
                  {item}
                </option>
              ))}
            </select>
          </label>

          <label className="browse-filter">
            <span>Complexity level</span>
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
          </label>

          <label className="browse-filter">
            <span>Language support</span>
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
          </label>

          <label className="browse-filter">
            <span>License</span>
            <input
              placeholder="License name"
              value={license}
              onChange={(event) => setLicense(event.target.value)}
            />
          </label>

          <label className="browse-filter">
            <span>Released from</span>
            <input
              type="date"
              value={releaseDateFrom}
              onChange={(event) => setReleaseDateFrom(event.target.value)}
            />
          </label>

          <label className="browse-filter">
            <span>Released to</span>
            <input
              type="date"
              value={releaseDateTo}
              onChange={(event) => setReleaseDateTo(event.target.value)}
            />
          </label>
        </div>
      </section>

      <section className="browse-results-toolbar" aria-label="Catalogue actions">
        <div aria-live="polite" aria-atomic="true">
          <strong>{loading ? "Updating results" : `${benchmarks.length} benchmarks`}</strong>
          <span>
            {loading
              ? " matching the current filters."
              : hasActiveFilters
                ? " match the current filters."
                : " currently shown."}
          </span>
        </div>

        <div className="browse-export-actions">
          <span>Export published catalogue</span>
          <a className="button secondary" href={exportPublicXlsxUrl()}>
            Excel
          </a>
          <a className="button secondary" href={exportPublicCsvUrl()}>
            CSV
          </a>
        </div>
      </section>

      <section className="browse-table-card" aria-labelledby="browse-results-heading">
        <div className="browse-table-heading">
          <div>
            <h2 id="browse-results-heading">Benchmark records</h2>
            <p>Scroll horizontally to inspect all metadata fields.</p>
          </div>
        </div>

        {loading ? (
          <div className="browse-state" role="status" aria-live="polite">
            <span className="browse-loading-indicator" aria-hidden="true" />
            Loading benchmark records.
          </div>
        ) : error ? (
          <div className="browse-state browse-state-error" role="alert">
            <p>{error}</p>
            <button className="secondary" type="button" onClick={load}>
              Try again
            </button>
          </div>
        ) : benchmarks.length === 0 ? (
          <div className="browse-state">
            <p>No published benchmarks match the current filters.</p>
            {hasActiveFilters && (
              <button className="secondary" type="button" onClick={clearFilters}>
                Clear filters
              </button>
            )}
          </div>
        ) : (
          <div className="browse-table-scroll" tabIndex={0} aria-label="Benchmark results table">
            <table className="browse-table">
              <caption className="sr-only">
                Published AI safety benchmarks and their metadata
              </caption>
              <thead>
                <tr>
                  <th scope="col">Name</th>
                  <th scope="col">Task Type</th>
                  <th scope="col">Use Case</th>
                  <th scope="col">Complexity</th>
                  <th scope="col">Release Date</th>
                  <th scope="col">Code</th>
                  <th scope="col">Dataset</th>
                  <th scope="col">Created By</th>
                  <th scope="col">Entry Modalities</th>
                  <th scope="col">Dev Purpose</th>
                  <th scope="col">Evaluation Metrics</th>
                  <th scope="col">Language Support</th>
                  <th scope="col">Integration Option</th>
                  <th scope="col">License</th>
                  <th scope="col">Cited By</th>
                </tr>
              </thead>

              <tbody>
                {benchmarks.map((benchmark) => (
                  <tr key={benchmark.id}>
                    <th scope="row" className="browse-name-cell">
                      <Link href={`/browse/${benchmark.id}`}>
                        {benchmark.benchmark_name}
                      </Link>
                    </th>
                    <td>
                      <MetadataTags
                        cellKey={`${benchmark.id}-task-type`}
                        values={benchmark.task_type}
                        expanded={expandedTagCells[`${benchmark.id}-task-type`] ?? false}
                        onExpandedChange={handleExpandedTagCell}
                      />
                    </td>
                    <td>
                      <MetadataTags
                        cellKey={`${benchmark.id}-use-cases`}
                        values={benchmark.use_cases}
                        expanded={expandedTagCells[`${benchmark.id}-use-cases`] ?? false}
                        onExpandedChange={handleExpandedTagCell}
                      />
                    </td>
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
                    
                    <td> <MetadataTag value={benchmark.created_by} /></td>
                    <td>
                      <MetadataTags
                        cellKey={`${benchmark.id}-entry-modalities`}
                        values={benchmark.entry_modalities}
                        expanded={expandedTagCells[`${benchmark.id}-entry-modalities`] ?? false}
                        onExpandedChange={handleExpandedTagCell}
                      />
                    </td>
                    <td> <MetadataTag value={benchmark.dev_purpose} /></td>
                    <td>
                      <MetadataTags
                        cellKey={`${benchmark.id}-evaluation-metrics`}
                        values={benchmark.evaluation_metrics}
                        expanded={expandedTagCells[`${benchmark.id}-evaluation-metrics`] ?? false}
                        onExpandedChange={handleExpandedTagCell}
                      />
                    </td>
                    <td>
                      <MetadataTags
                        cellKey={`${benchmark.id}-language-support`}
                        values={benchmark.language_support}
                        expanded={expandedTagCells[`${benchmark.id}-language-support`] ?? false}
                        onExpandedChange={handleExpandedTagCell}
                      />
                    </td>
                    <td> <MetadataTag value={benchmark.integration_option} /></td>
                    <td> <MetadataTag value={benchmark.license} /></td>
                    <td>{benchmark.cited_by}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </main>
  );
}