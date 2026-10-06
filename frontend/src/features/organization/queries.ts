import { infiniteQueryOptions, queryOptions } from "@tanstack/react-query";
import { api, unwrap } from "@/lib/api/client";

/*
 * Query keys are scoped by organization id: after switching companies, cached data from
 * the previous tenant can never be rendered, even for a frame.
 */

export const AUDIT_PAGE_SIZE = 30;

export const membersQuery = (organizationId: string) =>
  queryOptions({
    queryKey: ["org", organizationId, "members"],
    queryFn: () => unwrap(api.GET("/api/v1/organization/members")),
  });

export const invitationsQuery = (organizationId: string) =>
  queryOptions({
    queryKey: ["org", organizationId, "invitations"],
    queryFn: () => unwrap(api.GET("/api/v1/organization/invitations")),
  });

export const auditQuery = (organizationId: string, pageSize = AUDIT_PAGE_SIZE) =>
  infiniteQueryOptions({
    queryKey: ["org", organizationId, "audit", pageSize],
    queryFn: ({ pageParam }) =>
      unwrap(
        api.GET("/api/v1/organization/audit-events", {
          params: { query: { limit: pageSize, ...(pageParam ? { before: pageParam } : {}) } },
        }),
      ),
    initialPageParam: null as string | null,
    getNextPageParam: (lastPage) =>
      lastPage.length === pageSize ? (lastPage.at(-1)?.id ?? null) : null,
  });

export const activeSessionsQuery = queryOptions({
  queryKey: ["account", "sessions"],
  queryFn: () => unwrap(api.GET("/api/v1/auth/sessions")),
});
