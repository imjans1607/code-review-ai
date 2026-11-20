import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button, buttonVariants } from "@/components/ui/button";
import { SeverityBadge } from "./SeverityBadge";
import { reviewExportUrl, type ReviewDetail } from "@/lib/api";
import { cn } from "@/lib/utils";
import { Download, ShieldAlert, Sparkles, X } from "lucide-react";

export function ReviewDetailPanel({
  detail,
  loading,
  onClose,
}: {
  detail: ReviewDetail | null;
  loading: boolean;
  onClose: () => void;
}) {
  if (!detail && !loading) return null;

  return (
    <Card>
      <CardHeader className="flex-row items-start justify-between">
        <div>
          <CardTitle>
            Review #{detail?.pr_number || detail?.id} — {detail?.repo || "—"}
          </CardTitle>
          <CardDescription>
            {detail
              ? `${detail.report.total} comment(s) · commit ${
                  detail.commit_sha?.slice(0, 7) || "—"
                }`
              : "Loading…"}
          </CardDescription>
        </div>
        <div className="flex items-center gap-2">
          {detail && (
            <>
              <a
                href={reviewExportUrl(detail.id, "csv")}
                download
                className={cn(buttonVariants({ variant: "outline", size: "sm" }))}
              >
                <Download /> CSV
              </a>
              <a
                href={reviewExportUrl(detail.id, "json")}
                download
                className={cn(buttonVariants({ variant: "outline", size: "sm" }))}
              >
                <Download /> JSON
              </a>
            </>
          )}
          <Button variant="ghost" size="icon" onClick={onClose} aria-label="Close">
            <X />
          </Button>
        </div>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        {loading && <p className="text-muted-foreground text-sm">Loading review…</p>}

        {detail?.report.comments.map((c, i) => (
          <div key={i} className="rounded-lg border p-3">
            <div className="mb-1.5 flex flex-wrap items-center gap-2">
              <SeverityBadge severity={c.severity} />
              <span className="text-muted-foreground inline-flex items-center gap-1 text-xs">
                {c.category === "security" ? (
                  <ShieldAlert className="size-3" />
                ) : (
                  <Sparkles className="size-3" />
                )}
                {c.category}
              </span>
              <code className="text-muted-foreground text-xs">
                {c.path}:{c.line}
              </code>
            </div>
            <p className="text-sm">{c.message}</p>
            {c.cwe?.length > 0 && (
              <p className="text-muted-foreground mt-1 text-xs">{c.cwe[0]}</p>
            )}
            {c.rationale && (
              <p className="text-muted-foreground mt-1 border-l-2 pl-2 text-xs italic">
                {c.rationale}
              </p>
            )}
          </div>
        ))}

        {detail && detail.report.comments.length === 0 && (
          <p className="text-muted-foreground text-sm">
            No issues found in this review. ✅
          </p>
        )}

        {detail?.report.notes && detail.report.notes.length > 0 && (
          <p className="text-muted-foreground text-xs">
            Notes: {detail.report.notes.join("; ")}
          </p>
        )}
      </CardContent>
    </Card>
  );
}
