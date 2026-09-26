"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Brand } from "@/components/Brand";
import DrJohn from "@/components/DrJohn";
import HeroArt from "@/components/HeroArt";
import { LevelBadge } from "@/components/ui";
import { getSummary, isOffline } from "@/lib/api";
import { caseLabel, num, pct } from "@/lib/format";
import { ModeToggle, useMode } from "@/lib/mode";
import type { CaseCard, HomeSummary } from "@/lib/types";

const TREND_LABELS: Record<string, [string, string, string]> = {
  // [detailed label, plain label, swatch colour]
  res_new_construction_permits: ["New residential construction permits", "Permits to build new homes", "#8c7851"],
  demolition_permits: ["Demolition permits", "Demolition permits", "#f25042"],
  res_alteration_permits: ["Residential renovation permits", "Home renovation permits", "#eaddcf"],
  res_permit_value: ["Declared residential permit value", "Planned spending on home projects", "#020826"],
};

function CaseTile({ c, basic }: { c: CaseCard; basic: boolean }) {
  return (
    <Link href={`/investigate?case=${c.id}`} className="dossier group block p-5 transition hover:-translate-y-0.5 hover:bg-paper-sunk">
      <div className="mb-3 flex items-center justify-between">
        <span className="case-stamp text-[11px] uppercase text-ink-muted">Case {caseLabel(c)}</span>
        <LevelBadge level={c.level} />
      </div>
      <p className="text-xl font-bold leading-snug">{basic ? c.name : c.title}</p>
      <p className="mb-3 text-sm text-ink-soft">{basic ? c.title : c.name}</p>
      {!basic && (
        <ul className="space-y-1 text-xs text-ink-soft">
          {c.why_noticed.slice(0, 2).map((w) => <li key={w} className="tabular">• {w}</li>)}
        </ul>
      )}
    </Link>
  );
}

