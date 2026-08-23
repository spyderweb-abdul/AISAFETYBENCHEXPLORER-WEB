"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { Benchmark, getBenchmark } from "../../../../lib/api";
import BenchmarkForm from "../../../../components/BenchmarkForm";
import EvalMetricsPanel from "../../../../components/EvalMetricsPanel";
import RepoStatsPanel from "../../../../components/RepoStatsPanel";
import ReviewPanel from "../../../../components/ReviewPanel";

export default function EditBenchmarkPage() {
  const params = useParams();
  const id = params.id as string;
  const [benchmark, setBenchmark] = useState<Benchmark | null>(null);

  useEffect(() => {
    getBenchmark(id).then(setBenchmark);
  }, [id]);

  if (!benchmark) return <div className="container"><p>Loading...</p></div>;

  return (
    <div className="container">
      <h2>Edit: {benchmark.benchmark_name}</h2>

      {/* FIX (2026-08-23): review action now lives directly on this
          page, since status was never editable via BenchmarkForm and
          the Extraction Panel's queue could miss this benchmark
          entirely (see ReviewPanel.tsx for the full explanation). */}
      <ReviewPanel benchmark={benchmark} onReviewed={setBenchmark} />

      <BenchmarkForm initial={benchmark} benchmarkId={id} />
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
    </div>
  );
}
