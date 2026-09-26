"use client";

// Basic ("Quick Brief") vs In-depth ("Full Dossier") view, remembered per browser.
import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";

export type ViewMode = "basic" | "detailed";
const KEY = "sherlock-view-mode";

const ModeContext = createContext<{ mode: ViewMode; setMode: (m: ViewMode) => void }>({
  mode: "basic",
  setMode: () => {},
});

export function ModeProvider({ children }: { children: ReactNode }) {
  const [mode, setModeState] = useState<ViewMode>("basic");
  useEffect(() => {
    try {
      const saved = window.localStorage.getItem(KEY);
      if (saved === "basic" || saved === "detailed") setModeState(saved);
    } catch {
      /* storage unavailable: keep default */
    }
  }, []);
  const setMode = useCallback((m: ViewMode) => {
    setModeState(m);
    try {
      window.localStorage.setItem(KEY, m);
    } catch {
      /* ignore */
    }
  }, []);
  return <ModeContext.Provider value={{ mode, setMode }}>{children}</ModeContext.Provider>;
}

export const useMode = () => useContext(ModeContext);

/**
 * View switch. `size="lg"` is the big two-card switch used on the home page and
 * at the top of every case file; the default is the header version.
 */
export function ModeToggle({ size = "md" }: { size?: "md" | "lg" }) {
  const { mode, setMode } = useMode();
  if (size === "lg") {
    const card = (m: ViewMode, label: string, hint: string) => {
      const on = mode === m;
      return (
        <button
          type="button"
          onClick={() => setMode(m)}
          aria-pressed={on}
          className={`flex-1 rounded-md border-2 border-[var(--stroke)] px-4 py-3 text-left transition ${
            on ? "bg-[var(--brass)] text-[#fffffe]" : "bg-[var(--paper-raised)] text-[var(--ink)] hover:bg-[var(--paper-sunk)]"
          }`}
        >
          <span className="flex items-center gap-2 font-serif text-lg font-bold">
            <span aria-hidden className={`inline-block h-4 w-4 rounded-full border-2 ${on ? "border-[#fffffe] bg-[var(--coral)]" : "border-[var(--stroke)]"}`} />
            {label}
          </span>
          <span className={`mt-0.5 block text-xs ${on ? "text-[#fffffe]" : "text-[var(--ink-soft)]"}`}>{hint}</span>
        </button>
      );
    };
    return (
      <div role="group" aria-label="Choose view" className="flex gap-3">
        {card("basic", "Quick brief", "Plain English, one chart")}
        {card("detailed", "Full dossier", "Every number, source and method")}
      </div>
    );
  }
  const opt = (m: ViewMode, label: string, hint: string) => (
    <button
      type="button"
      onClick={() => setMode(m)}
      aria-pressed={mode === m}
      title={hint}
      className={`case-stamp px-4 py-2 text-xs uppercase transition ${
        mode === m ? "bg-[var(--ink)] text-[var(--paper-raised)]" : "text-[var(--ink)] hover:bg-[var(--paper-sunk)]"
      }`}
    >
      {mode === m ? "● " : "○ "}
      {label}
    </button>
  );
  return (
    <div className="flex items-center gap-2">
      <span className="case-stamp hidden text-[11px] uppercase text-[var(--ink-soft)] sm:inline">View:</span>
      <div className="inline-flex overflow-hidden rounded-md border-2 border-[var(--stroke)] bg-[var(--paper-raised)]" role="group" aria-label="View mode">
        {opt("basic", "Quick brief", "Plain-English summary for everyone")}
        {opt("detailed", "Full dossier", "All evidence, statistics and sources")}
      </div>
    </div>
  );
}
