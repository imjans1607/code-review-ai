/** Types mirroring the backend's JSON, and a tiny fetch wrapper. */

export type Severity = "Critical" | "High" | "Medium" | "Low" | "Informational";

export const SEVERITIES: Severity[] = [
  "Critical",
  "High",
  "Medium",
  "Low",
  "Informational",
];

export interface ReviewComment {
  path: string;
  line: number;
  severity: Severity;
  category: string;
  message: string;
  source: string;
  rationale: string;
  rule_id: string;
  cwe: string[];
}

export interface ReviewRow {
  id: number;
  created_at: string;
  repo: string;
  pr_number: number;
  author: string;
  commit_sha: string;
  total: number;
  files: string[];
  summary: Record<Severity, number>;
}

export interface ReviewDetail extends ReviewRow {
  report: {
    summary: Record<string, number>;
    total: number;
    comments: ReviewComment[];
    notes: string[];
  };
}

export interface Stats {
  total_reviews: number;
  total_findings: number;
  severity_totals: Record<Severity, number>;
  category_totals: Record<string, number>;
  top_rules: { rule_id: string; count: number }[];
  trend: { date: string; findings: number }[];
  run_history: {
    review_id: number;
    pr_number: number;
    created_at: string;
    response_time_ms: number | null;
    ai_findings: number | null;
    security_findings: number | null;
    fused_findings: number | null;
    cold_start: boolean;
  }[];
}

export type TrendDirection = "improving" | "worsening" | "steady" | "insufficient_data";

export interface AuthorTrend {
  author: string;
  reviews: number;
  total_findings: number;
  avg_findings: number;
  avg_critical_high: number;
  direction: TrendDirection;
  change_pct: number | null;
  series: { date: string; reviews: number; avg_findings: number }[];
}

export interface AuthorTrends {
  days: number;
  min_reviews: number;
  authors: AuthorTrend[];
}

// In dev, Vite proxies /api -> the FastAPI backend (see vite.config.ts).
const BASE = "/api";

/** URL of a downloadable export; opening it makes the browser save a file. */
export function exportUrl(opts: {
  format: "csv" | "json";
  scope?: "reviews" | "findings";
  filters?: { repo: string; author: string; severity: string; file: string };
}): string {
  const q = new URLSearchParams({ format: opts.format });
  if (opts.format === "csv") q.set("scope", opts.scope ?? "reviews");
  for (const [k, v] of Object.entries(opts.filters ?? {})) {
    if (v && v.trim()) q.set(k, v.trim());
  }
  return `${BASE}/reviews/export?${q}`;
}

/** URL to download one review (findings CSV, or the full report as JSON). */
export function reviewExportUrl(id: number, format: "csv" | "json"): string {
  return `${BASE}/reviews/${id}/export?format=${format}`;
}

async function getJSON<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`);
  if (!res.ok) throw new Error(`${path} → ${res.status}`);
  return res.json() as Promise<T>;
}

export const api = {
  stats: (days = 14) => getJSON<Stats>(`/stats?days=${days}`),
  reviews: (limit = 20) =>
    getJSON<{ reviews: ReviewRow[] }>(`/reviews?limit=${limit}`).then((d) => d.reviews),
  authorTrends: (days = 30) => getJSON<AuthorTrends>(`/stats/authors?days=${days}`),
  review: (id: number) => getJSON<ReviewDetail>(`/reviews/${id}`),
};
