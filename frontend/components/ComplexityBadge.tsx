// Destination path: frontend/components/ComplexityBadge.tsx
// Replaces the existing file in full.
//
// CHANGE (2026-09-02): accepts an optional justification prop and
// renders it as a native title tooltip, so hovering the badge anywhere
// it's used (admin benchmarks list, /browse, benchmark detail pages)
// shows the actual reason a benchmark was classified Popular/High/
// Medium/Low -- previously this component only ever rendered the bare
// level string with no way to surface complexity_justification at all.
//
// Existing callers that only pass level continue to work unchanged
// (justification is optional); update call sites to
// <ComplexityBadge level={b.complexity_level} justification={b.complexity_justification} />
// wherever the justification should be visible on hover.

export default function ComplexityBadge({
  level,
  justification,
}: {
  level: string;
  justification?: string | null;
}) {
  const cls = `badge complexity-badge badge-${level.toLowerCase()}`;
  return (
    <span className={cls} title={justification || undefined}>
      {level}
    </span>
  );
}
