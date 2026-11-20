import { buttonVariants } from "@/components/ui/button";
import type { Filters } from "@/components/FilterBar";
import { exportUrl } from "@/lib/api";
import { cn } from "@/lib/utils";
import { Download } from "lucide-react";

/**
 * Download buttons for the review history. They export everything in the
 * database that matches the active filters (not just the rows loaded in the
 * table), so the file can be larger than "Showing X of Y".
 */
export function ExportMenu({ filters }: { filters: Filters }) {
  const links = [
    { label: "Reviews CSV", href: exportUrl({ format: "csv", scope: "reviews", filters }) },
    { label: "Findings CSV", href: exportUrl({ format: "csv", scope: "findings", filters }) },
    { label: "JSON", href: exportUrl({ format: "json", filters }) },
  ];
  return (
    <div className="flex flex-wrap items-center gap-2">
      <span className="text-muted-foreground inline-flex items-center gap-1.5 text-sm">
        <Download className="size-4" /> Export
      </span>
      {links.map((l) => (
        <a
          key={l.label}
          href={l.href}
          download
          className={cn(buttonVariants({ variant: "outline", size: "sm" }))}
        >
          {l.label}
        </a>
      ))}
      <span className="text-muted-foreground text-xs">
        all history matching the filters
      </span>
    </div>
  );
}
