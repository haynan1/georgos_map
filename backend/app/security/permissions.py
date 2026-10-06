"""Role-based access control.

Roles are assigned per organization (a person can be an admin in one company and a viewer
in another). Permissions are derived from the role in code, not stored, so the matrix is
versioned, reviewed and tested like any other code.

Domain modules guard endpoints with ``require(Permission.X)`` from
``app.modules.auth.dependencies``.
"""

from enum import StrEnum


class Role(StrEnum):
    OWNER = "owner"
    ADMIN = "admin"
    MANAGER = "manager"
    OPERATOR = "operator"
    VIEWER = "viewer"

    @property
    def rank(self) -> int:
        return _RANK[self]

    def outranks(self, other: Role) -> bool:
        return self.rank > other.rank


_RANK = {
    Role.VIEWER: 10,
    Role.OPERATOR: 20,
    Role.MANAGER: 30,
    Role.ADMIN: 40,
    Role.OWNER: 50,
}


class Permission(StrEnum):
    ORGANIZATION_UPDATE = "organization:update"
    MEMBERS_READ = "members:read"
    MEMBERS_MANAGE = "members:manage"
    AUDIT_READ = "audit:read"

    MACHINES_READ = "machines:read"
    MACHINES_WRITE = "machines:write"
    MAINTENANCE_READ = "maintenance:read"
    MAINTENANCE_WRITE = "maintenance:write"
    PARTS_READ = "parts:read"
    PARTS_WRITE = "parts:write"
    TELEMETRY_READ = "telemetry:read"
    COMMERCIAL_READ = "commercial:read"
    COMMERCIAL_WRITE = "commercial:write"


_VIEWER = frozenset(
    {
        Permission.MEMBERS_READ,
        Permission.MACHINES_READ,
        Permission.MAINTENANCE_READ,
        Permission.PARTS_READ,
        Permission.TELEMETRY_READ,
    }
)
_OPERATOR = _VIEWER | {Permission.MAINTENANCE_WRITE}
_MANAGER = _OPERATOR | {
    Permission.MACHINES_WRITE,
    Permission.PARTS_WRITE,
    Permission.COMMERCIAL_READ,
    Permission.COMMERCIAL_WRITE,
}
_ADMIN = _MANAGER | {
    Permission.MEMBERS_MANAGE,
    Permission.AUDIT_READ,
    Permission.ORGANIZATION_UPDATE,
}

ROLE_PERMISSIONS: dict[Role, frozenset[Permission]] = {
    Role.VIEWER: _VIEWER,
    Role.OPERATOR: _OPERATOR,
    Role.MANAGER: _MANAGER,
    Role.ADMIN: _ADMIN,
    Role.OWNER: _ADMIN,
}


def permissions_for(role: Role) -> frozenset[Permission]:
    return ROLE_PERMISSIONS[role]


def can_assign(actor: Role, target_role: Role) -> bool:
    """An actor may grant at most their own role (only owners create owners)."""
    return not target_role.outranks(actor)


def can_manage(actor: Role, member: Role) -> bool:
    """An actor may change or remove members strictly below them; owners manage owners."""
    return actor is Role.OWNER or actor.outranks(member)
