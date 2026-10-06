import { describe, expect, it } from "vitest";
import { assignableRoles, canAssign, canManage } from "./roles";
import { safeRedirect } from "./session";

describe("safeRedirect", () => {
  it.each([
    ["/equipe", "/equipe"],
    ["/seguranca?aba=sessoes", "/seguranca?aba=sessoes"],
  ])("keeps in-app path %s", (input, expected) => {
    expect(safeRedirect(input)).toBe(expected);
  });

  it.each([
    "https://evil.example",
    "//evil.example",
    "/\\evil.example",
    "javascript:alert(1)",
    "",
    undefined,
    42,
  ])("rejects open redirect %s", (input) => {
    expect(safeRedirect(input)).toBe("/");
  });
});

describe("role rules mirror the API", () => {
  it("never lets an actor grant a role above their own", () => {
    expect(canAssign("admin", "owner")).toBe(false);
    expect(canAssign("owner", "owner")).toBe(true);
    expect(assignableRoles("manager")).toEqual(["manager", "operator", "viewer"]);
  });

  it("requires a strictly higher rank to manage, except for owners", () => {
    expect(canManage("admin", "admin")).toBe(false);
    expect(canManage("admin", "manager")).toBe(true);
    expect(canManage("owner", "owner")).toBe(true);
  });
});
