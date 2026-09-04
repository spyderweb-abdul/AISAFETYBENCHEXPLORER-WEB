"use client";

import { useEffect, useMemo, useRef, useState } from "react";

const TAG_PALETTE = [
  { background: "#e0f2fe", color: "#075985" },
  { background: "#dcfce7", color: "#166534" },
  { background: "#fef3c7", color: "#92400e" },
  { background: "#fce7f3", color: "#9d174d" },
  { background: "#ede9fe", color: "#5b21b6" },
  { background: "#ccfbf1", color: "#115e59" },
  { background: "#ffedd5", color: "#9a3412" },
  { background: "#e2e8f0", color: "#334155" },
] as const;

const MAX_COLLAPSED_ROWS = 2;

function normalizeValue(value: string) {
  return value.trim().toLocaleLowerCase();
}

function hashValue(value: string) {
  let hash = 2166136261;

  for (let index = 0; index < value.length; index += 1) {
    hash ^= value.charCodeAt(index);
    hash = Math.imul(hash, 16777619);
  }

  return hash >>> 0;
}

function tagStyle(value: string) {
  const normalized = normalizeValue(value);
  const palette = TAG_PALETTE[hashValue(normalized) % TAG_PALETTE.length];

  return {
    backgroundColor: palette.background,
    color: palette.color,
  };
}

interface MetadataTagProps {
  value?: string | null;
  className?: string;
}

export function MetadataTag({ value, className = "" }: MetadataTagProps) {
  const cleanedValue = value?.trim();

  if (!cleanedValue) {
    return <span className="metadata-tags-empty">Not specified</span>;
  }

  return (
    <span
      className={`metadata-tag ${className}`.trim()}
      style={tagStyle(cleanedValue)}
      title={cleanedValue}
    >
      {cleanedValue}
    </span>
  );
}

interface MetadataTagsProps {
  cellKey: string;
  values?: string[] | null;
  expanded: boolean;
  onExpandedChange: (cellKey: string, expanded: boolean) => void;
}

export default function MetadataTags({
  cellKey,
  values,
  expanded,
  onExpandedChange,
}: MetadataTagsProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [visibleCount, setVisibleCount] = useState(values?.length ?? 0);

  const tagValues = useMemo(
    () => (values ?? []).map((value) => value.trim()).filter(Boolean),
    [values],
  );

  useEffect(() => {
    if (expanded || tagValues.length === 0) {
      setVisibleCount(tagValues.length);
      return;
    }

    const updateVisibleCount = () => {
      const container = containerRef.current;

      if (!container) return;

      const tags = Array.from(
        container.querySelectorAll<HTMLElement>("[data-metadata-tag]"),
      );

      if (tags.length === 0) return;

      const rowStarts: number[] = [];
      let count = tags.length;

      for (let index = 0; index < tags.length; index += 1) {
        const rowTop = Math.round(tags[index].offsetTop);

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

    if (containerRef.current && observer) {
      observer.observe(containerRef.current);
    }

    return () => {
      window.cancelAnimationFrame(frame);
      observer?.disconnect();
    };
  }, [expanded, tagValues]);

  if (tagValues.length === 0) {
    return <span className="metadata-tags-empty">Not specified</span>;
  }

  const displayedValues = expanded
    ? tagValues
    : tagValues.slice(0, visibleCount);

  const hiddenCount = Math.max(tagValues.length - displayedValues.length, 0);

  return (
    <div className="metadata-tags-cell">
      <div ref={containerRef} className="metadata-tags-list">
        {displayedValues.map((value, index) => (
          <span
            className="metadata-tag"
            data-metadata-tag
            key={`${value}-${index}`}
            style={tagStyle(value)}
            title={value}
          >
            {value}
          </span>
        ))}
      </div>

      {!expanded && hiddenCount > 0 && (
        <button
          className="metadata-tags-toggle"
          onClick={() => onExpandedChange(cellKey, true)}
          type="button"
        >
          +{hiddenCount} more
        </button>
      )}

      {expanded && tagValues.length > 1 && (
        <button
          className="metadata-tags-toggle"
          onClick={() => onExpandedChange(cellKey, false)}
          type="button"
        >
          Show less
        </button>
      )}
    </div>
  );
}