import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "@tanstack/react-router";
import { Check, ChevronsUpDown } from "lucide-react";
import { toast } from "sonner";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { ROLE_LABEL } from "@/features/auth/roles";
import { applySession, useSession } from "@/features/auth/session";
import { api, unwrap } from "@/lib/api/client";
import { errorMessage } from "@/lib/errors";
import { initials } from "@/lib/format";

function OrganizationTile({ name }: { name: string }) {
  return (
    <span
      aria-hidden="true"
      className="flex size-8 shrink-0 items-center justify-center rounded-md border border-border-strong bg-card font-mono text-[0.6875rem] font-medium tracking-wider"
    >
      {initials(name)}
    </span>
  );
}

export function OrganizationSwitcher() {
  const session = useSession();
  const queryClient = useQueryClient();
  const router = useRouter();
  const canSwitch = session.organizations.length > 1;

  const switchTo = useMutation({
    mutationFn: (organizationId: string) =>
      unwrap(
        api.POST("/api/v1/auth/switch-organization", {
          body: { organization_id: organizationId },
        }),
      ),
    onSuccess: async (next) => {
      queryClient.removeQueries({ predicate: (query) => query.queryKey[0] !== "session" });
      applySession(queryClient, next);
      await router.navigate({ to: "/" });
      toast.success(`Você está em ${next.organization.name}.`);
    },
    onError: (error) => toast.error(errorMessage(error)),
  });

  const summary = (
    <>
      <OrganizationTile name={session.organization.name} />
      <span className="min-w-0 flex-1 text-left">
        <span className="block truncate text-sm font-medium">{session.organization.name}</span>
        <span className="block text-xs text-muted-foreground">{ROLE_LABEL[session.role]}</span>
      </span>
    </>
  );

  if (!canSwitch) {
    return (
      <div className="flex items-center gap-3 rounded-lg border bg-card/50 p-2">{summary}</div>
    );
  }

  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        className="flex w-full cursor-pointer items-center gap-3 rounded-lg border bg-card/50 p-2 transition-colors hover:bg-sidebar-accent"
        aria-label="Trocar de empresa"
      >
        {summary}
        <ChevronsUpDown className="size-4 text-muted-foreground" aria-hidden="true" />
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start" className="w-60">
        <DropdownMenuLabel className="text-xs font-normal text-muted-foreground">
          Suas empresas
        </DropdownMenuLabel>
        {session.organizations.map((organization) => {
          const current = organization.id === session.organization.id;
          return (
            <DropdownMenuItem
              key={organization.id}
              disabled={switchTo.isPending}
              onSelect={() => !current && switchTo.mutate(organization.id)}
              className="gap-3"
            >
              <OrganizationTile name={organization.name} />
              <span className="min-w-0 flex-1">
                <span className="block truncate">{organization.name}</span>
                <span className="block text-xs text-muted-foreground">
                  {ROLE_LABEL[organization.role]}
                </span>
              </span>
              {current && <Check className="size-4 text-primary" aria-label="Atual" />}
            </DropdownMenuItem>
          );
        })}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
