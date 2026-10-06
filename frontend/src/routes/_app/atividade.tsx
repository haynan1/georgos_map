import { useInfiniteQuery, useQuery } from "@tanstack/react-query";
import { createFileRoute, redirect } from "@tanstack/react-router";
import { History } from "lucide-react";
import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { hasPermission, sessionQuery, useSession } from "@/features/auth/session";
import { ActivityFeed } from "@/features/organization/activity-feed";
import { auditQuery, membersQuery } from "@/features/organization/queries";

export const Route = createFileRoute("/_app/atividade")({
  beforeLoad: async ({ context }) => {
    const session = await context.queryClient.ensureQueryData(sessionQuery);
    if (!session || !hasPermission(session, "audit:read")) throw redirect({ to: "/" });
  },
  head: () => ({ meta: [{ title: "Atividade · Georgos Map" }] }),
  component: ActivityPage,
});

function ActivityPage() {
  const session = useSession();
  const audit = useInfiniteQuery(auditQuery(session.organization.id));
  const members = useQuery(membersQuery(session.organization.id));
  const events = audit.data?.pages.flat() ?? [];

  return (
    <>
      <PageHeader
        eyebrow={session.organization.name}
        title="Atividade"
        description="Registro permanente das ações de segurança e administração da empresa. Ninguém — nem administradores — pode editá-lo."
      />
      <div className="rounded-xl border bg-card p-6 sm:p-8">
        {audit.isPending ? (
          <div className="space-y-6">
            {[0, 1, 2, 3, 4].map((row) => (
              <Skeleton key={row} className="h-9 w-full" />
            ))}
          </div>
        ) : events.length === 0 ? (
          <div className="flex flex-col items-center py-12 text-center">
            <History className="size-6 text-muted-foreground" aria-hidden="true" />
            <p className="mt-4 font-medium">Nenhuma atividade ainda</p>
          </div>
        ) : (
          <ActivityFeed events={events} members={members.data} showIp />
        )}
      </div>
      {audit.hasNextPage && (
        <div className="mt-6 flex justify-center">
          <Button
            variant="outline"
            onClick={() => void audit.fetchNextPage()}
            disabled={audit.isFetchingNextPage}
          >
            {audit.isFetchingNextPage ? "Carregando…" : "Carregar mais"}
          </Button>
        </div>
      )}
    </>
  );
}
