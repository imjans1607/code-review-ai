import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { severityColor } from "@/lib/severity";
import { SEVERITIES, type ReviewRow } from "@/lib/api";

function SeverityDots({ summary }: { summary: ReviewRow["summary"] }) {
  return (
    <div className="flex flex-wrap gap-x-3 gap-y-1">
      {SEVERITIES.filter((s) => summary[s] > 0).map((s) => (
        <span key={s} className="flex items-center gap-1 text-xs">
          <span
            className="size-2 rounded-full"
            style={{ backgroundColor: severityColor[s] }}
          />
          {summary[s]}
        </span>
      ))}
    </div>
  );
}

export function ReviewsTable({
  reviews,
  selectedId,
  onSelect,
}: {
  reviews: ReviewRow[];
  selectedId: number | null;
  onSelect: (id: number) => void;
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Recent reviews</CardTitle>
      </CardHeader>
      <CardContent>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>PR</TableHead>
              <TableHead>Repository</TableHead>
              <TableHead>Author</TableHead>
              <TableHead>When (UTC)</TableHead>
              <TableHead className="text-right">Findings</TableHead>
              <TableHead>Breakdown</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {reviews.length === 0 && (
              <TableRow>
                <TableCell colSpan={6} className="text-muted-foreground text-center">
                  No reviews match the current filters.
                </TableCell>
              </TableRow>
            )}
            {reviews.map((r) => (
              <TableRow
                key={r.id}
                onClick={() => onSelect(r.id)}
                data-state={selectedId === r.id ? "selected" : undefined}
                className="cursor-pointer"
              >
                <TableCell className="font-medium">#{r.pr_number || r.id}</TableCell>
                <TableCell>{r.repo || "—"}</TableCell>
                <TableCell className="text-muted-foreground">{r.author || "—"}</TableCell>
                <TableCell className="text-muted-foreground">
                  {r.created_at.replace("T", " ").replace("+00:00", "")}
                </TableCell>
                <TableCell className="text-right font-medium">{r.total}</TableCell>
                <TableCell>
                  <SeverityDots summary={r.summary} />
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  );
}
