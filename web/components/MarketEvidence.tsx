// ZIP-level market evidence shown inside a neighborhood case file,
// plus optional Census ACS tract estimates. Everything is labelled with its
// geography because ZIPs and tracts don't match neighborhood borders.
import { num, pct, signed, usd } from "@/lib/format";
import type { AcsContext, ZipMarketContext, ZipSignalBrief } from "@/lib/types";
import { ConflictCard } from "./Conflicts";
import { LevelBadge, Pill } from "./ui";

const money = (s: ZipSignalBrief, x: number | null) =>
  x === null ? "n/a" : s.indicator === "zip_rent" ? `$${num(x)}/mo` : s.unit.startsWith("USD") ? usd(x) : num(x);

export function MarketEvidence({ m, onOpen }: { m: ZipMarketContext; onOpen: (id: string) => void }) {
  if (!m.zips.length) return <p className="text-sm text-ink-muted">No ZIP-level market data covers this neighborhood.</p>;
  return (
    <div className="space-y-3">
      <p className="text-xs text-ink-muted">{m.note}</p>
      {m.zips.map((z) => (
        <div key={z.zip} className="rounded-md border-2 border-stroke bg-paper p-3">
          <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
            <button onClick={() => onOpen(z.case_id)} className="font-serif font-semibold hover:text-oxblood hover:underline">
              {z.name}
            </button>
            <span className="flex items-center gap-2">
              <Pill>covers {Math.round(z.share_of_neighborhood_land * 100)}% of this neighborhood</Pill>
              <LevelBadge level={z.level} />
            </span>
          </div>
          <table className="tabular w-full text-xs">
            <thead className="text-left text-ink-muted">
              <tr><th className="py-1 font-normal">Indicator</th><th className="font-normal">Before → after</th><th className="text-right font-normal">Change</th><th className="text-right font-normal">County typical</th><th className="text-right font-normal">z</th></tr>
            </thead>
            <tbody>
              {z.signals.map((s) => (
                <tr key={s.indicator} className="border-t border-line align-top">
                  <td className="py-1.5">{s.short}<div className="text-[10px] text-ink-muted">{s.baseline_period} → {s.recent_period}</div></td>
                  <td>{s.status === "scored" ? `${money(s, s.baseline_value)} → ${money(s, s.recent_value)}` : "UNKNOWN"}</td>
                  <td className="text-right font-semibold">{pct(s.change_pct)}</td>
                  <td className="text-right">{pct(s.city_change_pct)}</td>
                  <td className="text-right">{s.status === "scored" ? signed(s.z_score) : "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="mt-1 text-[10px] text-ink-muted">Sources: Zillow ZHVI & ZORI (ZIP), Allegheny County valid sales. ZIP-code level, not neighborhood.</p>
        </div>
      ))}
      {m.zips[0]?.price_conflict && <ConflictCard c={m.zips[0].price_conflict} />}
    </div>
  );
}

export function AcsEvidence({ a }: { a: AcsContext }) {
  return (
    <div className="space-y-3 text-xs">
      <p className="text-ink-muted">{a.note}</p>
      {a.vintages.map((v) => (
        <div key={v.year} className="rounded-md border-2 border-stroke bg-paper p-3">
          <p className="mb-1 font-semibold">ACS {v.period} <span className="font-normal text-ink-muted">· {v.tract_vintage} tract boundaries</span></p>
          <table className="tabular w-full">
            <thead className="text-left text-ink-muted">
              <tr><th className="py-1 font-normal">Tract</th><th className="font-normal">Share</th><th className="text-right font-normal">Median rent</th><th className="text-right font-normal">Median income</th><th className="text-right font-normal">Vacant</th><th className="text-right font-normal">Renters</th></tr>
            </thead>
            <tbody>
              {v.tracts.map((t) => (
                <tr key={t.geoid} className="border-t border-line">
                  <td className="py-1">{t.geoid.slice(5)}</td>
                  <td>{Math.round(t.share_of_neighborhood_land * 100)}%</td>
                  <td className="text-right">{t.median_gross_rent === null ? "n/a" : `$${num(t.median_gross_rent)}`}</td>
                  <td className="text-right">{usd(t.median_household_income)}</td>
                  <td className="text-right">{t.vacancy_rate === null ? "n/a" : `${(t.vacancy_rate * 100).toFixed(0)}%`}</td>
                  <td className="text-right">{t.renter_share === null ? "n/a" : `${(t.renter_share * 100).toFixed(0)}%`}</td>
                </tr>
              ))}
              <tr className="border-t border-line text-ink-muted">
                <td className="py-1" colSpan={2}>Typical city tract</td>
                <td className="text-right">{v.typical_city_tract.median_gross_rent ? `$${num(v.typical_city_tract.median_gross_rent)}` : "n/a"}</td>
                <td className="text-right">{usd(v.typical_city_tract.median_household_income ?? null)}</td>
                <td className="text-right">{v.typical_city_tract.vacancy_rate != null ? `${(v.typical_city_tract.vacancy_rate * 100).toFixed(0)}%` : "n/a"}</td>
                <td className="text-right">{v.typical_city_tract.renter_share != null ? `${(v.typical_city_tract.renter_share * 100).toFixed(0)}%` : "n/a"}</td>
              </tr>
            </tbody>
          </table>
          <p className="mt-1 text-[10px] text-ink-muted">{v.source}. Survey estimates with margins of error.</p>
        </div>
      ))}
    </div>
  );
}
