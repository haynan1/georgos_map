import { ArrowRight, LoaderCircle } from "lucide-react";
import type { ReactNode } from "react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

/** Full-width primary form action with an in-place busy state (no layout shift). */
export function SubmitButton({
  submitting,
  children,
  className,
}: {
  submitting: boolean;
  children: ReactNode;
  className?: string;
}) {
  return (
    <Button
      type="submit"
      size="xl"
      disabled={submitting}
      aria-busy={submitting}
      className={cn("group mt-2 w-full", className)}
    >
      {submitting ? (
        <>
          <LoaderCircle className="animate-spin" aria-hidden="true" />
          <span className="sr-only">Enviando…</span>
        </>
      ) : (
        <>
          {children}
          <ArrowRight
            aria-hidden="true"
            className="transition-transform duration-300 group-hover:translate-x-0.5"
          />
        </>
      )}
    </Button>
  );
}
