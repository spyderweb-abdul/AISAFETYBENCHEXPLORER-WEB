// Destination path: frontend/app/admin/benchmarks/[id]/page.tsx
// Replaces the existing file in full.
//
// CHANGE (Phase 6 item 2, this session): added VersionHistoryPanel
// below RepoStatsPanel, following the exact same layout pattern as
// every other panel on this page (ReviewPanel, EvalMetricsPanel,
// RepoStatsPanel) -- a self-contained component that fetches its own
// data given the benchmarkId. No other section of this page changed.

"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { Benchmark, getBenchmark } from "../../../../lib/api";
import BenchmarkForm from "../../../../components/BenchmarkForm";
import EvalMetricsPanel from "../../../../components/EvalMetricsPanel";
import RepoStatsPanel from "../../../../components/RepoStatsPanel";
import ReviewPanel from "../../../../components/ReviewPanel";
import VersionHistoryPanel from "../../../../components/VersionHistoryPanel";
import PaperMetadataPanel from "../../../../components/PaperMetadataPanel";

export default function EditBenchmarkPage() {
  const params = useParams();
  const id = params.id as string;
  const [benchmark, setBenchmark] = useState<Benchmark | null>(null);

  useEffect(() => {
    getBenchmark(id).then(setBenchmark);
  }, [id]);

  if (!benchmark) return <main className="admin-page"><div className="browse-state" role="status">Loading benchmark record.</div></main>;

  return (
    <main className="admin-page">
      <header className="page-header">
        <div>
          <p className="eyebrow">Catalogue administration</p>
          <h1>Edit benchmark</h1>
          <p className="page-description">{benchmark.benchmark_name}</p>
        </div>
      </header>

      {/* FIX (2026-08-23): review action now lives directly on this
          page, since status was never editable via BenchmarkForm and
          the Extraction Panel's queue could miss this benchmark
          entirely (see ReviewPanel.tsx for the full explanation). */}
      <ReviewPanel benchmark={benchmark} onReviewed={setBenchmark} />

      <BenchmarkForm initial={benchmark} benchmarkId={id} />
      <PaperMetadataPanel benchmarkId={id} />
      <EvalMetricsPanel
        benchmarkId={id}
        benchmarkName={benchmark.benchmark_name}
        paperTitle={benchmark.benchmark_paper_title}
        paperLink={benchmark.paper_link}
      />
      <RepoStatsPanel
        benchmarkId={id}
        codeRepository={benchmark.code_repository}
        datasetRepository={benchmark.dataset_repository}
      />
      {/* Phase 6 item 2: full version history, read-only, reusing the
          existing audit_log table (populated since Phase 2). */}
      <VersionHistoryPanel benchmarkId={id} />
    </main>
  );
}
