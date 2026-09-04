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

import { useId, useMemo, useState } from "react";

interface Props {
  label: string;
  options: string[];
  selected: string[];
  onChange: (next: string[]) => void;
  placeholder?: string;
}

export default function TagMultiSelect({ label, options, selected, onChange, placeholder }: Props) {
  const listboxId = useId();
  const [query, setQuery] = useState("");
  const [focused, setFocused] = useState(false);
  const [hoveredOption, setHoveredOption] = useState<string | null>(null);
  const [activeOptionIndex, setActiveOptionIndex] = useState(0);

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

  function handleKeyDown(event: React.KeyboardEvent<HTMLInputElement>) {
    if (event.key === "ArrowDown" && filtered.length > 0) {
      event.preventDefault();
      setFocused(true);
      setActiveOptionIndex((current) => Math.min(current + 1, filtered.length - 1));
    }

    if (event.key === "ArrowUp" && filtered.length > 0) {
      event.preventDefault();
      setActiveOptionIndex((current) => Math.max(current - 1, 0));
    }

    if (event.key === "Enter" && focused && filtered[activeOptionIndex]) {
      event.preventDefault();
      addValue(filtered[activeOptionIndex]);
    }

    if (event.key === "Escape") {
      setFocused(false);
    }
  }

  function removeValue(value: string) {
    onChange(selected.filter((v) => v !== value));
  }

  return (
    <div className="field tag-multi-select">
      <label>{label}</label>

      {selected.length > 0 && (
        <div className="tag-multi-selected">
          {selected.map((v) => (
            <span
              key={v}
              className="tag-multi-value"
            >
              {v}
              <button
                type="button"
                onClick={() => removeValue(v)}
                aria-label={`Remove ${v}`}
                className="tag-multi-remove"
              >
                ×
              </button>
            </span>
          ))}
        </div>
      )}

      <input
        type="text"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        onFocus={() => {
          setFocused(true);
          setActiveOptionIndex(0);
        }}
        onBlur={() => setTimeout(() => setFocused(false), 150)}
        onKeyDown={handleKeyDown}
        placeholder={placeholder || `Search ${label.toLowerCase()}...`}
        role="combobox"
        aria-autocomplete="list"
        aria-expanded={focused && filtered.length > 0}
        aria-controls={listboxId}
        aria-activedescendant={focused && filtered[activeOptionIndex] ? `${listboxId}-option-${activeOptionIndex}` : undefined}
      />

      {focused && filtered.length > 0 && (
        <div
          id={listboxId}
          className="tag-multi-options"
          role="listbox"
          aria-label={`${label} suggestions`}
        >
          {filtered.map((o, index) => (
            <button
              type="button"
              id={`${listboxId}-option-${index}`}
              key={o}
              onClick={() => addValue(o)}
              onMouseEnter={() => {
                setHoveredOption(o);
                setActiveOptionIndex(index);
              }}
              onMouseLeave={() => setHoveredOption((cur) => (cur === o ? null : cur))}
              className={hoveredOption === o || activeOptionIndex === index ? "tag-multi-option tag-multi-option-active" : "tag-multi-option"}
              onMouseDown={(e) => e.preventDefault()}
              role="option"
              aria-selected={activeOptionIndex === index}
            >
              {o}
            </button>
          ))}
        </div>
      )}

      {focused && query.trim() && filtered.length === 0 && (
        <p className="tag-multi-empty">
          No match. Type an exact new value and it can still be added manually if needed elsewhere.
        </p>
      )}
    </div>
  );
}
