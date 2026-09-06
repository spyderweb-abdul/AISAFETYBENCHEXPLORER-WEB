"use client";

import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";
import {
  CatalogueReportsData,
  CategoryCount,
  getCatalogueReports,
} from "../lib/api";

type CellValue = number | string | null;
type ChartKind = "bar" | "line" | "stacked" | "grouped";

interface ReportRow {
  key: string;
  label: string;
  cells: Record<string, CellValue>;
  chartValues: Record<string, number>;
  href?: string;
  color?: string;
}

interface ReportColumn {
  key: string;
  label: string;
  format?: "number" | "percent" | "signed-percent";
}

interface ChartSeries {
  key: string;
  label: string;
  color: string;
}

interface ReportDefinition {
  id: string;
  title: string;
  description: string;
  note?: string;
  firstColumnLabel: string;
  columns: ReportColumn[];
  rows: ReportRow[];
  chartKind: ChartKind;
  series: ChartSeries[];
}

const COUNT_SERIES: ChartSeries[] = [
  { key: "count", label: "Benchmarks", color: "#24796d" },
];

const COMPLEXITY_COLORS: Record<string, string> = {
  Popular: "#2f7d54",
  High: "#9a4b43",
  Medium: "#8a641f",
  Low: "#426e9c",
  Unknown: "#6f7c7a",
};

function categoryRows(rows: CategoryCount[]): ReportRow[] {
  return rows.map((row) => ({
    key: row.label,
    label: row.label,
    cells: { count: row.count, share: row.share_percent },
    chartValues: { count: row.count },
  }));
}

function useContainerWidth() {
  const ref = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(720);

  useEffect(() => {
    const element = ref.current;
    if (!element) return;
    const update = () => setWidth(Math.max(320, Math.floor(element.clientWidth)));
    update();
    const observer = new ResizeObserver(update);
    observer.observe(element);
    return () => observer.disconnect();
  }, []);

  return { ref, width };
}

function shortLabel(label: string, limit = 25) {
  return label.length > limit ? `${label.slice(0, limit - 1)}...` : label;
}

function tickValues(maximum: number) {
  const max = Math.max(maximum, 1);
  return Array.from(
    new Set([0, 0.25, 0.5, 0.75, 1].map((step) => Math.round(max * step))),
  );
}

function HorizontalChart({
  report,
  visibleSeries,
}: {
  report: ReportDefinition;
  visibleSeries: ChartSeries[];
}) {
  const { ref, width } = useContainerWidth();
  const labelWidth = Math.min(190, Math.max(112, width * 0.26));
  const right = 42;
  const top = 34;
  const bottom = 34;
  const rowHeight = report.chartKind === "grouped" ? 43 : 34;
  const height = Math.max(230, top + bottom + report.rows.length * rowHeight);
  const plotWidth = Math.max(width - labelWidth - right, 100);
  const maximum = Math.max(
    1,
    ...report.rows.map((row) =>
      report.chartKind === "stacked"
        ? visibleSeries.reduce((sum, series) => sum + (row.chartValues[series.key] || 0), 0)
        : Math.max(...visibleSeries.map((series) => row.chartValues[series.key] || 0), 0),
    ),
  );
  const ticks = tickValues(maximum);

  return (
    <div ref={ref} className="catalogue-chart-frame">
      <svg
        className="catalogue-chart"
        viewBox={`0 0 ${width} ${height}`}
        role="img"
        aria-labelledby={`chart-${report.id}-title chart-${report.id}-description`}
      >
        <title id={`chart-${report.id}-title`}>{report.title}</title>
        <desc id={`chart-${report.id}-description`}>
          {report.description} Exact values are also available in the adjacent data table.
        </desc>
        <text
          className="catalogue-chart-axis-title"
          x={labelWidth + plotWidth}
          y="15"
          textAnchor="end"
        >
          Benchmarks
        </text>

        {ticks.map((tick, index) => {
          const x = labelWidth + (tick / maximum) * plotWidth;
          return (
            <g key={`${tick}-${index}`}>
              <line className="catalogue-chart-grid" x1={x} x2={x} y1={top - 8} y2={height - bottom} />
              <text className="catalogue-chart-axis-label" x={x} y={height - 8} textAnchor="middle">
                {tick.toLocaleString()}
              </text>
            </g>
          );
        })}

        {report.rows.map((row, rowIndex) => {
          const rowY = top + rowIndex * rowHeight;
          let stackedX = labelWidth;
          return (
            <g key={row.key}>
              <text className="catalogue-chart-category" x={labelWidth - 10} y={rowY + rowHeight / 2 + 4} textAnchor="end">
                <title>{row.label}</title>
                {shortLabel(row.label, width < 520 ? 17 : 27)}
              </text>
              {visibleSeries.map((series, seriesIndex) => {
                const value = row.chartValues[series.key] || 0;
                const barWidth = (value / maximum) * plotWidth;
                const groupedHeight = Math.max(8, (rowHeight - 10) / Math.max(visibleSeries.length, 1));
                const y = report.chartKind === "grouped"
                  ? rowY + 4 + seriesIndex * groupedHeight
                  : rowY + 8;
                const barHeight = report.chartKind === "grouped" ? groupedHeight - 2 : rowHeight - 16;
                const x = report.chartKind === "stacked" ? stackedX : labelWidth;
                if (report.chartKind === "stacked") stackedX += barWidth;
                return (
                  <rect
                    key={series.key}
                    className="catalogue-chart-mark"
                    x={x}
                    y={y}
                    width={Math.max(barWidth, value > 0 ? 1 : 0)}
                    height={barHeight}
                    fill={visibleSeries.length === 1 && row.color ? row.color : series.color}
                    tabIndex={0}
                    aria-label={`${row.label}, ${series.label}: ${value.toLocaleString()}`}
                  >
                    <title>{`${row.label} - ${series.label}: ${value.toLocaleString()}`}</title>
                  </rect>
                );
              })}
            </g>
          );
        })}
      </svg>
    </div>
  );
}

