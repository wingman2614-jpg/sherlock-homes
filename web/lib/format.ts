import type { ConfidenceLevel, Level } from "./types";

export const pct = (x: number | null | undefined, digits = 0): string =>
  x === null || x === undefined || Number.isNaN(x) ? "n/a" : `${x >= 0 ? "+" : "−"}${Math.abs(x * 100).toFixed(digits)}%`;

export const num = (x: number | null | undefined, digits = 0): string =>
  x === null || x === undefined || Number.isNaN(x)
    ? "n/a"
    : x.toLocaleString("en-US", { maximumFractionDigits: digits, minimumFractionDigits: digits });

export const usd = (x: number | null | undefined): string => {
  if (x === null || x === undefined || Number.isNaN(x)) return "n/a";
  const a = Math.abs(x);
  if (a >= 1e6) return `$${(x / 1e6).toFixed(1)}M`;
  if (a >= 1e3) return `$${(x / 1e3).toFixed(0)}K`;
  return `$${x.toFixed(0)}`;
};

export const value = (unit: string, x: number | null | undefined): string =>
  unit === "USD per month" ? (x === null || x === undefined ? "n/a" : `$${num(x)}/mo`) : unit.startsWith("USD") ? usd(x) : num(x);

export const signed = (x: number | null | undefined, digits = 1): string =>
  x === null || x === undefined || Number.isNaN(x) ? "n/a" : `${x >= 0 ? "+" : "−"}${Math.abs(x).toFixed(digits)}`;

export const LEVEL_LABEL: Record<Level, string> = {
  HIGH: "High unusualness",
  MEDIUM: "Medium unusualness",
  LOW: "Low unusualness",
  "INSUFFICIENT DATA": "Insufficient data",
};

export const LEVEL_PLAIN: Record<Level, string> = {
  HIGH: "Very unusual",
  MEDIUM: "Somewhat unusual",
  LOW: "About typical",
  "INSUFFICIENT DATA": "Not enough data",
};

export const levelClass = (l: Level): string =>
  ({
    HIGH: "text-oxblood",
    MEDIUM: "text-brass",
    LOW: "text-ink-soft",
    "INSUFFICIENT DATA": "text-ink-muted",
  })[l];

export const confidenceClass = (c: ConfidenceLevel): string =>
  ({
    HIGH: "border-hunter text-hunter dark:border-brass dark:text-brass",
    MODERATE: "border-brass text-brass",
    LOW: "border-ink-muted text-ink-soft",
  })[c];

// Map fill colors: one-hue tobacco ordinal ramp (validated: monotone lightness,
// light end >= 2:1 on the basemap). Unusualness is magnitude, not good/bad.
export const LEVEL_FILL: Record<Level, string> = {
  HIGH: "#5e2a12",
  MEDIUM: "#a0602a",
  LOW: "#cf9a4e",
  "INSUFFICIENT DATA": "#d8d2c4",
};

/** "003" / "Z-003" style case label. */
export const caseLabel = (c: { case_label?: string | null; case_number: number | null }): string =>
  c.case_label ?? (c.case_number ? String(c.case_number).padStart(3, "0") : "");

/** Word for the comparison group: "city" for neighborhoods, "county" for ZIP codes. */
export const compWord = (geography?: string): string => (geography === "zip" ? "county" : "city");
