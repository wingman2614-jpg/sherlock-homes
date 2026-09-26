import { num, pct, signed } from "@/lib/format";
import type { MetroCase } from "@/lib/types";
import { LevelBadge, Pill, Section } from "./ui";

export default function MetroCaseFile({ m }: { m: MetroCase }) {
  const windows = ["5-year", "1-year"];
  return (
    <article className="pb-10">
      <header className="pb-4">
        <div className="mb-2 flex flex-wrap items-center gap-2">
          <span className="case-stamp text-xs font-semibold text-ink-muted">REGIONAL FILE</span>
          <LevelBadge level={m.anomaly["5-year"]?.level ?? "INSUFFICIENT DATA"} long />
        </div>
        <h2 className="font-serif text-2xl font-semibold">{m.title}</h2>
        <p className="mt-1 text-sm text-ink-soft">{m.name}</p>
        <p className="mt-2 rounded-md bg-brass-soft p-2 text-xs text-brass">{m.geography_note}</p>
      </header>
      {windows.map((w) => (
        <Section key={w} title={`Pittsburgh metro vs. ${m.signals.find((s) => s.window === w)?.peer_n ?? ""} peer metros — ${w}`} kicker="Evidence">
          <table className="tabular w-full text-sm">
            <thead className="text-left text-xs text-ink-muted">
              <tr><th className="py-1 font-normal">Indicator</th><th className="font-normal">Pittsburgh</th><th className="font-normal">Peer median</th><th className="font-normal">Percentile</th><th className="font-normal">z</th></tr>
            </thead>
            <tbody>
              {m.signals.filter((s) => s.window === w).map((s) => {
                const f = (x: number | null) => (s.transform === "diff" ? signed(x, 0) : pct(x, 1));
                return (
                  <tr key={s.indicator} className="border-t border-line align-top">
                    <td className="py-1.5">
                      {s.short} {!s.scored && <Pill>context</Pill>}
                      <div className="text-[10px] text-ink-muted">{s.period_start.slice(0, 7)} → {s.period_end.slice(0, 7)} · {s.source}</div>
                    </td>
                    <td className="font-semibold">{f(s.change)}</td>
                    <td>{f(s.peer_median)}</td>
                    <td>{num(s.percentile)}</td>
                    <td>{signed(s.z_score)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          <p className="mt-2 text-xs text-ink-muted">
            Anomaly score ({w}): {m.anomaly[w]?.score?.toFixed(2) ?? "n/a"} — {m.anomaly[w]?.level}. Robust z vs all metros with data.
          </p>
        </Section>
      ))}
      <Section title="Zillow forecast (not evidence)" kicker="Outlook">
        <ul className="tabular text-sm">
          {Object.entries(m.forecast.horizons).map(([d, h]) => (
            <li key={d}>to {d.slice(0, 7)}: Pittsburgh {h.pittsburgh_pct >= 0 ? "+" : ""}{h.pittsburgh_pct}% · US {h.us_pct >= 0 ? "+" : ""}{h.us_pct}%</li>
          ))}
        </ul>
        <p className="mt-2 text-xs text-ink-muted">{m.forecast.note}</p>
      </Section>
      <Section title="What Sherlock doesn't know" kicker="Open questions">
        <ul className="space-y-1 text-sm text-ink-soft">{m.limitations.map((l) => <li key={l}>• {l}</li>)}</ul>
      </Section>
    </article>
  );
}
