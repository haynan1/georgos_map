import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import type { Schemas } from "@/lib/api/client";
import { formatDateTime, formatRelative } from "@/lib/format";
import { type AuditEvent, describeEvent } from "./audit";

export function ActivityFeed({
  events,
  members,
  showIp = false,
}: {
  events: AuditEvent[];
  members: Schemas["MemberView"][] | undefined;
  showIp?: boolean;
}) {
  const names = new Map(members?.map((member) => [member.user_id, member.full_name]));
  const memberName = (userId: string | null) => (userId ? (names.get(userId) ?? null) : null);

  return (
    <ol className="relative">
      {events.map((event, index) => {
        const { icon: Icon, text } = describeEvent(event, memberName);
        const last = index === events.length - 1;
        return (
          <li key={event.id} className="relative flex gap-4 pb-6 last:pb-0">
            {!last && (
              <span
                aria-hidden="true"
                className="absolute top-9 bottom-1 left-[1.0625rem] w-px bg-border"
              />
            )}
            <span className="flex size-[2.125rem] shrink-0 items-center justify-center rounded-full border bg-card">
              <Icon className="size-4 text-muted-foreground" aria-hidden="true" />
            </span>
            <div className="min-w-0 flex-1 pt-1.5">
              <p className="text-sm leading-relaxed">
                <span className="font-medium">{event.actor_name ?? "Alguém"}</span>{" "}
                <span className="text-muted-foreground">{text}</span>
              </p>
              <p className="mt-1 flex flex-wrap items-center gap-x-2 font-mono text-xs text-subtle-foreground">
                <Tooltip>
                  <TooltipTrigger asChild>
                    <time dateTime={event.created_at} className="cursor-default">
                      {formatRelative(event.created_at)}
                    </time>
                  </TooltipTrigger>
                  <TooltipContent>{formatDateTime(event.created_at)}</TooltipContent>
                </Tooltip>
                {showIp && event.ip_address && (
                  <>
                    <span aria-hidden="true">·</span>
                    <span>{event.ip_address}</span>
                  </>
                )}
              </p>
            </div>
          </li>
        );
      })}
    </ol>
  );
}
