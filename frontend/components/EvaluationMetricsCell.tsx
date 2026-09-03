"use client";

import { useEffect, useMemo, useRef, useState } from "react";

const MAX_COLLAPSED_ROWS = 2;

interface EvaluationMetricsCellProps {
  cellKey: string;
  values?: string[] | null;
  expanded: boolean;
  onExpandedChange: (cellKey: string, expanded: boolean) => void;
}

export default function EvaluationMetricsCell({
  cellKey,
  values,
  expanded,
  onExpandedChange,
}: EvaluationMetricsCellProps) {
  const listRef = useRef<HTMLDivElement>(null);
  const [visibleCount, setVisibleCount] = useState(values?.length ?? 0);

  const metrics = useMemo(
    () => (values ?? []).map((value) => value.trim()).filter(Boolean),
    [values],
  );

  useEffect(() => {
    if (expanded || metrics.length === 0) {
      setVisibleCount(metrics.length);
      return;
    }

    const updateVisibleCount = () => {
      const list = listRef.current;
      if (!list) return;

      const items = Array.from(
        list.querySelectorAll<HTMLElement>("[data-evaluation-metric]"),
      );

      const rowStarts: number[] = [];
      let count = items.length;

      for (let index = 0; index < items.length; index += 1) {
        const rowTop = Math.round(items[index].offsetTop);

        if (!rowStarts.includes(rowTop)) {
          rowStarts.push(rowTop);
        }

        if (rowStarts.length > MAX_COLLAPSED_ROWS) {
          count = index;
          break;
        }
      }

      setVisibleCount(count);
    };

    const frame = window.requestAnimationFrame(updateVisibleCount);

    const observer =
      typeof ResizeObserver === "undefined"
        ? null
        : new ResizeObserver(updateVisibleCount);

    if (listRef.current && observer) {
      observer.observe(listRef.current);
    }

    return () => {
      window.cancelAnimationFrame(frame);
      observer?.disconnect();
    };
  }, [expanded, metrics]);

  if (metrics.length === 0) {
    return <span className="evaluation-metrics-empty">Not specified</span>;
  }

  const displayedMetrics = expanded
    ? metrics
    : metrics.slice(0, visibleCount);

  const hiddenCount = metrics.length - displayedMetrics.length;

  return (
    <div className="evaluation-metrics-cell">
      <div ref={listRef} className="evaluation-metrics-list">
        {displayedMetrics.map((metric, index) => (
          <span
            data-evaluation-metric
            className="evaluation-metric"
            key={`${metric}-${index}`}
            title={metric}
          >
            {metric}
          </span>
        ))}
      </div>

      {!expanded && hiddenCount > 0 && (
        <button
          className="evaluation-metrics-toggle"
          onClick={() => onExpandedChange(cellKey, true)}
          type="button"
        >
          +{hiddenCount} more
        </button>
      )}

      {expanded && metrics.length > 1 && (
        <button
          className="evaluation-metrics-toggle"
          onClick={() => onExpandedChange(cellKey, false)}
          type="button"
        >
          Show less
        </button>
      )}
    </div>
  );
}