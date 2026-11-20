// Shared helpers for the per-run dashboard charts.

export interface RunPoint {
  reviewId: number;
  prNumber: number;
  coldStart: boolean;
}

/** Tooltip title: "Run R12 (PR #3)", flagged when the run included model load. */
export function runTooltipLabel(point: RunPoint | undefined): string {
  if (!point) return "";
  const base = point.prNumber
    ? `Run R${point.reviewId} (PR #${point.prNumber})`
    : `Run R${point.reviewId}`;
  return point.coldStart ? `${base} · includes model load` : base;
}
