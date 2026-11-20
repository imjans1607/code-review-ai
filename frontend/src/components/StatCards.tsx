import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { severityColor } from "@/lib/severity";
import { SEVERITIES, type Stats } from "@/lib/api";
import { FileSearch, ShieldAlert, GitPullRequest } from "lucide-react";

export function StatCards({ stats }: { stats: Stats }) {
  const critHigh =
    stats.severity_totals.Critical + stats.severity_totals.High;

  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
      <Card>
        <CardHeader className="flex-row items-center justify-between">
          <CardTitle className="text-sm text-muted-foreground">Reviews run</CardTitle>
          <GitPullRequest className="size-4 text-muted-foreground" />
        </CardHeader>
        <CardContent>
          <div className="text-3xl font-semibold">{stats.total_reviews}</div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="flex-row items-center justify-between">
          <CardTitle className="text-sm text-muted-foreground">Total findings</CardTitle>
          <FileSearch className="size-4 text-muted-foreground" />
        </CardHeader>
        <CardContent>
          <div className="text-3xl font-semibold">{stats.total_findings}</div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="flex-row items-center justify-between">
          <CardTitle className="text-sm text-muted-foreground">
            Critical + High
          </CardTitle>
          <ShieldAlert className="size-4" style={{ color: severityColor.Critical }} />
        </CardHeader>
        <CardContent>
          <div className="flex items-end gap-3">
            <div className="text-3xl font-semibold">{critHigh}</div>
            <div className="mb-1 flex flex-wrap gap-x-3 gap-y-1 text-xs text-muted-foreground">
              {SEVERITIES.map((s) => (
                <span key={s} className="flex items-center gap-1">
                  <span
                    className="size-2 rounded-full"
                    style={{ backgroundColor: severityColor[s] }}
                  />
                  {s[0]}: {stats.severity_totals[s]}
                </span>
              ))}
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
