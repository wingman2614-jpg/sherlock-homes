import Link from "next/link";

export function Magnifier({ className = "h-6 w-6" }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} className={className} aria-hidden>
      <circle cx="10" cy="10" r="6.5" />
      <circle cx="10" cy="10" r="4.2" strokeWidth={0.8} opacity={0.6} />
      <path d="M15 15l6 6" strokeLinecap="round" strokeWidth={2.6} />
    </svg>
  );
}

/** Wordmark. (`onDark` kept for compatibility; the header is light now.) */
export function Brand({ compact = false, onDark = false }: { compact?: boolean; onDark?: boolean }) {
  return (
    <Link href="/" className="flex items-center gap-2 text-ink" aria-label="Sherlock Homes home" data-dark={onDark || undefined}>
      <span className={`inline-flex items-center justify-center rounded-full border-2 border-stroke bg-brass text-paper-raised ${compact ? "h-7 w-7" : "h-9 w-9"}`}>
        <Magnifier className={compact ? "h-4 w-4" : "h-5 w-5"} />
      </span>
      <span className="leading-none">
        <span className={`flex items-center gap-1.5 font-serif font-bold tracking-tight ${compact ? "text-lg" : "text-2xl"}`}>
          Sherlock Homes
        </span>
        {!compact && <span className="block text-xs font-medium text-ink-soft">Pittsburgh housing, investigated</span>}
      </span>
    </Link>
  );
}
