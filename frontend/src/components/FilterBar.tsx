import { useMemo } from "react";
import { Select } from "@/components/ui/select";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { SEVERITIES, type ReviewRow, type Severity } from "@/lib/api";
import { Filter, X } from "lucide-react";

export interface Filters {
  author: string; // "" = all
  repo: string; // "" = all
  severity: Severity | ""; // "" = all; matches reviews containing >=1 of this
  file: string; // substring match on touched file paths
}

export const EMPTY_FILTERS: Filters = { author: "", repo: "", severity: "", file: "" };

/** Apply the active filters to the reviews list. */
export function applyFilters(reviews: ReviewRow[], f: Filters): ReviewRow[] {
  const file = f.file.trim().toLowerCase();
  return reviews.filter((r) => {
    if (f.author && r.author !== f.author) return false;
    if (f.repo && r.repo !== f.repo) return false;
    if (f.severity && (r.summary[f.severity] ?? 0) === 0) return false;
    if (file && !r.files.some((p) => p.toLowerCase().includes(file))) return false;
    return true;
  });
}

export function FilterBar({
  reviews,
  filters,
  onChange,
  shown,
  total,
}: {
  reviews: ReviewRow[];
  filters: Filters;
  onChange: (next: Filters) => void;
  shown: number;
  total: number;
}) {
  const authors = useMemo(
    () => [...new Set(reviews.map((r) => r.author).filter(Boolean))].sort(),
    [reviews]
  );
  const repos = useMemo(
    () => [...new Set(reviews.map((r) => r.repo).filter(Boolean))].sort(),
    [reviews]
  );

  const active =
    filters.author || filters.repo || filters.severity || filters.file.trim();

  return (
    <div className="flex flex-wrap items-center gap-2">
      <span className="text-muted-foreground inline-flex items-center gap-1.5 text-sm">
        <Filter className="size-4" /> Filters
      </span>

      <Select
        value={filters.author}
        onChange={(e) => onChange({ ...filters, author: e.target.value })}
        aria-label="Filter by author"
      >
        <option value="">All authors</option>
        {authors.map((a) => (
          <option key={a} value={a}>
            {a}
          </option>
        ))}
      </Select>

      <Select
        value={filters.repo}
        onChange={(e) => onChange({ ...filters, repo: e.target.value })}
        aria-label="Filter by repository"
      >
        <option value="">All repos</option>
        {repos.map((r) => (
          <option key={r} value={r}>
            {r}
          </option>
        ))}
      </Select>

      <Select
        value={filters.severity}
        onChange={(e) =>
          onChange({ ...filters, severity: e.target.value as Severity | "" })
        }
        aria-label="Filter by severity"
      >
        <option value="">Any severity</option>
        {SEVERITIES.map((s) => (
          <option key={s} value={s}>
            Has {s}
          </option>
        ))}
      </Select>

      <Input
        value={filters.file}
        onChange={(e) => onChange({ ...filters, file: e.target.value })}
        placeholder="Filter by file…"
        className="w-44"
        aria-label="Filter by file path"
      />

      {active ? (
        <Button variant="ghost" size="sm" onClick={() => onChange(EMPTY_FILTERS)}>
          <X /> Clear
        </Button>
      ) : null}

      <span className="text-muted-foreground ml-auto text-xs">
        Showing {shown} of {total}
      </span>
    </div>
  );
}
