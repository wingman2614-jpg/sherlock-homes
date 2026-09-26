"use client";

import { useMemo, useState } from "react";
import { CartesianGrid, Legend, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { num, usd } from "@/lib/format";
import type { Onset, Signal, TimelinePoint } from "@/lib/types";

interface Props {
  timeline: Record<string, TimelinePoint[]>;
  signals: Signal[];
  onsets: Onset[];
  /** Quick Brief: one indicator, plain labels, no chips or table */
  simple?: boolean;
  /** Plain title used in the simple view */
  title?: string;
  /** Legend label for the dashed comparison line */
  expectedLabel?: string;
  /** Legend label for the solid line */
  areaLabel?: string;
}

export default function TimelineChart({ timeline, signals, onsets, simple = false, title, expectedLabel, areaLabel = "This neighborhood" }: Props) {
  const inds = signals.map((s) => s.indicator).filter((i) => timeline[i]);
  const firstStrong = [...signals].filter((s) => s.status === "scored").sort((a, b) => Math.abs(b.z_score ?? 0) - Math.abs(a.z_score ?? 0))[0];
  const [ind, setInd] = useState<string>(firstStrong?.indicator ?? inds[0]);
  const sig = signals.find((s) => s.indicator === ind);
  const isUsd = sig?.unit.startsWith("USD") ?? false;
  const fmt = (v: number | null | undefined) => (sig?.unit === "USD per month" ? (v == null ? "n/a" : `$${num(v)}`) : isUsd ? usd(v) : num(v));
  const onset = onsets.find(
    (o) => o.indicator === ind && o.year && (!simple || (o.direction === "up") === ((sig?.z_score ?? 0) > 0)),
  );

  const data = useMemo(
    () =>
      (timeline[ind] ?? []).map((p) => ({
        year: p.partial ? `${p.year}*` : String(p.year),
        value: p.value,
        expected: p.expected_from_2020_21_share,
        partial: p.partial,
      })),
    [timeline, ind],
  );

  return (
    <div>
      {!simple && <div className="mb-3 flex flex-wrap gap-1.5" role="tablist" aria-label="Indicator">
        {inds.map((i) => {
          const s = signals.find((x) => x.indicator === i);
          return (
            <button
              key={i}
              role="tab"
              aria-selected={i === ind}
              onClick={() => setInd(i)}
              className={`case-stamp rounded border-2 px-2.5 py-1 text-[11px] ${i === ind ? "border-stroke bg-ink text-paper-raised" : "border-stroke bg-paper-raised text-ink hover:bg-paper-sunk"}`}
            >
              {s?.short ?? i}
            </button>
          );
        })}
      </div>}
      {simple && sig && <p className="mb-2 text-sm font-semibold">{title ?? sig.label} per year</p>}
      <div className={`${simple ? "h-44" : "h-56"} w-full`}>
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 8, right: 12, left: 0, bottom: 0 }}>
            <CartesianGrid stroke="var(--line)" strokeDasharray="0" vertical={false} />
            <XAxis dataKey="year" tick={{ fill: "var(--ink-soft)", fontSize: 11 }} axisLine={{ stroke: "var(--line)" }} tickLine={false} />
            <YAxis tick={{ fill: "var(--ink-soft)", fontSize: 11 }} axisLine={false} tickLine={false} width={isUsd ? 56 : 36} tickFormatter={(v) => fmt(Number(v))} />
            <Tooltip
              contentStyle={{ background: "var(--paper-raised)", border: "1px solid var(--line)", borderRadius: 8, fontSize: 12, color: "var(--ink)" }}
              formatter={(v, name) => [fmt(v === null || v === undefined ? null : Number(v)), String(name)]}
            />
            <Legend wrapperStyle={{ fontSize: 11 }} />
            {onset?.year && (
              <ReferenceLine x={String(onset.year)} stroke="var(--brass)" strokeDasharray="3 3" label={{ value: simple ? "change begins" : "first departure", fill: "var(--brass)", fontSize: 10, position: "insideTopLeft" }} />
            )}
            <Line type="monotone" dataKey="value" name={areaLabel} stroke="var(--series-1)" strokeWidth={2} dot={{ r: 4 }} activeDot={{ r: 6 }} connectNulls={false} />
            <Line type="monotone" dataKey="expected" name={expectedLabel ?? (simple ? "If it had kept pace with the city" : "If it kept its 2020–21 share of city activity")} stroke="var(--series-expected)" strokeWidth={2} strokeDasharray="5 4" dot={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>
      {simple ? (
        <p className="mt-2 text-[11px] text-ink-muted">* Partial year. Source: City of Pittsburgh building permits.</p>
      ) : (<>
      <p className="mt-2 text-[11px] text-ink-muted">
        * Partial year — shown for context, excluded from change calculations. Source: {sig?.source}; {sig?.time_resolution}.
      </p>
      <details className="mt-2 text-xs text-ink-soft">
        <summary className="cursor-pointer">Table view</summary>
        <table className="tabular mt-2 w-full text-left">
          <thead className="text-ink-muted">
            <tr><th className="py-1">Year</th><th>{areaLabel}</th><th>{expectedLabel ?? "Expected (2020–21 share)"}</th></tr>
          </thead>
          <tbody>
            {data.map((d) => (
              <tr key={d.year} className="border-t border-line"><td className="py-1">{d.year}</td><td>{fmt(d.value)}</td><td>{fmt(d.expected)}</td></tr>
            ))}
          </tbody>
        </table>
      </details>
      </>)}
    </div>
  );
}
