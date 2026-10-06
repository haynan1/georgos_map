import { createFileRoute, Outlet, redirect } from "@tanstack/react-router";
import { AuthLayout } from "@/features/auth/auth-layout";
import { sessionQuery } from "@/features/auth/session";

export const Route = createFileRoute("/_auth")({
  beforeLoad: async ({ context }) => {
    if (await context.queryClient.ensureQueryData(sessionQuery)) {
      throw redirect({ to: "/" });
    }
  },
  component: () => (
    <AuthLayout>
      <Outlet />
    </AuthLayout>
  ),
});
