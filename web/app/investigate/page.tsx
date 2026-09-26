"use client";

import dynamic from "next/dynamic";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useRef, useState } from "react";
import AskSherlock from "@/components/AskSherlock";
import { Brand } from "@/components/Brand";
import { ModeToggle, useMode } from "@/lib/mode";
import CaseFile from "@/components/CaseFile";
import DrJohn from "@/components/DrJohn";
import MetroCaseFile from "@/components/MetroCaseFile";
import { LevelBadge } from "@/components/ui";
import { LEVEL_PLAIN } from "@/lib/format";
import { getCase, getCases, getGeo, getMetro, isOffline, type Layer } from "@/lib/api";
import { caseLabel } from "@/lib/format";
import type { CaseCard, CaseFile as CaseFileT, MetroCase } from "@/lib/types";

const MapView = dynamic(() => import("@/components/MapView"), { ssr: false, loading: () => <div className="h-full w-full animate-pulse bg-paper-sunk" /> });

function Investigate() {
  const params = useSearchParams();
  const router = useRouter();
  const caseParam = params.get("case");
  const [layer, setLayer] = useState<Layer>(caseParam?.startsWith("z") || params.get("layer") === "zip" ? "zip" : "neighborhood");
  const [geo, setGeo] = useState<GeoJSON.FeatureCollection | null>(null);
  const [cases, setCases] = useState<CaseCard[]>([]);
  const [current, setCurrent] = useState<CaseFileT | null>(null);
  const [metro, setMetro] = useState<MetroCase | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const panel = useRef<HTMLDivElement>(null);
  const { mode } = useMode();

  useEffect(() => {
    setGeo(null);
    getGeo(layer).then(setGeo).catch((e) => setErr(String(e)));
    getCases(layer).then(setCases).catch((e) => setErr(String(e)));
  }, [layer]);

  // opening a ZIP case switches the map to the ZIP layer (and vice versa)
  useEffect(() => {
    if (current) setLayer(current.geography === "zip" ? "zip" : "neighborhood");
  }, [current]);

  useEffect(() => {
    setErr(null);
    if (!caseParam) {
      setCurrent(null);
      setMetro(null);
      return;
    }
    setLoading(true);
    if (caseParam === "case-metro") {
      getMetro().then((m) => { setMetro(m); setCurrent(null); }).catch((e) => setErr(String(e))).finally(() => setLoading(false));
    } else {
      getCase(caseParam).then((c) => { setCurrent(c); setMetro(null); }).catch((e) => setErr(String(e))).finally(() => setLoading(false));
    }
    panel.current?.scrollTo({ top: 0 });
  }, [caseParam]);

  const open = useCallback((id: string) => router.push(`/investigate?case=${encodeURIComponent(id)}`, { scroll: false }), [router]);
  const onSelect = useCallback((areaId: string, caseId: string | null) => open(caseId ?? areaId), [open]);

  return (
    <div className="flex h-screen flex-col">
      <header className="tweed z-20 flex flex-wrap items-center gap-3 px-4 py-2.5">
        <Brand compact onDark />
        <div className="min-w-[240px] flex-1"><AskSherlock onOpen={open} /></div>
        <ModeToggle />
        <button onClick={() => open("case-metro")} className="hidden text-sm font-bold text-ink hover:text-oxblood md:block">
          Regional backdrop
        </button>
      </header>
      <div className="flex min-h-0 flex-1 flex-col lg:flex-row">
        <div className="relative h-[45vh] lg:h-auto lg:flex-1">
          <MapView geo={geo} selectedAreaId={current?.area_id ?? null} onSelect={onSelect} fitKey={layer} />
          <div className="dossier absolute right-14 top-3 flex overflow-hidden rounded-sm text-xs" role="group" aria-label="Map layer">
            {(["neighborhood", "zip"] as const).map((l) => (
              <button
                key={l}
                onClick={() => setLayer(l)}
                aria-pressed={layer === l}
                className={`case-stamp px-3 py-2 uppercase ${layer === l ? "bg-hunter text-hunter-ink" : "text-ink-soft hover:text-ink"}`}
              >
                {l === "neighborhood" ? "Neighborhoods" : "ZIP codes"}
              </button>
            ))}
          </div>
          <div className="dossier absolute left-3 top-3 max-h-[60%] w-64 overflow-auto rounded-sm">
            <p className="case-stamp sticky top-0 border-b border-line bg-paper-raised px-3 py-2 text-[11px] uppercase text-oxblood">
              {cases.length} {layer === "zip" ? "ZIP codes" : mode === "basic" ? "places" : "neighborhoods"} {mode === "basic" ? "worth a closer look" : "worth investigating"}
            </p>
            <ul>
              {cases.map((c) => (
                <li key={c.id}>
                  <button
                    onClick={() => open(c.id)}
                    className={`flex w-full items-center justify-between gap-2 px-3 py-1.5 text-left text-xs hover:bg-paper-sunk ${current?.id === c.id ? "bg-brass-soft" : ""}`}
                  >
                    <span>
                      <span className="case-stamp text-[10px] text-ink-muted">#{caseLabel(c)}</span> {c.name}
                    </span>
                    <LevelBadge level={c.level} />
                  </button>
                </li>
              ))}
            </ul>
          </div>
        </div>
        <aside ref={panel} className="min-h-0 overflow-y-auto border-l-[3px] border-double border-line bg-paper-raised px-6 lg:w-[560px] xl:w-[640px]">
          {err && <p className="mt-4 rounded bg-red-50 p-3 text-sm text-red-800">{err}</p>}
          {isOffline() && <p className="case-stamp mt-3 text-[10px] uppercase text-ink-muted">Offline mode — showing exported analysis. Start the API for questions and AI rephrasing.</p>}
          {loading && <p className="mt-6 text-sm text-ink-muted">Opening case file…</p>}
          {!loading && current && (
            <>
              <div className="sticky top-0 z-10 -mx-6 border-b border-line bg-paper-raised px-6 py-3">
                <ModeToggle size="lg" />
              </div>
              <div className="pt-5"><CaseFile c={current} onOpenArea={open} /></div>
            </>
          )}
          {!loading && metro && <div className="pt-5"><MetroCaseFile m={metro} /></div>}
          {!loading && !current && !metro && (
            <div className="py-10">
              <p className="case-stamp text-xs uppercase text-oxblood">Case files</p>
              <h2 className="mt-2 font-serif text-3xl font-bold">{layer === "zip" ? "Pick a ZIP code to investigate" : "Pick a neighborhood to investigate"}</h2>
              <p className="mt-3 text-ink-soft">
                {layer === "zip"
                  ? mode === "basic"
                    ? "The ZIP view covers all of Allegheny County and looks at home values, rents and sales. Darker ZIP codes changed differently from the rest of the county."
                    : "ZIP layer: Zillow home values (ZHVI) and rents (ZORI) plus County recorded sales, each ZIP compared with the typical Allegheny County ZIP. Unusual does not mean good or bad."
                  : mode === "basic"
                    ? "Darker areas changed differently from the rest of Pittsburgh. Click any area on the map, or a name in the list, to read its story in plain English."
                    : "Darker areas differ more from the citywide pattern of permits between 2020–22 and 2023–25. Click any area, or a case in the list, to open its case file. Unusual does not mean good or bad."}
              </p>
              <ul className="mt-6 space-y-2">
                {cases.slice(0, 5).map((c) => (
                  <li key={c.id}>
                    <button onClick={() => open(c.id)} className="w-full rounded-md border-2 border-stroke bg-paper p-3 text-left hover:border-oxblood">
                      <span className="case-stamp text-[10px] uppercase text-ink-muted">Case No. {caseLabel(c)} · {LEVEL_PLAIN[c.level]}</span>
                      <p className="font-serif text-lg font-semibold">{mode === "basic" ? c.name : c.title}</p>
                      <p className="text-xs text-ink-soft">{mode === "basic" ? c.title : `${c.name} · ${c.why_noticed[0]}`}</p>
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </aside>
      </div>
      <DrJohn caseId={current?.id ?? null} onOpenCase={open} />
    </div>
  );
}

export default function Page() {
  return (
    <Suspense fallback={<div className="p-6 text-sm">Loading…</div>}>
      <Investigate />
    </Suspense>
  );
}