export default function Home() {
  const [s, setS] = useState<HomeSummary | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const { mode } = useMode();
  const router = useRouter();
  const basic = mode === "basic";
  useEffect(() => {
    getSummary().then(setS).catch((e) => setErr(String(e)));
  }, []);

  return (
    <div className="min-h-screen">
      <header className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-4 px-4 py-6 sm:px-6">
        <Brand />
        <nav className="flex flex-wrap items-center gap-5 text-[15px] font-bold">
          <Link href="/investigate" className="hover:text-oxblood">Case files</Link>
          <Link href="/investigate?layer=zip" className="hover:text-oxblood">ZIP map</Link>
          <Link href="/investigate?case=case-metro" className="hover:text-oxblood">Regional backdrop</Link>
          <ModeToggle />
        </nav>
      </header>

      <main className="mx-auto max-w-6xl px-4 pb-16 sm:px-6">
        {/* hero */}
        <section className="grid items-center gap-10 py-10 md:grid-cols-[1.05fr_1fr] md:py-16">
          <div>
            <h1 className="text-5xl font-bold leading-[1.05] tracking-tight sm:text-6xl">
              Housing dashboards show you the data.
            </h1>
            <p className="mt-3 text-2xl font-bold leading-snug text-oxblood sm:text-3xl">Sherlock Homes shows you where to investigate.</p>
            <p className="mt-6 max-w-xl text-lg leading-8 text-ink-soft">
              {basic
                ? "Sherlock looks at every Pittsburgh neighborhood and ZIP code and points out the ones where housing changed differently from the rest of the area. Then it explains what it found in plain English, and what it can't know."
                : "Sherlock scans every Pittsburgh neighborhood and Allegheny County ZIP code, flags areas whose housing activity departs from the typical pattern, and opens a case file: evidence, timing, similar areas, where sources disagree, and what the data cannot tell us."}
            </p>
            <div className="mt-8 flex flex-wrap items-center gap-5">
              <Link href="/investigate" className="btn-primary inline-block px-7 py-4 text-base">
                Open the case files
              </Link>
              {s && (
                <p className="text-ink-soft">
                  <strong className="text-3xl text-ink">{s.areas_worth_investigating}</strong> of {s.areas_analysed} neighborhoods
                  {s.zip && (
                    <>
                      {" "}· <strong className="text-3xl text-ink">{s.zip.cases_worth_investigating}</strong> of {s.zip.areas} ZIP codes
                    </>
                  )}{" "}
                  stand out
                </p>
              )}
            </div>
            {err && <p className="mt-4 text-sm text-oxblood">Could not load data: {err}</p>}
            {s && isOffline() && <p className="mt-3 text-xs text-ink-muted">Offline mode: showing the last exported analysis.</p>}
          </div>
          <HeroArt className="w-full" />
        </section>

        {/* choose view */}
        <section className="py-8">
          <h2 className="text-3xl font-bold">Choose your view</h2>
          <p className="mb-5 text-ink-soft">Switch any time from the top of the page.</p>
          <div className="max-w-3xl"><ModeToggle size="lg" /></div>
        </section>

        {/* city numbers, styled like hue chips */}
        {s && (
          <section className="py-8">
            <h2 className="text-3xl font-bold">{basic ? "Across the whole city" : "Citywide baseline"}</h2>
            <p className="mb-5 text-ink-soft">
              {basic ? "How activity changed across Pittsburgh" : "Every neighborhood is compared with the city's change"}, {s.baseline_years[0]}–
              {s.baseline_years.at(-1)} vs. {s.recent_years[0]}–{s.recent_years.at(-1)}
            </p>
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {Object.entries(s.city_trends).map(([k, t]) => {
                const [det, plain, color] = TREND_LABELS[k] ?? [k, k, "#8c7851"];
                return (
                  <div key={k} className="dossier flex items-center gap-3 px-4 py-3">
                    <span className="h-6 w-6 shrink-0 rounded-full border-2 border-stroke" style={{ background: color }} />
                    <span className="flex-1 font-bold">{basic ? plain : det}</span>
                    <span className="tabular text-lg font-bold">{pct(t.change_pct)}</span>
                  </div>
                );
              })}
            </div>
            {!basic && <p className="mt-2 text-xs text-ink-muted">Source: City of Pittsburgh building permits, through {s.permit_last_date}.</p>}
          </section>
        )}

        {/* cases */}
        <section className="py-8">
          <div className="mb-5 flex items-baseline justify-between">
            <div>
              <h2 className="text-3xl font-bold">Open cases</h2>
              <p className="text-ink-soft">Neighborhoods where building activity changed the most.</p>
            </div>
            <Link href="/investigate" className="font-bold hover:text-oxblood">All case files →</Link>
          </div>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {s?.top_cases.map((c) => <CaseTile key={c.id} c={c} basic={basic} />)}
          </div>
        </section>

        {s?.top_zip_cases && s.top_zip_cases.length > 0 && (
          <section className="py-8">
            <div className="mb-5 flex items-baseline justify-between">
              <div>
                <h2 className="text-3xl font-bold">{basic ? "Homes & rents: ZIP codes to watch" : "ZIP-code market cases"}</h2>
                <p className="text-ink-soft">
                  {basic
                    ? "Home values, rents and sales across Allegheny County, from Zillow and County sales records."
                    : "Zillow ZHVI and ZORI plus County valid sales, each ZIP compared with the typical Allegheny County ZIP."}
                </p>
              </div>
              <Link href="/investigate?layer=zip" className="font-bold hover:text-oxblood">ZIP map →</Link>
            </div>
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {s.top_zip_cases.map((c) => <CaseTile key={c.id} c={c} basic={basic} />)}
            </div>
          </section>
        )}

        {/* principles */}
        <section className="grid gap-4 py-8 md:grid-cols-3">
          {(basic
            ? [
                ["Built on real records", "Every finding comes from City permits, County sales and published housing data. Nothing is made up.", "#8c7851"],
                ["Clear about limits", "Sherlock tells you how sure it is, and what the data can't show, like incomes or who lives in a neighborhood.", "#f25042"],
                ["A lead, not a verdict", "An unusual area is a place to look closer. It is not a judgment that things are good or bad.", "#eaddcf"],
              ]
            : [
                ["Deterministic evidence", "Trends, anomaly scores, timing and similarity are computed from the data with transparent formulas.", "#8c7851"],
                ["Language only explains", "Findings are written from calculated evidence; AI text is fact-checked for invented numbers and causal claims.", "#f25042"],
                ["Uncertainty is shown", "Every case lists sources, geography, time period, confidence and what Sherlock cannot conclude.", "#eaddcf"],
              ]
          ).map(([t, d, c]) => (
            <div key={t} className="dossier p-5">
              <span className="mb-3 block h-8 w-8 rounded-full border-2 border-stroke" style={{ background: c }} />
              <h3 className="mb-1 text-lg font-bold">{t}</h3>
              <p className="text-sm leading-6 text-ink-soft">{d}</p>
            </div>
          ))}
        </section>

        <footer className="mt-6 border-t-2 border-stroke pt-6 text-xs text-ink-soft">
          Sherlock Homes · Decision support only: not legal, financial or zoning advice. Data: City of Pittsburgh permits & city-owned property,
          Allegheny County property sales (WPRDC), Census blocks and tracts, Zillow Research, Redfin Data Center.{" "}
          {s && `${num(s.areas_analysed)} neighborhoods and ${s.zip?.areas ?? 0} ZIP codes analysed.`}
        </footer>
      </main>
      <DrJohn onOpenCase={(id) => router.push(`/investigate?case=${encodeURIComponent(id)}`)} />
    </div>
  );
}
