import {
  KeyRound,
  LogIn,
  LogOut,
  type LucideIcon,
  Mail,
  MailX,
  Pencil,
  Repeat,
  ShieldOff,
  Sparkles,
  UserCog,
  UserMinus,
  UserPlus,
} from "lucide-react";
import { ROLE_LABEL, type Role } from "@/features/auth/roles";
import type { Schemas } from "@/lib/api/client";

export type AuditEvent = Schemas["AuditEventView"];

interface Described {
  icon: LucideIcon;
  text: string;
}

function roleLabel(value: unknown): string {
  return typeof value === "string" && value in ROLE_LABEL ? ROLE_LABEL[value as Role] : "—";
}

function change(details: AuditEvent["details"], key: string): { from: unknown; to: unknown } {
  const value = details[key];
  if (typeof value === "object" && value !== null && "from" in value && "to" in value) {
    return value as { from: unknown; to: unknown };
  }
  return { from: null, to: null };
}

/**
 * Renders an audit event as a sentence completing "<actor> …".
 * ``memberName`` resolves target user ids into names when the member is still known.
 */
export function describeEvent(
  event: AuditEvent,
  memberName: (userId: string | null) => string | null,
): Described {
  const target = memberName(event.target_id);
  switch (event.action) {
    case "auth.login_succeeded":
      return { icon: LogIn, text: "entrou na conta" };
    case "auth.logout":
      return { icon: LogOut, text: "saiu da conta" };
    case "auth.password_changed":
      return { icon: KeyRound, text: "alterou a própria senha" };
    case "auth.session_revoked":
      return {
        icon: ShieldOff,
        text:
          event.details.scope === "other_sessions"
            ? "encerrou as sessões em outros dispositivos"
            : "encerrou uma sessão",
      };
    case "auth.organization_switched":
      return { icon: Repeat, text: "acessou esta empresa" };
    case "organization.created":
      return { icon: Sparkles, text: "criou a empresa" };
    case "organization.updated":
      return {
        icon: Pencil,
        text: `renomeou a empresa para “${String(change(event.details, "name").to ?? "")}”`,
      };
    case "member.joined":
      return { icon: UserPlus, text: `entrou na equipe como ${roleLabel(event.details.role)}` };
    case "member.role_changed": {
      const { from, to } = change(event.details, "role");
      return {
        icon: UserCog,
        text: `mudou o papel de ${target ?? "um membro"} de ${roleLabel(from)} para ${roleLabel(to)}`,
      };
    }
    case "member.removed":
      return { icon: UserMinus, text: `removeu ${target ?? "um membro"} da equipe` };
    case "invitation.created":
      return { icon: Mail, text: `convidou uma pessoa como ${roleLabel(event.details.role)}` };
    case "invitation.revoked":
      return { icon: MailX, text: "cancelou um convite" };
    default:
      return { icon: Pencil, text: event.action };
  }
}
