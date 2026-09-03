"use client";

import { useEffect, useMemo, useRef, useState } from "react";

const TAG_PALETTE = [
  { background: "#e0f2fe", color: "#075985", border: "#7dd3fc" },
  { background: "#dcfce7", color: "#166534", border: "#86efac" },
  { background: "#fef3c7", color: "#92400e", border: "#fcd34d" },
  { background: "#fce7f3", color: "#9d174d", border: "#f9a8d4" },
  { background: "#ede9fe", color: "#5b21b6", border: "#c4b5fd" },
  { background: "#ccfbf1", color: "#115e59", border: "#5eead4" },
  { background: "#ffedd5", color: "#9a3412", border: "#fdba74" },
  { background: "#e2e8f0", color: "#334155", border: "#cbd5e1" },
];

const BORDER_STYLES = ["solid", "dashed", "dotted", "double"] as const;
const MAX_COLLAPSED_ROWS = 2;

function hashValue(value: string, seed = 0) {
  let hash = 2166136261 ^ seed;

  for (let index = 0; index < value.length; index += 1) {
    hash ^= value.charCodeAt(index);
    hash = Math.imul(hash, 16777619);
  }

  return hash >>> 0;
}

function getTagStyle(value: string) {
  const normalized = value.trim().toLocaleLowerCase();

  const palette =
    TAG_PALETTE[hashValue(normalized) % TAG_PALETTE.length];

  const borderStyle =
    BORDER_STYLES[
      hashValue(normalized, 97) % BORDER_STYLES.length
    ];

  return {
    backgroundColor: palette.background,
    borderColor: palette.border,
    borderStyle,
    color: palette.color,
  };
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

  const [visibleCount, setVisibleCount] = useState(
    values?.length ?? 0,
  );

  const tagValues = useMemo(
    () =>
      (values ?? [])
        .map((value) => value.trim())
        .filter(Boolean),
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
        container.querySelectorAll<HTMLElement>(
          "[data-metadata-tag]",
        ),
      );

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

  const hiddenCount = tagValues.length - displayedValues.length;

  return (
    <div className="metadata-tags-cell">
      <div ref={containerRef} className="metadata-tags-list">
        {displayedValues.map((value, index) => (
          <span
            className="metadata-tag"
            data-metadata-tag
            key={`${value}-${index}`}
            style={getTagStyle(value)}
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