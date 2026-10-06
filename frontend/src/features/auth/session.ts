import { type QueryClient, queryOptions, useSuspenseQuery } from "@tanstack/react-query";
import { ApiError, api, type Schemas, setCsrfToken, unwrap } from "@/lib/api/client";
import type { Permission } from "./roles";

export type Session = Schemas["SessionView"];

export const sessionKey = ["session"] as const;

export const sessionQuery = queryOptions({
  queryKey: sessionKey,
  queryFn: async (): Promise<Session | null> => {
    try {
      const session = await unwrap(api.GET("/api/v1/auth/session"));
      setCsrfToken(session.csrf_token);
      return session;
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) {
        setCsrfToken(null);
        return null;
      }
      throw error;
    }
  },
  staleTime: 5 * 60_000,
});

/** Install a session returned by login, registration, invitation or org switch. */
export function applySession(queryClient: QueryClient, session: Session | null) {
  setCsrfToken(session?.csrf_token ?? null);
  if (session === null) {
    // Everything cached belonged to the previous identity.
    queryClient.clear();
  }
  queryClient.setQueryData(sessionKey, session);
}

/** Inside the authenticated area the session is guaranteed by the route guard. */
export function useSession(): Session {
  const { data } = useSuspenseQuery(sessionQuery);
  if (!data) {
    throw new Error("useSession() used outside the authenticated area");
  }
  return data;
}

export function hasPermission(session: Session, permission: Permission): boolean {
  return session.permissions.includes(permission);
}

/** Only same-app paths are honoured, so a crafted link cannot bounce users elsewhere. */
export function safeRedirect(target: unknown): string {
  if (typeof target !== "string" || !target.startsWith("/") || target.startsWith("//")) {
    return "/";
  }
  return target.includes("\\") ? "/" : target;
}
