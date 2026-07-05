export default function ComplexityBadge({ level }: { level: string }) {
  const cls = `badge badge-${level.toLowerCase()}`;
  return <span className={cls}>{level}</span>;
}
