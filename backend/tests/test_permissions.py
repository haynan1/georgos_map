from itertools import pairwise

import pytest

from app.security.permissions import (
    ROLE_PERMISSIONS,
    Permission,
    Role,
    can_assign,
    can_manage,
    permissions_for,
)


def test_every_role_has_a_permission_set() -> None:
    assert set(ROLE_PERMISSIONS) == set(Role)


def test_permissions_grow_monotonically_with_rank() -> None:
    ordered = sorted(Role, key=lambda role: role.rank)
    for lower, higher in pairwise(ordered):
        assert permissions_for(lower) <= permissions_for(higher), (lower, higher)


@pytest.mark.parametrize(
    ("role", "permission", "allowed"),
    [
        (Role.VIEWER, Permission.MACHINES_READ, True),
        (Role.VIEWER, Permission.MAINTENANCE_WRITE, False),
        (Role.VIEWER, Permission.COMMERCIAL_READ, False),
        (Role.OPERATOR, Permission.MAINTENANCE_WRITE, True),
        (Role.OPERATOR, Permission.MACHINES_WRITE, False),
        (Role.MANAGER, Permission.MACHINES_WRITE, True),
        (Role.MANAGER, Permission.MEMBERS_MANAGE, False),
        (Role.ADMIN, Permission.MEMBERS_MANAGE, True),
        (Role.ADMIN, Permission.AUDIT_READ, True),
    ],
)
def test_permission_matrix(role: Role, permission: Permission, allowed: bool) -> None:
    assert (permission in permissions_for(role)) is allowed


def test_assignment_never_exceeds_own_role() -> None:
    assert can_assign(Role.ADMIN, Role.ADMIN)
    assert not can_assign(Role.ADMIN, Role.OWNER)
    assert can_assign(Role.OWNER, Role.OWNER)
    assert not can_assign(Role.MANAGER, Role.ADMIN)


def test_management_requires_strictly_higher_rank_except_owners() -> None:
    assert can_manage(Role.ADMIN, Role.MANAGER)
    assert not can_manage(Role.ADMIN, Role.ADMIN)
    assert not can_manage(Role.ADMIN, Role.OWNER)
    assert can_manage(Role.OWNER, Role.OWNER)
