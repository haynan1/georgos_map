import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createFileRoute, redirect, useNavigate } from "@tanstack/react-router";
import { MailX, UserMinus, UserPlus } from "lucide-react";
import { toast } from "sonner";
import { z } from "zod";
import { PageHeader, Section } from "@/components/page-header";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { assignableRoles, canManage, ROLE_LABEL, type Role } from "@/features/auth/roles";
import { hasPermission, sessionQuery, useSession } from "@/features/auth/session";
import { InviteDialog } from "@/features/organization/invite-dialog";
import { invitationsQuery, membersQuery } from "@/features/organization/queries";
import { api, type Schemas, unwrap } from "@/lib/api/client";
import { errorMessage } from "@/lib/errors";
import { formatDate, formatRelative, initials } from "@/lib/format";

export const Route = createFileRoute("/_app/equipe")({
  validateSearch: z.object({ convidar: z.boolean().optional() }),
  beforeLoad: async ({ context }) => {
    const session = await context.queryClient.ensureQueryData(sessionQuery);
    if (!session || !hasPermission(session, "members:read")) throw redirect({ to: "/" });
  },
  head: () => ({ meta: [{ title: "Equipe · Georgos Map" }] }),
  component: TeamPage,
});

function TeamPage() {
  const session = useSession();
  const { convidar } = Route.useSearch();
  const navigate = useNavigate({ from: Route.fullPath });
  const manage = hasPermission(session, "members:manage");
  const members = useQuery(membersQuery(session.organization.id));
  const invitations = useQuery({
    ...invitationsQuery(session.organization.id),
    enabled: manage,
  });

  const inviteOpen = Boolean(convidar) && manage;
  const setInviteOpen = (open: boolean) =>
    void navigate({ search: open ? { convidar: true } : {}, replace: true });

  return (
    <>
      <PageHeader
        eyebrow={session.organization.name}
        title="Equipe"
        description="Quem tem acesso à empresa e o que cada pessoa pode fazer."
        actions={
          manage && (
            <Button size="lg" onClick={() => setInviteOpen(true)}>
              <UserPlus aria-hidden="true" />
              Convidar pessoa
            </Button>
          )
        }
      />

      <Section
        title="Membros"
        description={
          members.data
            ? `${members.data.length} ${members.data.length === 1 ? "pessoa" : "pessoas"}`
            : undefined
        }
      >
        <div className="overflow-hidden rounded-xl border bg-card">
          {members.data ? (
            <ul className="divide-y">
              {members.data.map((member) => (
                <MemberRow key={member.id} member={member} />
              ))}
            </ul>
          ) : (
            <div className="space-y-px">
              {[0, 1, 2].map((row) => (
                <Skeleton key={row} className="h-[4.25rem] rounded-none" />
              ))}
            </div>
          )}
        </div>
      </Section>

      {manage && invitations.data && invitations.data.length > 0 && (
        <Section
          title="Convites pendentes"
          description="Links ainda não utilizados. Cancele os que não forem mais necessários."
        >
          <ul className="divide-y overflow-hidden rounded-xl border bg-card">
            {invitations.data.map((invitation) => (
              <InvitationRow key={invitation.id} invitation={invitation} />
            ))}
          </ul>
        </Section>
      )}

      {manage && <InviteDialog open={inviteOpen} onOpenChange={setInviteOpen} />}
    </>
  );
}

