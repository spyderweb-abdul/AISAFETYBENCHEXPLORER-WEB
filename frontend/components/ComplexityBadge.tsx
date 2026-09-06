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
