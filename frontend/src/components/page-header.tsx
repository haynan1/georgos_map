import type { ReactNode } from "react";

export function PageHeader({
  eyebrow,
  title,
  description,
  actions,
}: {
  eyebrow?: ReactNode;
  title: ReactNode;
  description?: ReactNode;
  actions?: ReactNode;
}) {
  return (
    <header className="mb-10 flex flex-col gap-6 border-b pb-8 sm:flex-row sm:items-end sm:justify-between">
      <div className="max-w-2xl animate-rise">
        {eyebrow && (
          <p className="mb-3 font-mono text-[0.6875rem] uppercase tracking-[0.24em] text-muted-foreground">
            {eyebrow}
          </p>
        )}
        <h1 className="font-display text-[clamp(2.5rem,5vw,3.5rem)] leading-[0.95] tracking-[-0.01em] text-balance">
          {title}
        </h1>
        {description && (
          <p className="mt-4 text-[0.9375rem] leading-relaxed text-muted-foreground">
            {description}
          </p>
        )}
      </div>
      {actions && <div className="flex shrink-0 gap-2">{actions}</div>}
    </header>
  );
}

export function Section({
  title,
  description,
  actions,
  children,
}: {
  title: ReactNode;
  description?: ReactNode;
  actions?: ReactNode;
  children: ReactNode;
}) {
  return (
    <section className="mb-14">
      <div className="mb-5 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h2 className="text-base font-semibold tracking-tight">{title}</h2>
          {description && <p className="mt-1 text-sm text-muted-foreground">{description}</p>}
        </div>
        {actions}
      </div>
      {children}
    </section>
  );
}