function LineChart({ report }: { report: ReportDefinition }) {
  const { ref, width } = useContainerWidth();
  const height = 320;
  const margin = { top: 24, right: 24, bottom: 58, left: 58 };
  const plotWidth = Math.max(width - margin.left - margin.right, 100);
  const plotHeight = height - margin.top - margin.bottom;
  const maximum = Math.max(1, ...report.rows.map((row) => row.chartValues.count || 0));
  const x = (index: number) => margin.left + (index / Math.max(report.rows.length - 1, 1)) * plotWidth;
  const y = (value: number) => margin.top + plotHeight - (value / maximum) * plotHeight;
  const points = report.rows.map((row, index) => `${x(index)},${y(row.chartValues.count || 0)}`).join(" ");

  return (
    <div ref={ref} className="catalogue-chart-frame">
      <svg
        className="catalogue-chart"
        viewBox={`0 0 ${width} ${height}`}
        role="img"
        aria-labelledby={`chart-${report.id}-title chart-${report.id}-description`}
      >
        <title id={`chart-${report.id}-title`}>{report.title}</title>
        <desc id={`chart-${report.id}-description`}>
          {report.description} Exact values are also available in the adjacent data table.
        </desc>
        <text
          className="catalogue-chart-axis-title"
          x="16"
          y={margin.top + plotHeight / 2}
          textAnchor="middle"
          transform={`rotate(-90 16 ${margin.top + plotHeight / 2})`}
        >
          Benchmarks
        </text>
        <text
          className="catalogue-chart-axis-title"
          x={margin.left + plotWidth / 2}
          y={height - 7}
          textAnchor="middle"
        >
          Release year
        </text>
        {tickValues(maximum).map((tick, index) => (
          <g key={`${tick}-${index}`}>
            <line className="catalogue-chart-grid" x1={margin.left} x2={width - margin.right} y1={y(tick)} y2={y(tick)} />
            <text className="catalogue-chart-axis-label" x={margin.left - 8} y={y(tick) + 4} textAnchor="end">
              {tick.toLocaleString()}
            </text>
          </g>
        ))}
        {report.rows.length > 1 && (
          <polyline className="catalogue-chart-line" points={points} fill="none" stroke={COUNT_SERIES[0].color} />
        )}
        {report.rows.map((row, index) => (
          <g key={row.key}>
            <circle
              className="catalogue-chart-mark catalogue-chart-point"
              cx={x(index)}
              cy={y(row.chartValues.count || 0)}
              r="5"
              fill={COUNT_SERIES[0].color}
              tabIndex={0}
              aria-label={`${row.label}: ${(row.chartValues.count || 0).toLocaleString()} benchmarks`}
            >
              <title>{`${row.label}: ${(row.chartValues.count || 0).toLocaleString()} benchmarks`}</title>
            </circle>
            <text className="catalogue-chart-axis-label" x={x(index)} y={height - 28} textAnchor="middle">
              {row.label}
            </text>
          </g>
        ))}
      </svg>
    </div>
  );
}

