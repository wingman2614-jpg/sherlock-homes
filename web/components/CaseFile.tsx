"use client";

import dynamic from "next/dynamic";
import { useEffect, useState } from "react";
import { explainCase, isOffline } from "@/lib/api";
import { caseLabel, compWord, num, pct, signed, value } from "@/lib/format";
import { AcsEvidence, MarketEvidence } from "./MarketEvidence";
import type { CaseFile as CaseFileT } from "@/lib/types";
import { useMode } from "@/lib/mode";
import CaseBrief from "./CaseBrief";
import { ConflictCard } from "./Conflicts";
import EvidencePanel from "./EvidencePanel";
import { ActionButton, ConfidenceBadge, LevelBadge, Pill, Section } from "./ui";

const TimelineChart = dynamic(() => import("./TimelineChart"), { ssr: false });

export default function CaseFile(props: { c: CaseFileT; onOpenArea: (areaId: string) => void }) {
  const { mode } = useMode();
  return mode === "basic" ? <CaseBrief {...props} /> : <FullDossier {...props} />;
}

function FullDossier({ c, onOpenArea }: { c: CaseFileT; onOpenArea: (areaId: string) => void }) {
  const [showFirst, setShowFirst] = useState(false);
  const [showSimilar, setShowSimilar] = useState(false);
  const [showNational, setShowNational] = useState(false);
  const [finding, setFinding] = useState(c.finding);
  const [explaining, setExplaining] = useState(false);

  useEffect(() => {
    setShowFirst(false);
    setShowSimilar(false);
    setShowNational(false);
    setFinding(c.finding);
  }, [c]);

  const top = c.why_noticed[0];
  const cw = compWord(c.geography);
  const scored = c.evidence.signals.filter((s) => s.status === "scored");
  const wcf = c.what_changed_first;
  const conflictCount =
    c.conflicting_evidence.neighborhood.length +
    c.conflicting_evidence.citywide_and_regional.filter((x) => x.status !== "agree").length;

  async function rephrase() {
    setExplaining(true);
    const r = await explainCase(c.id);
    if (r) setFinding(r);
    setExplaining(false);
  }

  return (
    <article className="pb-10">
      {/* header */}
      <header className="pb-4">
        <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
          <span className="case-stamp text-xs uppercase text-ink-muted">
            {c.case_number ? `Case No. ${caseLabel(c)}` : c.geography === "zip" ? "ZIP file" : "Area file"} · Full dossier
          </span>
          <div className="flex items-center gap-2">
            <ConfidenceBadge level={c.confidence.level} />
            <LevelBadge level={c.level} long stamp />
          </div>
        </div>
        <h2 className="font-serif text-3xl font-bold leading-tight">{c.title}</h2>
        <p className="mt-1 text-sm text-ink-soft">
          <span className="case-stamp text-[11px] uppercase text-ink-muted">Location:</span> {c.name} · <span className="text-ink-muted">{c.geography_note}</span>
        </p>
      </header>

      <Section title="Why Sherlock noticed" kicker="Leads">
        {c.why_noticed.length === 0 ? (
          <p className="text-sm text-ink-soft">No scored indicator departs strongly (|z| ≥ 1) from the citywide pattern here.</p>
        ) : (
          <table className="tabular w-full text-sm">
            <tbody>
              {c.why_noticed.map((w) => (
                <tr key={w.indicator} className="border-b border-line last:border-0">
                  <td className="py-1.5 pr-2">{w.short}</td>
                  <td className="py-1.5 text-right font-semibold">{w.change_pct !== null ? pct(w.change_pct) : `${num(w.baseline_value)} → ${num(w.recent_value)}`}</td>
                  <td className="py-1.5 pl-3 text-right text-xs text-ink-muted">{cw} {pct(w.city_change_pct)}</td>
                  <td className="py-1.5 pl-3 text-right"><Pill tone={Math.abs(w.z_score) >= 2 ? "warn" : "neutral"}>z {signed(w.z_score)}</Pill></td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Section>

      {top && (
        <Section title={c.geography === "zip" ? "County comparison" : "City comparison"} kicker="Leads">
          <div className="grid grid-cols-3 gap-3 text-center">
            <div className="rounded-md border-2 border-stroke bg-paper-sunk p-3">
              <p className="text-[10px] uppercase tracking-wider text-ink-muted">{c.geography === "zip" ? "Typical county ZIP" : "Typical (citywide)"}</p>
              <p className="tabular font-serif text-2xl font-semibold">{pct(top.city_change_pct)}</p>
            </div>
            <div className="rounded-md border-2 border-stroke bg-paper-sunk p-3">
              <p className="text-[10px] uppercase tracking-wider text-ink-muted">This area</p>
              <p className="tabular font-serif text-2xl font-semibold">{top.change_pct !== null ? pct(top.change_pct) : `${num(top.baseline_value)}→${num(top.recent_value)}`}</p>
            </div>
            <div className="rounded-md border-2 border-stroke bg-paper-sunk p-3">
              <p className="text-[10px] uppercase tracking-wider text-ink-muted">{`Expected at ${cw} trend`}</p>
              <p className="tabular font-serif text-2xl font-semibold">
                {value(c.evidence.signals.find((s) => s.indicator === top.indicator)?.unit ?? "", top.expected_recent)}
              </p>
            </div>
          </div>
          <p className="mt-2 text-xs text-ink-soft">
            {top.label}, {top.period}. Observed {value(c.evidence.signals.find((s) => s.indicator === top.indicator)?.unit ?? "", top.recent_value)}. Source: {top.source} ({top.geography} level).
          </p>
        </Section>
      )}

      <Section title="Unusualness" kicker="Anomaly score">
        <div className="flex items-center gap-3">
          <LevelBadge level={c.level} />
          <span className="tabular text-sm">score {c.anomaly_score !== null ? c.anomaly_score.toFixed(2) : "n/a"}</span>
          <span className="text-xs text-ink-muted">= root-mean-square of {scored.length} indicator z-scores ({scored.map((s) => `${s.short} ${signed(s.z_score)}`).join(", ")})</span>
        </div>
        <p className="mt-2 text-xs text-ink-muted">
          High means this neighborhood differs meaningfully from its comparison pattern — not that the change is good or bad.
        </p>
      </Section>

      <Section
        title="Sherlock's finding"
        kicker="Finding"
        action={!isOffline() && <button onClick={rephrase} disabled={explaining} className="case-stamp text-[11px] uppercase text-oxblood hover:underline disabled:opacity-50">{explaining ? "Rephrasing…" : "Rephrase with AI"}</button>}
      >
        <div className="space-y-3 text-sm leading-relaxed">
          {finding.text.split("\n\n").map((p, i) => <p key={i}>{p}</p>)}
        </div>
        <p className="mt-2 text-[10px] text-ink-muted">Generated by: {finding.generated_by}{finding.llm_status && finding.llm_status !== "ok" ? ` · AI: ${finding.llm_status}` : ""}</p>
      </Section>

      <Section title="Examine evidence" kicker="Evidence">
        <EvidencePanel c={c} />
      </Section>

      {c.evidence.context.zip_market && (
        <Section title="The wider market" kicker="ZIP-code evidence">
          <MarketEvidence m={c.evidence.context.zip_market} onOpen={onOpenArea} />
        </Section>
      )}

      {c.evidence.context.neighborhoods && c.evidence.context.neighborhoods.length > 0 && (
        <Section title="Neighborhoods in this ZIP" kicker="Where it overlaps">
          <div className="flex flex-wrap gap-2">
            {c.evidence.context.neighborhoods.map((n) => (
              <button key={n.area_id} onClick={() => onOpenArea(n.area_id)} className="rounded-md border-2 border-stroke bg-paper px-2.5 py-1 text-xs hover:border-oxblood">
                {n.neighborhood} <span className="text-ink-muted">· {Math.round(n.share_of_zip_land * 100)}% of ZIP</span>
              </button>
            ))}
          </div>
          <p className="mt-2 text-[11px] text-ink-muted">Share of the ZIP's land (Allegheny County part) inside each City of Pittsburgh neighborhood.</p>
        </Section>
      )}

      {c.evidence.context.acs && (
        <Section title="Census estimates (ACS)" kicker="Tract-level evidence">
          <AcsEvidence a={c.evidence.context.acs} />
        </Section>
      )}

      <Section
        title="Case timeline"
        kicker="Timeline"
        action={<ActionButton onClick={() => setShowFirst((v) => !v)} active={showFirst}>What changed first?</ActionButton>}
      >
        {showFirst && (
          <div className="mb-4 border-l-4 border-oxblood bg-paper-sunk p-3 text-sm">
            {wcf.ordered.length === 0 ? (
              <p>No indicator clearly departed from its 2020–21 share of city activity during 2022–2025.</p>
            ) : (
              <ol className="space-y-2">
                {wcf.ordered.map((o) => (
                  <li key={o.indicator} className="flex gap-3">
                    <span className="case-stamp mt-0.5 font-semibold text-brass">{o.year}</span>
                    <span>
                      <span className="font-semibold">{o.order}. {o.short} {o.direction === "up" ? "rose above" : "fell below"} its earlier share</span>
                      <br />
                      <span className="text-xs text-ink-soft">{o.statement}</span>
                    </span>
                  </li>
                ))}
              </ol>
            )}
            {wcf.no_clear_change.length > 0 && (
              <p className="mt-2 text-xs text-ink-soft">No clear departure: {wcf.no_clear_change.map((o) => o.short).join(", ")}.</p>
            )}
            <p className="mt-3 text-xs font-semibold">⚠ {wcf.caution}</p>
            <details className="mt-1 text-[11px] text-ink-muted"><summary className="cursor-pointer">How timing is detected</summary>{wcf.method}</details>
          </div>
        )}
        <TimelineChart timeline={c.timeline} signals={c.evidence.signals} onsets={wcf.ordered} expectedLabel={c.timeline_expected_label} areaLabel={c.geography === "zip" ? "This ZIP code" : "This neighborhood"} />
      </Section>

      <Section
        title="Similar cases"
        kicker="Pattern match"
        action={<ActionButton onClick={() => setShowSimilar((v) => !v)} active={showSimilar}>Find similar cases</ActionButton>}
      >
        {!showSimilar ? (
          <p className="text-xs text-ink-muted">Compares this neighborhood's pattern of change with all others.</p>
        ) : c.similar_cases.length === 0 ? (
          <p className="text-sm text-ink-soft">Not enough scored indicators to compare this neighborhood reliably (needs at least 3).</p>
        ) : (
          <ul className="space-y-2">
            {c.similar_cases.map((s) => (
              <li key={s.area_id} className="rounded-md border-2 border-stroke bg-paper p-3 text-sm">
                <div className="flex items-baseline justify-between">
                  <button className="font-serif font-semibold text-ink hover:text-oxblood hover:underline" onClick={() => onOpenArea(s.area_id)}>{s.name}</button>
                  <span className="tabular text-xs">Similarity <strong>{Math.round(s.similarity * 100)}%</strong> · {s.features_compared} features</span>
                </div>
                <ul className="mt-1 text-xs text-ink-soft">
                  {s.shared.map((x) => <li key={x.indicator}>✓ {x.text}</li>)}
                  {s.differences.map((x) => <li key={x.indicator} className="text-ink-muted">≠ {x.text}</li>)}
                  {s.shared.length === 0 && <li>Similar overall direction of change, but no single indicator is strongly shared.</li>}
                </ul>
              </li>
            ))}
            <li className="text-[11px] text-ink-muted">Similarity = cosine similarity of standardised change signals (z-scores, clipped at ±4) on features both areas have.</li>
          </ul>
        )}
      </Section>

      <Section title="Conflicting evidence" kicker={conflictCount ? `${conflictCount} to review` : "Cross-checks"}>
        <div className="space-y-3">
          {c.conflicting_evidence.neighborhood.map((x) => <ConflictCard key={x.id} c={x} />)}
          {c.conflicting_evidence.citywide_and_regional.map((x) => <ConflictCard key={x.id} c={x} />)}
          <p className="text-[11px] text-ink-muted">{c.conflicting_evidence.note}</p>
          <button className="text-xs text-brass hover:underline" onClick={() => setShowNational((v) => !v)}>
            {showNational ? "Hide" : "Show"} national source cross-checks (Zillow vs Redfin, {c.conflicting_evidence.national.length})
          </button>
          {showNational && c.conflicting_evidence.national.map((x) => <ConflictCard key={x.id} c={x} />)}
        </div>
      </Section>

      <Section title="Data confidence" kicker="Confidence">
        <div className="mb-2"><ConfidenceBadge level={c.confidence.level} /></div>
        <ul className="space-y-1 text-sm">
          {c.confidence.factors.map((f) => (
            <li key={f.factor} className="flex gap-2">
              <Pill tone={f.severity === "minor" ? "neutral" : "warn"}>{f.severity}</Pill>
              <span><strong>{f.factor}.</strong> <span className="text-ink-soft">{f.detail}</span></span>
            </li>
          ))}
        </ul>
        <p className="mt-2 text-[11px] text-ink-muted">Rule: {c.confidence.rule}</p>
      </Section>

      <Section title="What Sherlock doesn't know" kicker="Open questions">
        <ul className="space-y-1 text-sm text-ink-soft">
          {c.limitations.map((l) => <li key={l}>• {l}</li>)}
        </ul>
      </Section>
    </article>
  );
}
