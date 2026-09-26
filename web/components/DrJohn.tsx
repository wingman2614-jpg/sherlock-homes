"use client";

// Dr. John — Sherlock's assistant. Answers from Sherlock's data [D#] and free
// web sources [W#]; every answer shows its sources and a fact check.
import { Fragment, useEffect, useRef, useState } from "react";
import { askDrJohn, type ChatReply } from "@/lib/api";
import { useMode } from "@/lib/mode";

type Msg = { role: "user"; content: string } | { role: "assistant"; content: string; reply?: ChatReply; error?: boolean };

const SUGGESTIONS = [
  "What does Sherlock Homes do?",
  "Which ZIP codes have the fastest-rising rents?",
  "Why was Allentown flagged?",
  "What is a building permit?",
  "Where can I find eviction data for Pittsburgh?",
];

function Monogram({ className = "h-9 w-9 text-sm" }: { className?: string }) {
  return (
    <span className={`inline-flex shrink-0 items-center justify-center rounded-full border-2 border-stroke bg-coral font-bold text-paper-raised ${className}`} aria-hidden>
      J
    </span>
  );
}

/** Render [D1]/[W2] tags as small superscript chips. */
function Cited({ text, onTag }: { text: string; onTag: (t: string) => void }) {
  const parts = text.split(/(\[[DW]\d+\])/g);
  return (
    <>
      {parts.map((p, i) => {
        const m = p.match(/^\[([DW]\d+)\]$/);
        if (!m) return <Fragment key={i}>{p}</Fragment>;
        return (
          <button key={i} onClick={() => onTag(m[1])} className={`mx-0.5 rounded-sm px-1 align-super text-[9px] font-semibold ${m[1][0] === "D" ? "bg-hunter text-hunter-ink" : "bg-brass-soft text-brass"}`}>
            {m[1]}
          </button>
        );
      })}
    </>
  );
}

function Reply({ m, onOpenCase }: { m: Extract<Msg, { role: "assistant" }>; onOpenCase?: (id: string) => void }) {
  const [open, setOpen] = useState(false);
  const [hl, setHl] = useState<string | null>(null);
  const r = m.reply;
  const used = r ? r.sources.filter((s) => m.content.includes(`[${s.tag}]`)) : [];
  const shown = open ? r?.sources ?? [] : used.length ? used : (r?.sources ?? []).slice(0, 3);
  return (
    <div className="flex gap-2">
      <Monogram className="mt-0.5 h-7 w-7 text-xs" />
      <div className="min-w-0 flex-1">
        <div className={`whitespace-pre-wrap rounded-sm border px-3 py-2 text-sm leading-relaxed ${m.error ? "border-oxblood bg-oxblood-soft text-oxblood" : "border-line bg-paper-raised"}`}>
          <Cited text={m.content} onTag={(t) => { setHl(t); setOpen(true); }} />
        </div>
        {r && (
          <div className="mt-1 space-y-1 text-[11px] text-ink-muted">
            {r.verification && !r.verification.ok && (
              <p className="rounded-sm bg-oxblood-soft px-2 py-1 text-oxblood">
                ⚠ Fact check:{" "}
                {r.verification.unmatched_numbers.length > 0 && `${r.verification.unmatched_numbers.join(", ")} not found in the sources. `}
                {r.verification.causal_language.length > 0 && `Uses cause-and-effect wording ("${r.verification.causal_language.join('", "')}") that the data can't prove.`}
              </p>
            )}
            {r.sources.length > 0 && (
              <div>
                <p className="case-stamp uppercase">Sources</p>
                <ul className="space-y-0.5">
                  {shown.map((s) => (
                    <li key={s.tag} className={`rounded-sm px-1 ${hl === s.tag ? "bg-brass-soft" : ""}`}>
                      <span className={`mr-1 font-semibold ${s.type === "data" ? "text-hunter" : "text-brass"}`}>[{s.tag}]</span>
                      {s.url ? (
                        <a href={s.url} target="_blank" rel="noreferrer" className="underline hover:text-oxblood">{s.title}</a>
                      ) : s.case_id && onOpenCase ? (
                        <button onClick={() => onOpenCase(s.case_id!)} className="underline hover:text-oxblood">{s.title}</button>
                      ) : (
                        <span>{s.title}</span>
                      )}
                      <span className="ml-1">{s.type === "data" ? "· Sherlock data" : "· web"}</span>
                    </li>
                  ))}
                </ul>
                {r.sources.length > shown.length && (
                  <button onClick={() => setOpen(true)} className="underline">show all {r.sources.length}</button>
                )}
              </div>
            )}
            <p>Answered by: {r.provider}{r.web ? ` · web: ${r.web}` : ""}{r.note ? ` · ${r.note}` : ""}</p>
          </div>
        )}
      </div>
    </div>
  );
}