function formatCell(value: CellValue, format?: ReportColumn["format"]) {
  if (value === null) return "-";
  if (typeof value !== "number") return value;
  if (format === "percent") return `${value.toFixed(1)}%`;
  if (format === "signed-percent") return `${value > 0 ? "+" : ""}${value.toFixed(1)}%`;
  return value.toLocaleString();
}

function buildReports(data: CatalogueReportsData): ReportDefinition[] {
  const currentYear = new Date().getFullYear();
  const includesCurrentYear = data.publication_trend.some((row) => row.year === currentYear);
  const publicationNote = [
    `${data.undated_benchmarks.toLocaleString()} benchmark${data.undated_benchmarks === 1 ? "" : "s"} excluded because no release date is recorded.`,
    includesCurrentYear ? `${currentYear} is a partial year.` : "",
  ].filter(Boolean).join(" ");

  const categoryReport = (
    id: string,
    title: string,
    description: string,
    firstColumnLabel: string,
    rows: CategoryCount[],
    note?: string,
  ): ReportDefinition => ({
    id,
    title,
    description,
    note,
    firstColumnLabel,
    columns: [
      { key: "count", label: "Benchmarks", format: "number" },
      { key: "share", label: "Catalogue share", format: "percent" },
    ],
    rows: categoryRows(rows),
    chartKind: "bar",
    series: COUNT_SERIES,
  });

  const complexityReport = categoryReport(
    "complexity",
    "Complexity landscape",
    "Distribution across the catalogue complexity tiers.",
    "Complexity",
    data.complexity_distribution,
  );
  complexityReport.rows = complexityReport.rows.map((row) => ({
    ...row,
    color: COMPLEXITY_COLORS[row.label] ?? COMPLEXITY_COLORS.Unknown,
  }));

  return [
    {
      id: "publication",
      title: "Publication trend",
      description: "Published benchmarks by release year.",
      note: publicationNote,
      firstColumnLabel: "Release year",
      columns: [
        { key: "count", label: "Benchmarks", format: "number" },
        { key: "change", label: "Year over year", format: "signed-percent" },
      ],
      rows: data.publication_trend.map((row) => ({
        key: String(row.year),
        label: String(row.year),
        cells: { count: row.count, change: row.year_over_year_percent },
        chartValues: { count: row.count },
      })),
      chartKind: "line",
      series: COUNT_SERIES,
    },
    complexityReport,
    {
      id: "research-gaps",
      title: "Research gap profile",
      description: "Complexity composition within each safety dimension.",
      note: "A benchmark may contribute to multiple safety dimensions.",
      firstColumnLabel: "Safety dimension",
      columns: [
        { key: "popular", label: "Popular", format: "number" },
        { key: "high", label: "High", format: "number" },
        { key: "medium", label: "Medium", format: "number" },
        { key: "low", label: "Low", format: "number" },
        { key: "severity", label: "Gap status" },
      ],
      rows: data.research_gaps.map((row) => ({
        key: row.dimension,
        label: row.dimension,
        cells: {
          popular: row.popular,
          high: row.high,
          medium: row.medium,
          low: row.low,
          severity: row.gap_severity,
        },
        chartValues: {
          popular: row.popular,
          high: row.high,
          medium: row.medium,
          low: row.low,
        },
      })),
      chartKind: "stacked",
      series: ["Popular", "High", "Medium", "Low"].map((label) => ({
        key: label.toLowerCase(),
        label,
        color: COMPLEXITY_COLORS[label],
      })),
    },
    categoryReport(
      "task-types",
      "Task type universe",
      "The 20 most represented benchmark task types.",
      "Task type",
      data.task_types,
      "A benchmark may contribute to multiple task types.",
    ),
    categoryReport(
      "metrics",
      "Evaluation metric frequency",
      "The 20 most frequently recorded evaluation metrics.",
      "Evaluation metric",
      data.evaluation_metrics,
      "A benchmark may contribute to multiple metrics.",
    ),
    {
      id: "citations",
      title: "Citation leaders",
      description: "The 15 benchmarks with the highest recorded citation counts.",
      firstColumnLabel: "Benchmark",
      columns: [
        { key: "citations", label: "Citations", format: "number" },
        { key: "complexity", label: "Complexity" },
      ],
      rows: data.citation_leaders.map((row) => ({
        key: row.benchmark_id,
        label: row.benchmark_name,
        href: `/browse/${row.benchmark_id}`,
        cells: { citations: row.citations, complexity: row.complexity_level },
        chartValues: { count: row.citations },
      })),
      chartKind: "bar",
      series: COUNT_SERIES,
    },
    {
      id: "repository-health",
      title: "Repository ecosystem health",
      description: "Latest recorded activity status for GitHub and Hugging Face sources.",
      note: "Unknown includes missing snapshots, failed lookups, and unavailable status values.",
      firstColumnLabel: "Activity status",
      columns: [
        { key: "github", label: "GitHub", format: "number" },
        { key: "huggingFace", label: "Hugging Face", format: "number" },
      ],
      rows: data.repository_health.map((row) => ({
        key: row.status,
        label: row.status,
        cells: { github: row.github, huggingFace: row.hugging_face },
        chartValues: { github: row.github, huggingFace: row.hugging_face },
      })),
      chartKind: "grouped",
      series: [
        { key: "github", label: "GitHub", color: "#24796d" },
        { key: "huggingFace", label: "Hugging Face", color: "#6b5b95" },
      ],
    },
    categoryReport(
      "github-stars",
      "GitHub star distribution",
      "Latest recorded GitHub stars grouped into interpretable bands.",
      "Star band",
      data.github_star_distribution,
      "Unknown includes benchmarks without a GitHub repository snapshot.",
    ),
    categoryReport(
      "languages",
      "Language coverage",
      "The 20 most represented language-support values.",
      "Language",
      data.language_coverage,
      "A benchmark may contribute to multiple languages.",
    ),
    categoryReport(
      "modalities",
      "Modality coverage",
      "Distribution of benchmark input modalities.",
      "Modality",
      data.modality_coverage,
      "A benchmark may contribute to multiple modalities.",
    ),
    categoryReport(
      "licenses",
      "License ecosystem",
      "The 20 most represented recorded license values.",
      "License",
      data.license_distribution,
    ),
    categoryReport(
      "creation",
      "Creation methodology",
      "How benchmark data was authored or generated.",
      "Methodology",
      data.creation_methodology,
    ),
    categoryReport(
      "development-purpose",
      "Development purpose",
      "Whether benchmarks support evaluation, training, or both.",
      "Purpose",
      data.development_purpose,
    ),
    categoryReport(
      "use-cases",
      "Use-case application map",
      "Distribution of intended benchmark applications.",
      "Use case",
      data.use_case_distribution,
      "A benchmark may contribute to multiple use cases.",
    ),
  ];
}

