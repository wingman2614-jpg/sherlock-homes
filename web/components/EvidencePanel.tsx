import { num, pct, signed, value } from "@/lib/format";
import type { CaseFile, Signal } from "@/lib/types";
import { Pill } from "./ui";

function SignalCard({ s }: { s: Signal }) {
  const scored = s.status === "scored";
  return (
    <div className="rounded-md border-2 border-stroke bg-paper-raised p-3">
      <div className="mb-2 flex items-start justify-between gap-2">
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-wider text-ink-muted">{s.category}</p>
          <p className="font-semibold leading-tight">{s.label}</p>
        </div>
        {scored ? (
          <Pill tone={Math.abs(s.z_score ?? 0) >= 2 ? "warn" : "neutral"}>z {signed(s.z_score)}</Pill>
        ) : (
          <Pill>UNKNOWN</Pill>
        )}
      </div>
      <dl className="tabular grid grid-cols-2 gap-x-3 gap-y-1 text-xs">
        <dt className="text-ink-muted">Previous ({s.baseline_period})</dt><dd className="text-right">{value(s.unit, s.baseline_value)}</dd>
        <dt className="text-ink-muted">Current ({s.recent_period})</dt><dd className="text-right">{value(s.unit, s.recent_value)}</dd>
        <dt className="text-ink-muted">Change</dt><dd className="text-right font-semibold">{pct(s.change_pct)}</dd>
        <dt className="text-ink-muted">{s.comparison_label ? "County comparison" : "Pittsburgh comparison"}</dt><dd className="text-right">{pct(s.city_change_pct)}</dd>
        <dt className="text-ink-muted">{s.comparison_label ? "Expected at county trend" : "Expected at city trend"}</dt><dd className="text-right">{value(s.unit, s.expected_recent)}</dd>
        {scored && (
          <>
            <dt className="text-ink-muted">Rank among {s.n_compared} areas</dt>
            <dd className="text-right">{s.percentile !== undefined ? `${num(s.percentile)}th pct.` : "n/a"}</dd>
          </>
        )}
      </dl>
      <div className="mt-2 border-t border-line pt-2 text-[11px] text-ink-soft">
        <p><span className="text-ink-muted">Source:</span> {s.source} <span className="font-mono text-[10px] text-ink-muted">({s.source_file})</span></p>
        <p><span className="text-ink-muted">Geography:</span> {s.geography} · <span className="text-ink-muted">Period:</span> {s.period_start} → {s.period_end}</p>
        <p><span className="text-ink-muted">Method:</span> {s.method}</p>
        {s.notes.length > 0 && (
          <ul className="mt-1 space-y-0.5 text-brass">
            {s.notes.map((n) => <li key={n}>• {n}</li>)}
          </ul>
        )}
      </div>
    </div>
  );
}

export default function EvidencePanel({ c }: { c: CaseFile }) {
  const v = c.evidence.context.city_owned_vacant_lots;
  const metro = c.evidence.context.metro;
  return (
    <div className="space-y-3">
      <div className="grid gap-3 xl:grid-cols-2">
        {c.evidence.signals.map((s) => <SignalCard key={s.indicator} s={s} />)}
      </div>
      {v && <div className="rounded-md border-2 border-dashed border-stroke p-3 text-xs">
        <p className="mb-1 font-semibold">Context: City-owned vacant lots <Pill>snapshot · not scored</Pill></p>
        <p className="tabular text-ink-soft">
          {num(v.value)} lots · {num(v.per_km2, 1)} per km² (citywide {num(v.city_per_km2, 1)}) · as of {v.snapshot}
        </p>
        <p className="mt-1 text-[11px] text-ink-muted">{v.source} · {v.geography} level · {v.caveats.join(" ")}</p>
      </div>}
      <div className="rounded-md border-2 border-dashed border-stroke p-3 text-xs">
        <p className="mb-1 font-semibold">Regional backdrop <Pill tone="warn">metro level — not this area</Pill></p>
        <ul className="tabular space-y-0.5 text-ink-soft">
          {metro.signals.map((m) => (
            <li key={m.indicator}>
              {m.short}: {m.transform === "diff" ? signed(m.change, 0) : pct(m.change)} over 5 years · peer-metro median {m.transform === "diff" ? signed(m.peer_median, 0) : pct(m.peer_median)}
            </li>
          ))}
        </ul>
        <p className="mt-1 text-[11px] text-ink-muted">{metro.note} Source: Zillow Research, Pittsburgh MSA (7 counties).</p>
      </div>
    </div>
  );
}
