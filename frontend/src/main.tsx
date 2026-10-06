import "@fontsource-variable/geist";
import "@fontsource-variable/geist-mono";
import "@fontsource/instrument-serif/400.css";
import "@fontsource/instrument-serif/400-italic.css";
import "./styles/globals.css";

import { MutationCache, QueryCache, QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createRouter, RouterProvider } from "@tanstack/react-router";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { applySession } from "@/features/auth/session";
import { ApiError } from "@/lib/api/client";
import { routeTree } from "./routeTree.gen";

function onApiError(error: unknown) {
  // A session can end at any moment (expired, revoked from another device, membership
  // removed). Any request that discovers it sends the user back to sign-in.
  if (error instanceof ApiError && error.code === "not_authenticated") {
    applySession(queryClient, null);
    void router.navigate({ to: "/entrar", search: { redirect: router.state.location.href } });
  }
}

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: (failures, error) =>
        !(error instanceof ApiError && error.status > 0 && error.status < 500) && failures < 2,
    },
  },
  queryCache: new QueryCache({ onError: onApiError }),
  mutationCache: new MutationCache({ onError: onApiError }),
});

const router = createRouter({
  routeTree,
  context: { queryClient },
  defaultPreload: "intent",
  defaultPreloadStaleTime: 0,
  scrollRestoration: true,
});

declare module "@tanstack/react-router" {
  interface Register {
    router: typeof router;
  }
}

const container = document.getElementById("root");
if (!container) throw new Error("#root element missing from index.html");

createRoot(container).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>
  </StrictMode>,
);
