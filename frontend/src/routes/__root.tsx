import type { QueryClient } from "@tanstack/react-query";
import { createRootRouteWithContext, HeadContent, Link, Outlet } from "@tanstack/react-router";
import { Wordmark } from "@/components/brand/wordmark";
import { Button } from "@/components/ui/button";
import { Toaster } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";

interface RouterContext {
  queryClient: QueryClient;
}

export const Route = createRootRouteWithContext<RouterContext>()({
  head: () => ({ meta: [{ title: "Georgos Map" }] }),
  component: RootLayout,
  notFoundComponent: NotFound,
});

function RootLayout() {
  return (
    <TooltipProvider delayDuration={300}>
      <HeadContent />
      <Outlet />
      <Toaster position="bottom-right" />
    </TooltipProvider>
  );
}

function NotFound() {
  return (
    <div className="flex min-h-dvh flex-col items-center justify-center gap-8 px-6 text-center">
      <Wordmark />
      <div>
        <p className="font-mono text-xs uppercase tracking-[0.24em] text-muted-foreground">
          Erro 404
        </p>
        <h1 className="mt-4 font-display text-5xl">Fora do mapa.</h1>
        <p className="mt-3 text-muted-foreground">Esta página não existe ou foi movida.</p>
      </div>
      <Button asChild size="lg">
        <Link to="/">Voltar ao início</Link>
      </Button>
    </div>
  );
}