export default function CatalogueReports() {
  const [data, setData] = useState<CatalogueReportsData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [selectedId, setSelectedId] = useState("publication");
  const [hiddenSeries, setHiddenSeries] = useState<Set<string>>(new Set());
  const [mobileView, setMobileView] = useState<"chart" | "table">("chart");

  async function load() {
    setLoading(true);
    setError(false);
    try {
      setData(await getCatalogueReports());
    } catch {
      setError(true);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  const reports = useMemo(() => (data ? buildReports(data) : []), [data]);
  const selected = reports.find((report) => report.id === selectedId) ?? reports[0];
  const visibleSeries = selected?.series.filter((series) => !hiddenSeries.has(series.key)) ?? [];

  useEffect(() => {
    setHiddenSeries(new Set());
    setMobileView("chart");
  }, [selectedId]);

  function toggleSeries(key: string) {
    setHiddenSeries((current) => {
      const next = new Set(current);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }

  return (
    <section className="catalogue-reports" aria-labelledby="catalogue-reports-heading" aria-busy={loading}>
      <header className="catalogue-reports-header">
        <div>
          <p className="eyebrow">Live meta-analysis</p>
          <h2 id="catalogue-reports-heading">Catalogue reports</h2>
          <p>Exact data tables and responsive charts computed from every published benchmark.</p>
        </div>
        {!loading && !error && reports.length > 0 && (
          <label className="catalogue-report-picker">
            <span>Report</span>
            <select value={selected?.id} onChange={(event) => setSelectedId(event.target.value)}>
              {reports.map((report) => (
                <option key={report.id} value={report.id}>{report.title}</option>
              ))}
            </select>
          </label>
        )}
      </header>

      {loading ? (
        <div className="catalogue-report-state" role="status" aria-live="polite">
          <span className="browse-loading-indicator" aria-hidden="true" />
          Building catalogue reports.
        </div>
      ) : error ? (
        <div className="catalogue-report-state catalogue-report-state-error" role="alert">
          <p>Catalogue reports are temporarily unavailable.</p>
          <button className="secondary" type="button" onClick={load}>Try again</button>
        </div>
      ) : !selected || data?.total_benchmarks === 0 ? (
        <div className="catalogue-report-state">
          No published benchmark metadata is available for reporting.
        </div>
      ) : (
        <div className="catalogue-report-body">
          <div className="catalogue-report-intro">
            <div>
              <h3 className="sr-only">{selected.title}</h3>
              <p>{selected.description}</p>
            </div>
            <span>{data?.total_benchmarks.toLocaleString()} published records</span>
          </div>

          {selected.note && <p className="catalogue-report-note">{selected.note}</p>}

          {selected.rows.length === 0 ? (
            <div className="catalogue-report-empty" role="status">
              No recorded metadata is available for this report yet.
            </div>
          ) : (
            <>
              {selected.series.length > 1 && (
                <div className="catalogue-chart-legend" aria-label="Chart series controls">
                  {selected.series.map((series) => {
                    const visible = !hiddenSeries.has(series.key);
                    return (
                      <button
                        key={series.key}
                        type="button"
                        className="catalogue-chart-legend-button"
                        aria-pressed={visible}
                        onClick={() => toggleSeries(series.key)}
                      >
                        <span style={{ backgroundColor: visible ? series.color : "transparent", borderColor: series.color }} />
                        {series.label}
                      </button>
                    );
                  })}
                </div>
              )}

              <div className="catalogue-report-mobile-switch" aria-label="Report display">
                <button
                  type="button"
                  className="catalogue-report-view-button"
                  aria-pressed={mobileView === "chart"}
                  onClick={() => setMobileView("chart")}
                >
                  Chart
                </button>
                <button
                  type="button"
                  className="catalogue-report-view-button"
                  aria-pressed={mobileView === "table"}
                  onClick={() => setMobileView("table")}
                >
                  Data table
                </button>
              </div>

              <div className={`catalogue-report-grid catalogue-report-grid--${mobileView}`}>
                <div className="catalogue-report-table-scroll" tabIndex={0} aria-label={`${selected.title} data table`}>
                  <table className="catalogue-report-table">
                    <caption className="sr-only">{selected.title}: {selected.description}</caption>
                    <thead>
                      <tr>
                        <th scope="col">{selected.firstColumnLabel}</th>
                        {selected.columns.map((column) => <th scope="col" key={column.key}>{column.label}</th>)}
                      </tr>
                    </thead>
                    <tbody>
                      {selected.rows.map((row) => (
                        <tr key={row.key}>
                          <th scope="row">
                            {row.href ? <Link href={row.href}>{row.label}</Link> : row.label}
                          </th>
                          {selected.columns.map((column) => (
                            <td key={column.key}>{formatCell(row.cells[column.key] ?? null, column.format)}</td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                <div className="catalogue-report-chart-panel">
                  {visibleSeries.length === 0 ? (
                    <div className="catalogue-chart-empty">Select at least one series to display the chart.</div>
                  ) : selected.chartKind === "line" ? (
                    <LineChart report={selected} />
                  ) : (
                    <HorizontalChart report={selected} visibleSeries={visibleSeries} />
                  )}
                </div>
              </div>
            </>
          )}
        </div>
      )}
    </section>
  );
}
