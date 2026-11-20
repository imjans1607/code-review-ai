import {
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { Stats } from "@/lib/api";
import { runTooltipLabel, type RunPoint } from "@/lib/runs";

export function ApiResponseTimeChart({ stats }: { stats: Stats | null | undefined }) {
  const hasRunHistory = Array.isArray(stats?.run_history);
  const runHistory = hasRunHistory ? stats.run_history : [];
  const data = runHistory.map((r) => ({
    run: `R${r.review_id}`,
    reviewId: r.review_id,
    prNumber: r.pr_number,
    coldStart: r.cold_start,
    responseTimeMs: r.response_time_ms,
  }));

  return (
    <Card>
      <CardHeader>
        <CardTitle>API response time by run</CardTitle>
      </CardHeader>
      <CardContent>
        {!hasRunHistory ? (
          <p className="text-muted-foreground text-sm">
            Run history is unavailable from the stats API response.
          </p>
        ) : data.length === 0 ? (
          <p className="text-muted-foreground text-sm">No review runs yet.</p>
        ) : (
          <ResponsiveContainer width="100%" height={260}>
            <LineChart data={data} margin={{ top: 8, right: 8, left: -16, bottom: 0 }}>
              <XAxis
                dataKey="run"
                tick={{ fontSize: 12, fill: "var(--muted-foreground)" }}
                tickLine={false}
                axisLine={false}
              />
              <YAxis
                tick={{ fontSize: 12, fill: "var(--muted-foreground)" }}
                tickLine={false}
                axisLine={false}
                label={{
                  value: "ms",
                  angle: -90,
                  position: "insideLeft",
                  fill: "var(--muted-foreground)",
                  fontSize: 12,
                }}
              />
              <Tooltip
                formatter={(value) => {
                  if (value == null || value === "") return "Unavailable";
                  const n = Number(value);
                  return Number.isFinite(n) ? `${n.toFixed(3)} ms` : "Unavailable";
                }}
                labelFormatter={(_, payload) =>
                  runTooltipLabel(payload?.[0]?.payload as RunPoint | undefined)
                }
                contentStyle={{
                  background: "var(--popover)",
                  border: "1px solid var(--border)",
                  borderRadius: 8,
                  color: "var(--popover-foreground)",
                  fontSize: 12,
                }}
              />
              <Line
                type="monotone"
                dataKey="responseTimeMs"
                stroke="var(--chart-1)"
                strokeWidth={2}
                dot={{ r: 3 }}
                activeDot={{ r: 5 }}
                connectNulls={false}
              />
            </LineChart>
          </ResponsiveContainer>
        )}
      </CardContent>
    </Card>
  );
}
