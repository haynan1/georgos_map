import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Link, useRouter } from "@tanstack/react-router";
import { ChevronsUpDown, LogOut, ShieldCheck } from "lucide-react";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { applySession, useSession } from "@/features/auth/session";
import { api, unwrap } from "@/lib/api/client";
import { initials } from "@/lib/format";

export function UserMenu() {
  const session = useSession();
  const queryClient = useQueryClient();
  const router = useRouter();

  const logout = useMutation({
    mutationFn: () => unwrap(api.POST("/api/v1/auth/logout")),
    // Whatever the server says, this browser is done with the session.
    onSettled: async () => {
      applySession(queryClient, null);
      await router.navigate({ to: "/entrar" });
    },
  });

  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        className="flex w-full cursor-pointer items-center gap-3 rounded-lg p-2 text-left transition-colors hover:bg-sidebar-accent"
        aria-label="Menu da conta"
      >
        <Avatar className="size-8">
          <AvatarFallback className="bg-secondary text-xs font-medium">
            {initials(session.user.full_name)}
          </AvatarFallback>
        </Avatar>
        <span className="min-w-0 flex-1">
          <span className="block truncate text-sm font-medium">{session.user.full_name}</span>
          <span className="block truncate text-xs text-muted-foreground">{session.user.email}</span>
        </span>
        <ChevronsUpDown className="size-4 text-muted-foreground" aria-hidden="true" />
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start" side="top" className="w-60">
        <DropdownMenuLabel className="truncate text-xs font-normal text-muted-foreground">
          {session.user.email}
        </DropdownMenuLabel>
        <DropdownMenuItem asChild>
          <Link to="/seguranca">
            <ShieldCheck aria-hidden="true" />
            Segurança da conta
          </Link>
        </DropdownMenuItem>
        <DropdownMenuSeparator />
        <DropdownMenuItem
          variant="destructive"
          disabled={logout.isPending}
          onSelect={() => logout.mutate()}
        >
          <LogOut aria-hidden="true" />
          Sair
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
