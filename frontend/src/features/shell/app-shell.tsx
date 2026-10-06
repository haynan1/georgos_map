import { Link, Outlet, useRouterState } from "@tanstack/react-router";
import { History, LayoutGrid, type LucideIcon, Menu, ShieldCheck, Users } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Wordmark } from "@/components/brand/wordmark";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetTitle, SheetTrigger } from "@/components/ui/sheet";
import type { Permission } from "@/features/auth/roles";
import { hasPermission, useSession } from "@/features/auth/session";
import { cn } from "@/lib/utils";
import { OrganizationSwitcher } from "./organization-switcher";
import { UserMenu } from "./user-menu";

type AppPath = "/" | "/equipe" | "/seguranca" | "/atividade";

interface NavItem {
  to: AppPath;
  label: string;
  icon: LucideIcon;
  permission?: Permission;
}

const NAV: NavItem[] = [
  { to: "/", label: "Visão geral", icon: LayoutGrid },
  { to: "/equipe", label: "Equipe", icon: Users, permission: "members:read" },
  { to: "/atividade", label: "Atividade", icon: History, permission: "audit:read" },
  { to: "/seguranca", label: "Segurança", icon: ShieldCheck },
];

function Navigation({ onNavigate }: { onNavigate?: () => void }) {
  const session = useSession();
  const items = NAV.filter((item) => !item.permission || hasPermission(session, item.permission));
  return (
    <nav aria-label="Principal" className="flex flex-col gap-0.5">
      {items.map(({ to, label, icon: Icon }) => (
        <Link
          key={to}
          to={to}
          onClick={onNavigate}
          activeOptions={{ exact: to === "/" }}
          className="group relative flex h-10 items-center gap-3 rounded-lg px-3 text-sm text-muted-foreground transition-colors hover:bg-sidebar-accent hover:text-foreground data-[status=active]:bg-sidebar-accent data-[status=active]:text-foreground"
        >
          <span
            aria-hidden="true"
            className="absolute inset-y-2.5 left-0 w-0.5 rounded-full bg-primary opacity-0 transition-opacity group-data-[status=active]:opacity-100"
          />
          <Icon className="size-4" aria-hidden="true" />
          {label}
        </Link>
      ))}
    </nav>
  );
}

function SidebarContent({ onNavigate }: { onNavigate?: () => void }) {
  return (
    <div className="flex h-full flex-col gap-6 p-4">
      <div className="px-1 pt-1">
        <Wordmark />
      </div>
      <OrganizationSwitcher />
      <Navigation {...(onNavigate ? { onNavigate } : {})} />
      <div className="mt-auto">
        <UserMenu />
      </div>
    </div>
  );
}

export function AppShell() {
  const [mobileOpen, setMobileOpen] = useState(false);
  const pathname = useRouterState({ select: (state) => state.location.pathname });

  // Move focus to the page on navigation (not on first load, where the skip link should
  // remain the first stop) so screen readers announce the new content.
  const previousPath = useRef(pathname);
  useEffect(() => {
    if (previousPath.current === pathname) return;
    previousPath.current = pathname;
    document.getElementById("conteudo")?.focus({ preventScroll: true });
  }, [pathname]);

  return (
    <div className="min-h-dvh">
      <a
        href="#conteudo"
        className="sr-only z-50 rounded-md bg-primary px-4 py-2 text-primary-foreground focus:not-sr-only focus:fixed focus:top-3 focus:left-3"
      >
        Pular para o conteúdo
      </a>

      <aside className="fixed inset-y-0 left-0 hidden w-64 border-r bg-sidebar lg:block">
        <SidebarContent />
      </aside>

      <header className="sticky top-0 z-30 flex h-14 items-center justify-between border-b bg-background/85 px-4 backdrop-blur-md lg:hidden">
        <Wordmark />
        <Sheet open={mobileOpen} onOpenChange={setMobileOpen}>
          <SheetTrigger asChild>
            <Button variant="ghost" size="icon-lg" aria-label="Abrir menu">
              <Menu />
            </Button>
          </SheetTrigger>
          <SheetContent side="left" className="w-72 bg-sidebar p-0">
            <SheetTitle className="sr-only">Menu</SheetTitle>
            <SidebarContent onNavigate={() => setMobileOpen(false)} />
          </SheetContent>
        </Sheet>
      </header>

      <div className="lg:pl-64">
        <main
          id="conteudo"
          tabIndex={-1}
          className={cn("mx-auto w-full max-w-5xl px-5 py-10 outline-none sm:px-8 lg:py-16")}
        >
          <Outlet />
        </main>
      </div>
    </div>
  );
}
