import { num, pct } from "@/lib/format";
import type { Conflict } from "@/lib/types";
import { Pill } from "./ui";

const STATUS: Record<Conflict["status"], { label: string; tone: "neutral" | "warn" | "ok" }> = {
  agree: { label: "Sources agree", tone: "ok" },
  magnitude: { label: "Conflicting evidence: size differs", tone: "warn" },
  direction: { label: "Conflicting evidence: direction differs", tone: "warn" },
  unknown: { label: "Cannot compare", tone: "neutral" },
};

export function ConflictCard({ c }: { c: Conflict }) {
  const st = STATUS[c.status];
  return (
    <div className={`rounded-md border-2 border-stroke p-3 text-xs ${c.status === "agree" ? "bg-paper-raised" : "bg-oxblood-soft"}`}>
      <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
        <p className="font-semibold">{c.concept} <span className="font-normal text-ink-muted">· {c.scope}</span></p>
        <Pill tone={st.tone}>{st.label}</Pill>
      </div>
      {c.summary && <p className="mb-2 text-ink-soft">{c.summary}</p>}
      {c.comparisons && c.sources && (
        <table className="tabular mb-2 w-full text-left">
          <thead className="text-ink-muted">
            <tr><th className="py-1 font-normal">Window</th><th className="font-normal">{c.sources[0].label}</th><th className="font-normal">{c.sources[1].label}</th></tr>
          </thead>
          <tbody>
            {c.comparisons.map((x) => (
              <tr key={x.window} className="border-t border-line">
                <td className="py-1">{x.window} ({x.period_start}→{x.period_end})</td>
                <td className="font-semibold">{pct(x.zillow_change_pct, 1)}</td>
                <td className="font-semibold">{pct(x.redfin_change_pct, 1)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {!c.comparisons && c.sources && (
        <table className="tabular mb-2 w-full text-left">
          <tbody>
            {c.sources.map((s) => (
              <tr key={s.label} className="border-t border-line">
                <td className="py-1">{s.label}<br /><span className="text-ink-muted">{s.geography}</span></td>
                <td>{num(s.baseline)} → {num(s.recent)}</td>
                <td className="text-right font-semibold">{pct(s.change_pct)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      <div className="grid gap-2 sm:grid-cols-2">
        <div>
          <p className="font-semibold uppercase tracking-wider text-[10px] text-ink-muted">What the evidence agrees on</p>
          <ul className="text-ink-soft">{c.evidence_agrees_on.map((t) => <li key={t}>• {t}</li>)}</ul>
        </div>
        <div>
          <p className="font-semibold uppercase tracking-wider text-[10px] text-ink-muted">What remains uncertain</p>
          <ul className="text-ink-soft">{c.remains_uncertain.map((t) => <li key={t}>• {t}</li>)}</ul>
        </div>
      </div>
      <p className="mt-2 font-semibold uppercase tracking-wider text-[10px] text-ink-muted">Possible reasons (not verified)</p>
      <ul className="text-ink-soft">{c.possible_reasons.map((t) => <li key={t}>• {t}</li>)}</ul>
      <p className="mt-1 text-[10px] italic text-ink-muted">{c.reason_basis}</p>
    </div>
  );
}
