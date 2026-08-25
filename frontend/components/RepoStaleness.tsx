import { RepoStat } from "../lib/api";

/**
 * Phase 5: staleness badge for a repo_stats row, using the Phase 4 data
 * (activity_status/is_archived/days_since_last_activity) that the
 * roadmap's own 2026-07-26 note flagged as "not currently exposed
 * anywhere in the frontend or export layer yet."
 *
 * Built from is_archived and days_since_last_activity specifically
 * (both unambiguous boolean/numeric columns on RepoStat) rather than
 * re-deriving thresholds from the raw activity_status string, since
 * this session never verified github_scrapper.py's/hf_scrapper.py's
 * exact activity_status value set. The raw activity_status string is
 * still displayed alongside this badge, not replaced by it.
 */
export function computeStaleness(stat: RepoStat): { label: string; background: string; color: string } {
  if (stat.is_archived) {
    return { label: "Archived", background: "#fee2e2", color: "#991b1b" };
  }
  if (stat.days_since_last_activity == null) {
    return { label: "Unknown", background: "#e5e5e5", color: "#444" };
  }
  if (stat.days_since_last_activity <= 90) {
    return { label: "Active", background: "#dcfce7", color: "#166534" };
  }
  if (stat.days_since_last_activity <= 365) {
    return { label: "Moderate", background: "#fef3c7", color: "#92400e" };
  }
  return { label: "Stale", background: "#fee2e2", color: "#991b1b" };
}

export default function StalenessBadge({ stat }: { stat: RepoStat }) {
  const { label, background, color } = computeStaleness(stat);
  return (
    <span className="badge" style={{ background, color }}>
      {label}
    </span>
  );
}
