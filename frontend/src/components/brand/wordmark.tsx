import { cn } from "@/lib/utils";

/** Brand mark: three contour lines around a signal point — terrain read as data. */
export function BrandMark({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 32 32" fill="none" aria-hidden="true" className={cn("size-8", className)}>
      <rect
        x="0.5"
        y="0.5"
        width="31"
        height="31"
        rx="9"
        className="fill-card stroke-border-strong"
      />
      <path
        d="M7 20.5c2.4-6.8 9.6-10.6 17.5-8.6"
        className="stroke-foreground/30"
        strokeWidth="1.25"
        strokeLinecap="round"
      />
      <path
        d="M9.5 23.5c2-4.6 7.4-7.4 13-6.1"
        className="stroke-foreground/55"
        strokeWidth="1.25"
        strokeLinecap="round"
      />
      <path
        d="M12.5 26c1.5-2.6 4.4-4 7.4-3.4"
        className="stroke-foreground/80"
        strokeWidth="1.25"
        strokeLinecap="round"
      />
      <circle cx="22.5" cy="9.5" r="2.25" className="fill-primary" />
    </svg>
  );
}

export function Wordmark({ className }: { className?: string }) {
  return (
    <span className={cn("inline-flex items-center gap-2.5", className)}>
      <BrandMark />
      <span className="flex items-baseline gap-1.5">
        <span className="font-display text-[1.375rem] leading-none tracking-tight">Georgos</span>
        <span className="font-mono text-[0.625rem] uppercase tracking-[0.22em] text-muted-foreground">
          Map
        </span>
      </span>
    </span>
  );
}
