import { useMemo } from "react";
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import type { AuthorTrend, AuthorTrends } from "@/lib/api";
import { Minus, TrendingDown, TrendingUp } from "lucide-react";

const LINE_COLORS = [
  "var(--chart-1)",
  "var(--chart-2)",
  "var(--chart-3)",
  "var(--chart-4)",
  "var(--chart-5)",
];
const CHART_AUTHORS = LINE_COLORS.length;

function TrendCell({ a }: { a: AuthorTrend }) {
  switch (a.direction) {
    case "improving":
      return (
        <span className="inline-flex items-center gap-1 text-emerald-500">
          <TrendingDown className="size-4" /> Improving
          {a.change_pct != null && ` (${a.change_pct}%)`}
        </span>
      );
    case "worsening":
      return (
        <span className="inline-flex items-center gap-1 text-red-500">
          <TrendingUp className="size-4" /> Worsening
          {a.change_pct != null && ` (+${a.change_pct}%)`}
        </span>
      );
    case "steady":
      return (
        <span className="text-muted-foreground inline-flex items-center gap-1">
          <Minus className="size-4" /> Steady
        </span>
      );
    default:
      return <span className="text-muted-foreground">Not enough reviews</span>;
  }
}

export function AuthorTrendChart({ trends }: { trends: AuthorTrends | null }) {
  const plotted = useMemo(
    () => (trends?.authors ?? []).slice(0, CHART_AUTHORS),
    [trends]
  );

  // One row per date, one column per author (undefined where they had no review).
  const data = useMemo(() => {
    const byDate = new Map<string, Record<string, number | string>>();
    for (const a of plotted) {
      for (const p of a.series) {
        const row = byDate.get(p.date) ?? { date: p.date };
        row[a.author] = p.avg_findings;
        byDate.set(p.date, row);
      }
    }
    return [...byDate.values()].sort((x, y) => String(x.date).localeCompare(String(y.date)));
  }, [plotted]);

  const hasData = (trends?.authors.length ?? 0) > 0;

  return (
    <Card>
      <CardHeader>
        <CardTitle>Developer improvement trend</CardTitle>
        <CardDescription>
          Average findings per review, by author, over the last{" "}
          {trends?.days ?? 30} days. Lower is better.
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-5">
        {!trends ? (
          <p className="text-muted-foreground text-sm">Trend data is unavailable.</p>
        ) : !hasData ? (
          <p className="text-muted-foreground text-sm">
            No reviews with an author in this period. Reviews run by CI record the PR
            author automatically.
          </p>
        ) : (
          <>
            <ResponsiveContainer width="100%" height={260}>
              <LineChart data={data} margin={{ top: 8, right: 8, left: -16, bottom: 0 }}>
                <CartesianGrid stroke="var(--border)" vertical={false} />
                <XAxis
                  dataKey="date"
                  tickFormatter={(d: string) => d.slice(5)}
                  tick={{ fontSize: 12, fill: "var(--muted-foreground)" }}
                  tickLine={false}
                  axisLine={false}
                  minTickGap={16}
                />
                <YAxis
                  tick={{ fontSize: 12, fill: "var(--muted-foreground)" }}
                  tickLine={false}
                  axisLine={false}
                />
                <Tooltip
                  contentStyle={{
                    background: "var(--popover)",
                    border: "1px solid var(--border)",
                    borderRadius: 8,
                    color: "var(--popover-foreground)",
                    fontSize: 12,
                  }}
                />
                <Legend wrapperStyle={{ fontSize: 12 }} />
                {plotted.map((a, i) => (
                  <Line
                    key={a.author}
                    type="monotone"
                    dataKey={a.author}
                    stroke={LINE_COLORS[i]}
                    strokeWidth={2}
                    dot={{ r: 3 }}
                    connectNulls
                  />
                ))}
              </LineChart>
            </ResponsiveContainer>

            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Author</TableHead>
                  <TableHead className="text-right">Reviews</TableHead>
                  <TableHead className="text-right">Findings / review</TableHead>
                  <TableHead className="text-right">Critical+High / review</TableHead>
                  <TableHead>Trend</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {trends!.authors.map((a) => (
                  <TableRow key={a.author}>
                    <TableCell className="font-medium">{a.author}</TableCell>
                    <TableCell className="text-right">{a.reviews}</TableCell>
                    <TableCell className="text-right">{a.avg_findings}</TableCell>
                    <TableCell className="text-right">{a.avg_critical_high}</TableCell>
                    <TableCell>
                      <TrendCell a={a} />
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
            <p className="text-muted-foreground text-xs">
              Trend compares an author&apos;s earlier and later reviews in this period
              (needs at least {trends!.min_reviews} reviews; changes within 10% count as
              steady). The chart shows the {CHART_AUTHORS} most active authors.
            </p>
          </>
        )}
      </CardContent>
    </Card>
  );
}
