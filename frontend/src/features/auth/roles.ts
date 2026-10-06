import type { Schemas } from "@/lib/api/client";

export type Role = Schemas["Role"];
export type Permission = Schemas["Permission"];

/** Mirrors app/security/permissions.py. The API remains the authority; the UI only uses
 * this to hide controls the user could not use anyway. */
const RANK: Record<Role, number> = { viewer: 10, operator: 20, manager: 30, admin: 40, owner: 50 };

export const ROLES: readonly Role[] = ["owner", "admin", "manager", "operator", "viewer"];

export const ROLE_LABEL: Record<Role, string> = {
  owner: "Proprietário",
  admin: "Administrador",
  manager: "Gestor",
  operator: "Operador",
  viewer: "Leitor",
};

export const ROLE_DESCRIPTION: Record<Role, string> = {
  owner: "Controle total da empresa, incluindo outros proprietários.",
  admin: "Gerencia equipe, convites, auditoria e dados da empresa.",
  manager: "Gerencia máquinas, peças e área comercial.",
  operator: "Registra manutenções e acompanha as máquinas.",
  viewer: "Consulta máquinas, manutenções e telemetria.",
};

export function canAssign(actor: Role, target: Role): boolean {
  return RANK[target] <= RANK[actor];
}

export function canManage(actor: Role, member: Role): boolean {
  return actor === "owner" || RANK[actor] > RANK[member];
}

export function assignableRoles(actor: Role): Role[] {
  return ROLES.filter((role) => canAssign(actor, role));
}
