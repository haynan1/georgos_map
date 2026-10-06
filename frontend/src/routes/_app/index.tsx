import { useInfiniteQuery, useQuery } from "@tanstack/react-query";
import { createFileRoute, Link } from "@tanstack/react-router";
import { ArrowUpRight, MonitorSmartphone, ShieldCheck, UserPlus, Users } from "lucide-react";
import type { ReactNode } from "react";
import { PageHeader, Section } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { ROLE_DESCRIPTION, ROLE_LABEL } from "@/features/auth/roles";
import { hasPermission, useSession } from "@/features/auth/session";
import { ActivityFeed } from "@/features/organization/activity-feed";
import {
  activeSessionsQuery,
  auditQuery,
  invitationsQuery,
  membersQuery,
} from "@/features/organization/queries";
import { firstName } from "@/lib/format";

export const Route = createFileRoute("/_app/")({
  head: () => ({ meta: [{ title: "Visão geral · Georgos Map" }] }),
  component: OverviewPage,
});

function greeting(date = new Date()): string {
  const hour = date.getHours();
  if (hour < 5) return "Boa noite";
  if (hour < 12) return "Bom dia";
  if (hour < 18) return "Boa tarde";
  return "Boa noite";
}

function OverviewPage() {
  const session = useSession();
  const orgId = session.organization.id;
  const canReadMembers = hasPermission(session, "members:read");
  const canManage = hasPermission(session, "members:manage");
  const canAudit = hasPermission(session, "audit:read");

  const members = useQuery({ ...membersQuery(orgId), enabled: canReadMembers });
  const invitations = useQuery({ ...invitationsQuery(orgId), enabled: canManage });
  const sessions = useQuery(activeSessionsQuery);
  const audit = useInfiniteQuery({ ...auditQuery(orgId, 6), enabled: canAudit });

  const teamSize = members.data?.length;
  const pending = invitations.data?.length ?? 0;
  const soloOwner = canManage && teamSize === 1 && pending === 0;

  return (
    <>
      <PageHeader
        eyebrow={session.organization.name}
        title={
          <>
            {greeting()}, <em className="text-primary">{firstName(session.user.full_name)}.</em>
          </>
        }
        description={`Você acessa esta empresa como ${ROLE_LABEL[session.role].toLowerCase()}. ${ROLE_DESCRIPTION[session.role]}`}
      />

      {soloOwner && (
        <div className="mb-10 flex flex-col gap-5 rounded-xl border border-primary/25 bg-primary/[0.04] p-6 sm:flex-row sm:items-center sm:justify-between animate-rise">
          <div>
            <p className="font-medium">Traga sua equipe para o Georgos</p>
            <p className="mt-1 text-sm text-muted-foreground">
              Convide operadores, gestores e técnicos. Cada pessoa recebe só o acesso que o papel
              dela permite.
            </p>
          </div>
          <Button asChild size="lg">
            <Link to="/equipe" search={{ convidar: true }}>
              <UserPlus aria-hidden="true" />
              Convidar pessoas
            </Link>
          </Button>
        </div>
      )}

      <div className="mb-14 grid auto-cols-fr gap-px overflow-hidden rounded-xl border bg-border sm:grid-flow-col">
        {canReadMembers && (
          <Stat
            to="/equipe"
            icon={<Users aria-hidden="true" />}
            label="Equipe"
            value={teamSize}
            detail={
              pending > 0
                ? `${pending} ${pending === 1 ? "convite pendente" : "convites pendentes"}`
                : "pessoas com acesso"
            }
          />
        )}
        <Stat
          to="/seguranca"
          icon={<MonitorSmartphone aria-hidden="true" />}
          label="Sessões ativas"
          value={sessions.data?.length}
          detail="dispositivos conectados à sua conta"
        />
        <Stat
          icon={<ShieldCheck aria-hidden="true" />}
          label="Seu acesso"
          value={session.permissions.length}
          detail={`permissões como ${ROLE_LABEL[session.role].toLowerCase()}`}
        />
      </div>

      {canAudit && (
        <Section
          title="Atividade recente"
          description="O que aconteceu na empresa, em ordem cronológica."
          actions={
            <Button asChild variant="ghost" size="sm">
              <Link to="/atividade">
                Ver tudo
                <ArrowUpRight aria-hidden="true" />
              </Link>
            </Button>
          }
        >
          <div className="rounded-xl border bg-card p-6">
            {audit.data ? (
              <ActivityFeed events={audit.data.pages[0] ?? []} members={members.data} />
            ) : (
              <div className="space-y-5">
                {[0, 1, 2].map((row) => (
                  <Skeleton key={row} className="h-9 w-full" />
                ))}
              </div>
            )}
          </div>
        </Section>
      )}
    </>
  );
}

interface StatProps {
  to?: "/equipe" | "/seguranca";
  icon: ReactNode;
  label: string;
  value: number | undefined;
  detail: string;
}

/** Metric tile. Linked tiles navigate to the screen where the number can be acted on. */
function Stat({ to, icon, label, value, detail }: StatProps) {
  const body = (
    <>
      <span className="flex items-center justify-between text-sm text-muted-foreground">
        <span className="flex items-center gap-2">
          {icon}
          {label}
        </span>
        {to && (
          <ArrowUpRight
            aria-hidden="true"
            className="opacity-0 transition-opacity group-hover:opacity-100"
          />
        )}
      </span>
      <span>
        {value === undefined ? (
          <Skeleton className="h-10 w-12" />
        ) : (
          <span className="block text-[2.75rem] font-medium leading-none tracking-[-0.03em] tabular">
            {value}
          </span>
        )}
        <span className="mt-2 block text-sm text-muted-foreground">{detail}</span>
      </span>
    </>
  );
  const tile = "flex flex-col gap-6 bg-card p-6 [&_svg]:size-4";
  return to ? (
    <Link to={to} className={`group ${tile} transition-colors hover:bg-accent`}>
      {body}
    </Link>
  ) : (
    <div className={tile}>{body}</div>
  );
}
