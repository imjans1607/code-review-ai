import { useCallback, useEffect, useState } from "react";
import {
  api,
  type AuthorTrends,
  type ReviewDetail,
  type ReviewRow,
  type Stats,
} from "@/lib/api";
import { StatCards } from "@/components/StatCards";
import { SeverityChart } from "@/components/SeverityChart";
import { TrendChart } from "@/components/TrendChart";
import { AuthorTrendChart } from "@/components/AuthorTrendChart";
import { ApiResponseTimeChart } from "@/components/ApiResponseTimeChart";
import { FindingsAcrossRunsChart } from "@/components/FindingsAcrossRunsChart";
import { ReviewsTable } from "@/components/ReviewsTable";
import { ExportMenu } from "@/components/ExportMenu";
import { ReviewDetailPanel } from "@/components/ReviewDetailPanel";
import {
  applyFilters,
  EMPTY_FILTERS,
  FilterBar,
  type Filters,
} from "@/components/FilterBar";
import { Button } from "@/components/ui/button";
import { Moon, RefreshCw, ShieldCheck, Sun } from "lucide-react";

export default function App() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [authorTrends, setAuthorTrends] = useState<AuthorTrends | null>(null);
  const [reviews, setReviews] = useState<ReviewRow[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [detail, setDetail] = useState<ReviewDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [dark, setDark] = useState(true);
  const [filters, setFilters] = useState<Filters>(EMPTY_FILTERS);

  const filtered = applyFilters(reviews, filters);

  useEffect(() => {
    document.documentElement.classList.toggle("dark", dark);
  }, [dark]);

  const load = useCallback(async () => {
    setError(null);
    try {
      const [s, r, t] = await Promise.all([
        api.stats(),
        api.reviews(),
        api.authorTrends(),
      ]);
      setStats(s);
      setReviews(r);
      setAuthorTrends(t);
    } catch {
      setError(
        "Could not reach the backend. Start it with `uvicorn app.main:app` on port 8000."
      );
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const openReview = useCallback(async (id: number) => {
    setSelectedId(id);
    setDetailLoading(true);
    try {
      setDetail(await api.review(id));
    } finally {
      setDetailLoading(false);
    }
  }, []);

  return (
    <div className="min-h-screen">
      <header className="border-b">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
          <div className="flex items-center gap-2">
            <ShieldCheck className="size-6 text-primary" />
            <div>
              <h1 className="text-lg font-semibold leading-none">
                Automated Code Review
              </h1>
              <p className="text-muted-foreground text-xs">
                Vulnerability &amp; style feedback dashboard
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm" onClick={load}>
              <RefreshCw /> Refresh
            </Button>
            <Button
              variant="ghost"
              size="icon"
              onClick={() => setDark((d) => !d)}
              aria-label="Toggle theme"
            >
              {dark ? <Sun /> : <Moon />}
            </Button>
          </div>
        </div>
      </header>

      <main className="mx-auto flex max-w-6xl flex-col gap-6 px-6 py-6">
        {error && (
          <div className="border-destructive/40 bg-destructive/10 text-destructive rounded-lg border px-4 py-3 text-sm">
            {error}
          </div>
        )}

        {stats && <StatCards stats={stats} />}

        {stats && (
          <>
            <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
              <SeverityChart stats={stats} />
              <TrendChart stats={stats} />
            </div>
            <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
              <ApiResponseTimeChart stats={stats} />
              <FindingsAcrossRunsChart stats={stats} />
            </div>
          </>
        )}

        {stats && <AuthorTrendChart trends={authorTrends} />}

        <div className="flex flex-col gap-3">
          {reviews.length > 0 && <ExportMenu filters={filters} />}
          {reviews.length > 0 && (
            <FilterBar
              reviews={reviews}
              filters={filters}
              onChange={setFilters}
              shown={filtered.length}
              total={reviews.length}
            />
          )}
          <ReviewsTable
            reviews={filtered}
            selectedId={selectedId}
            onSelect={openReview}
          />
        </div>

        <ReviewDetailPanel
          detail={detail}
          loading={detailLoading}
          onClose={() => {
            setDetail(null);
            setSelectedId(null);
          }}
        />
      </main>
    </div>
  );
}
