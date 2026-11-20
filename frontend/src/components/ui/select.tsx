import * as React from "react";
import { ChevronDown } from "lucide-react";
import { cn } from "@/lib/utils";

/** A lightweight native <select> styled to match the shadcn look. */
function Select({ className, children, ...props }: React.ComponentProps<"select">) {
  return (
    <div className="relative inline-flex">
      <select
        className={cn(
          "border-input bg-background h-9 w-full appearance-none rounded-md border pl-3 pr-8 text-sm shadow-sm outline-none",
          "focus-visible:ring-ring/50 focus-visible:ring-[3px] disabled:opacity-50",
          className
        )}
        {...props}
      >
        {children}
      </select>
      <ChevronDown className="text-muted-foreground pointer-events-none absolute right-2 top-1/2 size-4 -translate-y-1/2" />
    </div>
  );
}

export { Select };
