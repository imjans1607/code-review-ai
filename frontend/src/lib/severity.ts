import type { Severity } from "./api";

/** One color per severity, used for dots, chart bars, and accents. */
export const severityColor: Record<Severity, string> = {
  Critical: "#dc2626", // red-600
  High: "#ea580c", // orange-600
  Medium: "#d97706", // amber-600
  Low: "#2563eb", // blue-600
  Informational: "#64748b", // slate-500
};
