import type { ReactNode } from "react";
import { FieldMap } from "@/components/brand/field-map";
import { Wordmark } from "@/components/brand/wordmark";

export function AuthLayout({ children }: { children: ReactNode }) {
  return (
    <div className="grid min-h-dvh lg:grid-cols-[minmax(0,1.1fr)_minmax(0,1fr)]">
      <aside className="relative hidden flex-col justify-between overflow-hidden border-r bg-sidebar p-10 lg:flex xl:p-14">
        <FieldMap className="absolute inset-0 size-full" />
        <div className="relative">
          <Wordmark />
        </div>
        <div className="relative max-w-xl">
          <p className="font-mono text-[0.6875rem] uppercase tracking-[0.24em] text-muted-foreground">
            Gestão de frota agrícola
          </p>
          <h2 className="mt-5 font-display text-[clamp(3rem,4.6vw,4.5rem)] leading-[0.95] tracking-[-0.01em] text-balance">
            A frota inteira, <em className="text-primary">lida como um mapa.</em>
          </h2>
          <p className="mt-6 max-w-md text-[0.9375rem] leading-relaxed text-muted-foreground">
            Máquinas, manutenção e operação da sua empresa em um só lugar — com o acesso de cada
            pessoa da equipe sob o seu controle.
          </p>
          <p className="mt-10 border-t pt-5 font-mono text-[0.6875rem] tracking-[0.12em] text-subtle-foreground">
            <span lang="el">γεωργός</span> — aquele que trabalha a terra
          </p>
        </div>
      </aside>

      <main className="flex min-h-dvh flex-col px-6 py-8 sm:px-12">
        <header className="lg:hidden">
          <Wordmark />
        </header>
        <div className="flex flex-1 items-center justify-center py-12">
          <div className="w-full max-w-[24rem] animate-rise">{children}</div>
        </div>
        <footer className="text-center font-mono text-[0.6875rem] tracking-wide text-subtle-foreground lg:text-left">
          © {new Date().getFullYear()} Georgos Map
        </footer>
      </main>
    </div>
  );
}

export function AuthHeading({ title, description }: { title: ReactNode; description: ReactNode }) {
  return (
    <div className="mb-8">
      <h1 className="font-display text-[2.75rem] leading-none tracking-[-0.01em]">{title}</h1>
      <p className="mt-3 text-[0.9375rem] leading-relaxed text-muted-foreground">{description}</p>
    </div>
  );
}
