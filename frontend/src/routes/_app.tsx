import { createFileRoute, redirect } from "@tanstack/react-router";
import { sessionQuery } from "@/features/auth/session";
import { AppShell } from "@/features/shell/app-shell";

export const Route = createFileRoute("/_app")({
  beforeLoad: async ({ context, location }) => {
    const session = await context.queryClient.ensureQueryData(sessionQuery);
    if (!session) {
      throw redirect({ to: "/entrar", search: { redirect: location.href } });
    }
    return { session };
  },
  component: AppShell,
});
