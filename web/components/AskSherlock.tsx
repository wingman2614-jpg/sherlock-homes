"use client";

import { useState } from "react";
import { investigate } from "@/lib/api";
import { useMode } from "@/lib/mode";
import type { InvestigateResult } from "@/lib/types";
import { Magnifier } from "./Brand";
import { LevelBadge } from "./ui";

const EXAMPLES = [
  "Where did housing supply increase the most?",
  "Where are demolitions rising but renovations falling?",
  "Which areas resemble Garfield?",
  "Where are rents rising faster than incomes?",
];

export default function AskSherlock({ onOpen }: { onOpen: (caseId: string) => void }) {
  const [q, setQ] = useState("");
  const [res, setRes] = useState<InvestigateResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [open, setOpen] = useState(false);
  const { mode } = useMode();
  const basic = mode === "basic";

  async function ask(question: string) {
    if (!question.trim()) return;
    setQ(question);
    setBusy(true);
    setOpen(true);
    try {
      setRes(await investigate(question));
    } catch (e) {
      setRes({ question, results: [], message: String(e) });
    }
    setBusy(false);
  }

  return (
    <div className="relative w-full max-w-xl">
      <form
        onSubmit={(e) => {
          e.preventDefault();
          ask(q);
        }}
        className="flex items-center gap-2 rounded-md border-2 border-stroke bg-paper-raised px-3 py-1.5 text-ink focus-within:ring-1 focus-within:ring-brass"
      >
        <Magnifier className="h-4 w-4 text-ink-muted" />
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          onFocus={() => setOpen(true)}
          placeholder="Ask Sherlock… e.g. where are demolitions rising?"
          className="w-full bg-transparent text-sm outline-none placeholder:text-ink-muted"
          aria-label="Ask Sherlock a question"
        />
        {busy && <span className="text-xs text-ink-muted">…</span>}
      </form>
      {open && (
        <div className="dossier absolute left-0 right-0 top-full z-30 mt-1 max-h-[70vh] overflow-auto rounded-sm p-3 text-sm text-ink">
          <div className="mb-2 flex justify-between">
            <span className="case-stamp text-[10px] uppercase text-oxblood">{res ? "Leads" : "Try asking"}</span>
            <button className="text-xs text-ink-muted hover:text-ink" onClick={() => setOpen(false)}>Close</button>
          </div>
          {!res && (
            <ul className="space-y-1">
              {EXAMPLES.map((e) => (
                <li key={e}><button className="text-left text-ink-soft hover:text-oxblood" onClick={() => ask(e)}>{e}</button></li>
              ))}
            </ul>
          )}
          {res && (
            <div>
              {res.interpretation && (
                <p className="mb-2 text-xs text-ink-soft">
                  <span className="font-semibold">Sherlock searched for:</span>{" "}
                  {basic ? res.interpretation.replace(/\s*\(\|z\|[^)]*\)/, "").replace(/ \(2023–25 vs 2020–22\)/g, "") : res.interpretation}
                </p>
              )}
              {res.notes?.map((n) => <p key={n} className="mb-2 rounded-sm bg-oxblood-soft p-2 text-xs text-oxblood">{n}</p>)}
              {res.message && <p className="mb-2 text-xs text-ink-soft">{res.message}</p>}
              <ul className="divide-y divide-line">
                {res.results.map((r) => (
                  <li key={r.area_id} className="py-2">
                    <button
                      className="flex w-full items-center justify-between text-left font-semibold hover:text-oxblood"
                      onClick={() => {
                        onOpen(r.case_id);
                        setOpen(false);
                      }}
                    >
                      {r.name} {r.level && <LevelBadge level={r.level} />}
                    </button>
                    <ul className="tabular text-xs text-ink-soft">{r.evidence.map((e) => <li key={e}>{e}</li>)}</ul>
                  </li>
                ))}
              </ul>
              {res.results.length === 0 && !res.message && <p className="text-xs text-ink-muted">No neighborhoods match.</p>}
              {res.total_matches !== undefined && res.total_matches > res.results.length && (
                <p className="mt-1 text-xs text-ink-muted">Showing {res.results.length} of {res.total_matches}.</p>
              )}
              {res.caution && <p className="mt-2 text-[11px] text-ink-muted">{res.caution}{basic ? "" : ` ${res.method ?? ""}`}</p>}
              <button className="mt-2 text-xs text-brass hover:underline" onClick={() => setRes(null)}>Other examples</button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
