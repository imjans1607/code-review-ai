import { Badge } from "@/components/ui/badge";
import { severityColor } from "@/lib/severity";
import type { Severity } from "@/lib/api";

/** A severity label with a color dot — readable in both light and dark themes. */
export function SeverityBadge({ severity }: { severity: Severity }) {
  return (
    <Badge variant="outline" className="gap-1.5">
      <span
        className="size-2 rounded-full"
        style={{ backgroundColor: severityColor[severity] }}
      />
      {severity}
    </Badge>
  );
}