function MemberRow({ member }: { member: Schemas["MemberView"] }) {
  const session = useSession();
  const queryClient = useQueryClient();
  const editable =
    !member.is_you &&
    hasPermission(session, "members:manage") &&
    canManage(session.role, member.role);

  const refresh = () =>
    queryClient.invalidateQueries({ queryKey: ["org", session.organization.id] });

  const changeRole = useMutation({
    mutationFn: (role: Role) =>
      unwrap(
        api.PATCH("/api/v1/organization/members/{membership_id}", {
          params: { path: { membership_id: member.id } },
          body: { role },
        }),
      ),
    onSuccess: async (_, role) => {
      await refresh();
      toast.success(`${member.full_name} agora é ${ROLE_LABEL[role].toLowerCase()}.`);
    },
    onError: (error) => toast.error(errorMessage(error)),
  });

  const remove = useMutation({
    mutationFn: () =>
      unwrap(
        api.DELETE("/api/v1/organization/members/{membership_id}", {
          params: { path: { membership_id: member.id } },
        }),
      ),
    onSuccess: async () => {
      await refresh();
      toast.success(`${member.full_name} foi removido da equipe.`);
    },
    onError: (error) => toast.error(errorMessage(error)),
  });

  return (
    <li className="flex flex-wrap items-center gap-x-4 gap-y-3 px-5 py-4">
      <Avatar className="size-9">
        <AvatarFallback className="bg-secondary text-xs font-medium">
          {initials(member.full_name)}
        </AvatarFallback>
      </Avatar>
      <div className="min-w-0 flex-1">
        <p className="flex items-center gap-2 truncate text-sm font-medium">
          {member.full_name}
          {member.is_you && (
            <Badge variant="outline" className="font-normal">
              Você
            </Badge>
          )}
        </p>
        <p className="truncate text-sm text-muted-foreground">{member.email}</p>
      </div>
      <p className="hidden w-36 text-sm text-muted-foreground md:block">
        Desde {formatDate(member.joined_at)}
      </p>
      <div className="flex items-center gap-1">
        {editable ? (
          <Select
            value={member.role}
            onValueChange={(role) => changeRole.mutate(role as Role)}
            disabled={changeRole.isPending}
          >
            <SelectTrigger className="h-9 w-40" aria-label={`Papel de ${member.full_name}`}>
              <SelectValue />
            </SelectTrigger>
            <SelectContent align="end">
              {assignableRoles(session.role).map((role) => (
                <SelectItem key={role} value={role}>
                  {ROLE_LABEL[role]}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        ) : (
          <span className="flex h-9 w-40 items-center px-3 text-sm text-muted-foreground">
            {ROLE_LABEL[member.role]}
          </span>
        )}
        {editable && (
          <AlertDialog>
            <AlertDialogTrigger asChild>
              <Button
                variant="ghost"
                size="icon"
                aria-label={`Remover ${member.full_name}`}
                className="text-muted-foreground hover:text-destructive"
              >
                <UserMinus />
              </Button>
            </AlertDialogTrigger>
            <AlertDialogContent>
              <AlertDialogHeader>
                <AlertDialogTitle>Remover {member.full_name}?</AlertDialogTitle>
                <AlertDialogDescription>
                  O acesso à {session.organization.name} termina imediatamente, inclusive nos
                  dispositivos em que a pessoa está conectada. A conta dela continua existindo.
                </AlertDialogDescription>
              </AlertDialogHeader>
              <AlertDialogFooter>
                <AlertDialogCancel>Cancelar</AlertDialogCancel>
                <AlertDialogAction
                  onClick={() => remove.mutate()}
                  className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                >
                  Remover da equipe
                </AlertDialogAction>
              </AlertDialogFooter>
            </AlertDialogContent>
          </AlertDialog>
        )}
      </div>
    </li>
  );
}

function InvitationRow({ invitation }: { invitation: Schemas["InvitationView"] }) {
  const session = useSession();
  const queryClient = useQueryClient();
  const revoke = useMutation({
    mutationFn: () =>
      unwrap(
        api.DELETE("/api/v1/organization/invitations/{invitation_id}", {
          params: { path: { invitation_id: invitation.id } },
        }),
      ),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["org", session.organization.id] });
      toast.success("Convite cancelado.");
    },
    onError: (error) => toast.error(errorMessage(error)),
  });

  return (
    <li className="flex flex-wrap items-center gap-x-4 gap-y-2 px-5 py-4">
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-medium">{invitation.email}</p>
        <p className="text-sm text-muted-foreground">
          {ROLE_LABEL[invitation.role]} · expira {formatRelative(invitation.expires_at)}
        </p>
      </div>
      <Button
        variant="ghost"
        size="sm"
        disabled={revoke.isPending}
        onClick={() => revoke.mutate()}
        className="text-muted-foreground hover:text-destructive"
      >
        <MailX aria-hidden="true" />
        Cancelar convite
      </Button>
    </li>
  );
}
