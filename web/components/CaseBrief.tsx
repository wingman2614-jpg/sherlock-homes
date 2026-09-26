"use client";

// "Quick brief": the case file in plain English for non-specialists.
import dynamic from "next/dynamic";
import { caseLabel } from "@/lib/format";
import { useMode } from "@/lib/mode";
import type { CaseFile } from "@/lib/types";
import { ConfidenceBadge, LevelBadge, Section } from "./ui";

const TimelineChart = dynamic(() => import("./TimelineChart"), { ssr: false });

export default function CaseBrief({ c, onOpenArea }: { c: CaseFile; onOpenArea: (areaId: string) => void }) {
  const { setMode } = useMode();
  const p = c.plain;
  const hasStory = p.bullets.length > 0;
  return (
    <article className="pb-10">
      <header className="pb-5">
        <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
          <span className="case-stamp text-xs uppercase text-ink-muted">
            {c.case_number ? `Case No. ${caseLabel(c)}` : c.geography === "zip" ? "ZIP code file" : "Neighborhood file"}
          </span>
          <LevelBadge level={c.level} stamp />
        </div>
        <h2 className="font-serif text-3xl font-bold leading-tight">{c.name}</h2>
        {c.case_number && <p className="mt-1 font-serif text-lg italic text-ink-soft">{c.title}</p>}
      </header>

      <div className="border-l-4 border-oxblood bg-paper-sunk px-4 py-3">
        <p className="case-stamp mb-1 text-[10px] uppercase text-oxblood">The short version</p>
        <p className="font-serif text-xl leading-snug">{p.headline}</p>
      </div>

      {hasStory && (
        <Section title="What Sherlock found" kicker="The clues">
          <ul className="space-y-3">
            {p.bullets.map((b) => (
              <li key={b} className="flex gap-3 leading-relaxed">
                <span className="mt-1 text-brass" aria-hidden>◆</span>
                <span>{b}</span>
              </li>
            ))}
          </ul>
        </Section>
      )}

      {p.market && (
        <Section title="The wider market" kicker="Homes & rents nearby">
          <p className="leading-relaxed">{p.market}</p>
          <p className="mt-1 text-xs text-ink-muted">ZIP-code level (Zillow and County sales records). ZIP codes don't match neighborhood borders.</p>
        </Section>
      )}

      {c.geography === "zip" && c.evidence.context.neighborhoods && c.evidence.context.neighborhoods.length > 0 && (
        <Section title="Neighborhoods in this ZIP" kicker="Where it is">
          <div className="flex flex-wrap gap-2">
            {c.evidence.context.neighborhoods.slice(0, 6).map((n) => (
              <button key={n.area_id} onClick={() => onOpenArea(n.area_id)} className="rounded-md border-2 border-stroke bg-paper-raised px-3 py-1.5 text-sm hover:border-oxblood hover:text-oxblood">
                {n.neighborhood}
              </button>
            ))}
          </div>
        </Section>
      )}

      {hasStory && (
        <Section title="How it changed over time" kicker="Timeline">
          <TimelineChart timeline={c.timeline} signals={c.evidence.signals} onsets={c.what_changed_first.ordered} simple expectedLabel={c.geography === "zip" ? "Typical county ZIP" : undefined} areaLabel={c.geography === "zip" ? "This ZIP code" : "This neighborhood"} />
          {p.timing && <p className="mt-3 text-sm text-ink-soft">{p.timing}</p>}
        </Section>
      )}

      <Section title="How sure are we?" kicker="Confidence">
        <div className="mb-2"><ConfidenceBadge level={c.confidence.level} /></div>
        <p className="text-sm leading-relaxed">{p.confidence}</p>
      </Section>

      <Section title="Keep in mind" kicker="Before you conclude">
        <ul className="space-y-1.5 text-sm text-ink-soft">
          {p.keep_in_mind.map((k) => <li key={k}>• {k}</li>)}
        </ul>
      </Section>

      {c.similar_cases.length > 0 && (
        <Section title="Places with a similar story" kicker="Related cases">
          <div className="flex flex-wrap gap-2">
            {c.similar_cases.slice(0, 3).map((s) => (
              <button
                key={s.area_id}
                onClick={() => onOpenArea(s.area_id)}
                className="rounded-md border-2 border-stroke bg-paper-raised px-3 py-1.5 text-sm hover:border-brass hover:text-oxblood"
              >
                {s.name}
              </button>
            ))}
          </div>
        </Section>
      )}

      <div className="mt-6 border-t-[3px] border-double border-line pt-5 text-center">
        <p className="mb-3 text-sm text-ink-soft">Want every number, source and method behind this?</p>
        <button
          onClick={() => setMode("detailed")}
          className="btn-primary border-2 border-stroke px-5 py-2.5 text-sm"
        >
          Open the full dossier
        </button>
      </div>
    </article>
  );
}
