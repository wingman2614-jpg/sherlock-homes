"use client";

import type { ReactNode } from "react";
import { confidenceClass, LEVEL_LABEL, LEVEL_PLAIN, levelClass } from "@/lib/format";
import { useMode } from "@/lib/mode";
import type { ConfidenceLevel, Level } from "@/lib/types";

/** Rubber-stamp style badge. Shows plain words in the Quick Brief view. */
export function LevelBadge({ level, long = false, stamp = false }: { level: Level; long?: boolean; stamp?: boolean }) {
  const { mode } = useMode();
  const text = mode === "basic" ? LEVEL_PLAIN[level] : long ? LEVEL_LABEL[level] : level;
  if (stamp) {
    return <span className={`ink-stamp inline-block px-2.5 py-1 text-xs uppercase ${levelClass(level)}`}>{text}</span>;
  }
  return (
    <span className={`case-stamp inline-flex items-center rounded border-2 border-current px-1.5 py-0.5 text-[10px] uppercase ${levelClass(level)}`}>
      {text}
    </span>
  );
}

export function ConfidenceBadge({ level }: { level: ConfidenceLevel }) {
  const { mode } = useMode();
  const words = mode === "basic" ? { HIGH: "Well supported", MODERATE: "Partly supported", LOW: "Weakly supported" }[level] : `${level} confidence`;
  return <span className={`case-stamp inline-flex items-center border px-1.5 py-0.5 text-[10px] uppercase ${confidenceClass(level)}`}>{words}</span>;
}

export function Section({ title, kicker, children, id, action }: { title: string; kicker?: string; children: ReactNode; id?: string; action?: ReactNode }) {
  return (
    <section id={id} className="border-t border-line py-5 first:border-t-0">
      <div className="mb-3 flex items-baseline justify-between gap-3">
        <div>
          {kicker && <p className="case-stamp text-[10px] uppercase text-oxblood">{kicker}</p>}
          <h3 className="text-xl font-bold">{title}</h3>
        </div>
        {action}
      </div>
      {children}
    </section>
  );
}

export function Pill({ children, tone = "neutral" }: { children: ReactNode; tone?: "neutral" | "warn" | "ok" }) {
  const t = {
    neutral: "bg-paper-sunk text-ink-soft",
    warn: "bg-oxblood-soft text-oxblood",
    ok: "bg-brass-soft text-hunter dark:text-brass",
  }[tone];
  return <span className={`inline-flex rounded-sm px-1.5 py-0.5 text-[11px] font-medium ${t}`}>{children}</span>;
}

export function ActionButton({ onClick, children, active = false }: { onClick: () => void; children: ReactNode; active?: boolean }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`case-stamp rounded border-2 px-3 py-1.5 text-[11px] uppercase transition ${
        active ? "border-stroke bg-ink text-paper-raised" : "border-stroke bg-brass text-paper-raised hover:brightness-110"
      }`}
    >
      {children}
    </button>
  );
}