export default function DrJohn({ caseId = null, onOpenCase }: { caseId?: string | null; onOpenCase?: (id: string) => void }) {
  const { mode } = useMode();
  const [open, setOpen] = useState(false);
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [q, setQ] = useState("");
  const [busy, setBusy] = useState(false);
  const [useWeb, setUseWeb] = useState(true);
  const end = useRef<HTMLDivElement>(null);

  useEffect(() => {
    end.current?.scrollIntoView({ behavior: "smooth" });
  }, [msgs, busy]);

  async function send(text: string) {
    const question = text.trim();
    if (!question || busy) return;
    const history = msgs.map((m) => ({ role: m.role, content: m.content }));
    setMsgs((p) => [...p, { role: "user", content: question }]);
    setQ("");
    setBusy(true);
    try {
      const reply = await askDrJohn(question, history, caseId, mode, useWeb);
      setMsgs((p) => [...p, { role: "assistant", content: reply.answer, reply }]);
    } catch (e) {
      setMsgs((p) => [
        ...p,
        { role: "assistant", error: true, content: `I can't reach the Sherlock API (${String(e)}). Start it with: uvicorn api.main:app --port 8000` },
      ]);
    }
    setBusy(false);
  }

  if (!open) {
    return (
      <button
        onClick={() => setOpen(true)}
        className="fixed bottom-5 right-5 z-40 flex items-center gap-2 rounded-full border-2 border-stroke bg-brass py-1.5 pl-1.5 pr-4 text-paper-raised hover:brightness-110"
        aria-label="Ask Dr. John"
      >
        <Monogram className="h-8 w-8 text-sm" />
        <span className="font-bold">Ask Dr. John</span>
      </button>
    );
  }

  return (
    <div className="dossier fixed bottom-5 right-5 z-40 flex h-[min(640px,80vh)] w-[min(420px,calc(100vw-2rem))] flex-col rounded-sm" role="dialog" aria-label="Dr. John">
      <header className="tweed flex items-center gap-3 px-3 py-2">
        <Monogram />
        <div className="flex-1 leading-tight">
          <p className="text-lg font-bold">Dr. John</p>
          <p className="text-xs font-medium text-ink-soft">Sherlock&apos;s assistant · data + web sources</p>
        </div>
        <button onClick={() => setOpen(false)} className="px-2 text-lg opacity-80 hover:opacity-100" aria-label="Close">×</button>
      </header>

      <div className="flex-1 space-y-3 overflow-y-auto p-3">
        {msgs.length === 0 && (
          <div className="text-sm">
            <p className="mb-2">
              Good day. Ask me anything about Pittsburgh housing or how Sherlock reached its conclusions. I answer from Sherlock&apos;s data
              <span className="mx-1 rounded-sm bg-hunter px-1 text-[9px] text-hunter-ink">D</span>
              and trusted web sources
              <span className="mx-1 rounded-sm bg-brass-soft px-1 text-[9px] text-brass">W</span>, and I show where every fact comes from.
            </p>
            {caseId && <p className="mb-2 text-xs text-ink-soft">I can see the case file you have open.</p>}
            <div className="flex flex-wrap gap-1.5">
              {SUGGESTIONS.map((s) => (
                <button key={s} onClick={() => send(s)} className="rounded-md border-2 border-stroke bg-paper px-2 py-1 text-xs text-ink-soft hover:border-oxblood hover:text-oxblood">
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}
        {msgs.map((m, i) =>
          m.role === "user" ? (
            <div key={i} className="ml-10 rounded-sm bg-hunter px-3 py-2 text-sm text-hunter-ink">{m.content}</div>
          ) : (
            <Reply key={i} m={m} onOpenCase={onOpenCase} />
          ),
        )}
        {busy && (
          <div className="flex items-center gap-2 text-sm text-ink-muted">
            <Monogram className="h-7 w-7 text-xs" /> <span className="case-stamp text-[11px] uppercase">Consulting the evidence…</span>
          </div>
        )}
        <div ref={end} />
      </div>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          send(q);
        }}
        className="border-t border-line p-2"
      >
        <div className="flex gap-2">
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Ask Dr. John…"
            className="min-w-0 flex-1 rounded-md border-2 border-stroke bg-paper px-3 py-2 text-sm outline-none focus:border-brass"
            aria-label="Your question"
          />
          <button disabled={busy || !q.trim()} className="btn-primary px-4 text-sm disabled:opacity-40">
            Ask
          </button>
        </div>
        <label className="mt-1 flex items-center gap-1.5 text-[11px] text-ink-muted">
          <input type="checkbox" checked={useWeb} onChange={(e) => setUseWeb(e.target.checked)} /> Also search the web (Wikipedia, DuckDuckGo, WPRDC)
        </label>
      </form>
    </div>
  );
}
