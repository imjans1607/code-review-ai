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

export function FindingsAcrossRunsChart({ stats }: { stats: Stats | null | undefined }) {
  const hasRunHistory = Array.isArray(stats?.run_history);
  const runHistory = hasRunHistory ? stats.run_history : [];
  const data = runHistory.map((r) => ({
    run: `R${r.review_id}`,
    reviewId: r.review_id,
    prNumber: r.pr_number,
    coldStart: r.cold_start,
    aiFindings: r.ai_findings,
    securityFindings: r.security_findings,
    fusedFindings: r.fused_findings,
  }));

  return (
    <Card>
      <CardHeader>
        <CardTitle>AI vs Security vs Fused findings by run</CardTitle>
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
                allowDecimals={false}
                tick={{ fontSize: 12, fill: "var(--muted-foreground)" }}
                tickLine={false}
                axisLine={false}
              />
              <Tooltip
                formatter={(value) => {
                  if (value == null || value === "") return "Unavailable";
                  const n = Number(value);
                  return Number.isFinite(n) ? n : "Unavailable";
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
                dataKey="aiFindings"
                name="AI findings"
                stroke="var(--chart-1)"
                strokeWidth={2}
                dot={{ r: 3 }}
                connectNulls={false}
              />
              <Line
                type="monotone"
                dataKey="securityFindings"
                name="Security findings"
                stroke="var(--chart-2)"
                strokeWidth={2}
                dot={{ r: 3 }}
                connectNulls={false}
              />
              <Line
                type="monotone"
                dataKey="fusedFindings"
                name="Fused total findings"
                stroke="var(--chart-3)"
                strokeWidth={2}
                dot={{ r: 3 }}
                connectNulls={false}
              />
            </LineChart>
          </ResponsiveContainer>
        )}
      </CardContent>
    </Card>
  );
}
