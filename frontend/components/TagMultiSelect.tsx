// Destination path: frontend/components/TagMultiSelect.tsx
// Replaces the existing file in full.
//
// FIX (2026-09-02): dropdown option text was invisible (white-on-white)
// despite being fully clickable -- confirmed by the reported symptom:
// cursor changes to a pointer on hover, and clicking an "empty" row
// correctly adds the right value as a tag. Root cause: the dropdown
// options are real <button> elements; the inline style set
// background: "white" but never set an explicit color, so each button
// inherited this app's global default button text color (white,
// matching the primary action buttons like "Save Benchmark" elsewhere
// in this app) -- white text on a white background is invisible but
// still perfectly interactive, exactly matching what was observed.
// Fixed by explicitly setting color, plus a hover background so the
// row's clickable area is visually obvious even without relying on
// any global button styling.

"use client";

import { useMemo, useState } from "react";

interface Props {
  label: string;
  options: string[];
  selected: string[];
  onChange: (next: string[]) => void;
  placeholder?: string;
}

export default function TagMultiSelect({ label, options, selected, onChange, placeholder }: Props) {
  const [query, setQuery] = useState("");
  const [focused, setFocused] = useState(false);
  const [hoveredOption, setHoveredOption] = useState<string | null>(null);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    const notSelected = options.filter((o) => !selected.includes(o));
    if (!q) return notSelected.slice(0, 20);
    return notSelected.filter((o) => o.toLowerCase().includes(q)).slice(0, 20);
  }, [options, selected, query]);

  function addValue(value: string) {
    if (!selected.includes(value)) onChange([...selected, value]);
    setQuery("");
  }

  function removeValue(value: string) {
    onChange(selected.filter((v) => v !== value));
  }

  return (
    <div className="field" style={{ position: "relative" }}>
      <label>{label}</label>

      {selected.length > 0 && (
        <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginBottom: 6 }}>
          {selected.map((v) => (
            <span
              key={v}
              style={{
                display: "inline-flex", alignItems: "center", gap: 4,
                background: "#eef2ff", color: "#3730a3", borderRadius: 999,
                padding: "2px 8px", fontSize: 12,
              }}
            >
              {v}
              <button
                type="button"
                onClick={() => removeValue(v)}
                aria-label={`Remove ${v}`}
                style={{
                  border: "none", background: "transparent", color: "#3730a3",
                  cursor: "pointer", fontSize: 12, lineHeight: 1, padding: 0,
                }}
              >
                &times;
              </button>
            </span>
          ))}
        </div>
      )}

      <input
        type="text"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        onFocus={() => setFocused(true)}
        onBlur={() => setTimeout(() => setFocused(false), 150)}
        placeholder={placeholder || `Search ${label.toLowerCase()}...`}
        style={{ fontSize: 13 }}
      />

      {focused && filtered.length > 0 && (
        <div
          style={{
            position: "absolute", zIndex: 20, top: "100%", left: 0, right: 0,
            background: "white", border: "1px solid #e5e5e5", borderRadius: 6,
            marginTop: 2, maxHeight: 220, overflowY: "auto",
            boxShadow: "0 4px 12px rgba(0,0,0,0.08)",
          }}
        >
          {filtered.map((o) => (
            <button
              type="button"
              key={o}
              onClick={() => addValue(o)}
              onMouseEnter={() => setHoveredOption(o)}
              onMouseLeave={() => setHoveredOption((cur) => (cur === o ? null : cur))}
              style={{
                display: "block", width: "100%", textAlign: "left",
                padding: "6px 10px", fontSize: 12, border: "none",
                background: hoveredOption === o ? "#f3f4f6" : "white",
                color: "#111827",
                cursor: "pointer",
              }}
              onMouseDown={(e) => e.preventDefault()}
            >
              {o}
            </button>
          ))}
        </div>
      )}

      {focused && query.trim() && filtered.length === 0 && (
        <p style={{ fontSize: 11, color: "#888", marginTop: 4 }}>
          No match. Type an exact new value and it can still be added manually if needed elsewhere.
        </p>
      )}
    </div>
  );
}
