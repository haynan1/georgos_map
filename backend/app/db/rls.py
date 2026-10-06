"""Migration helpers to put a tenant table under row-level security.

Usage inside an Alembic migration, right after creating a table that has an
``organization_id`` column::

    from app.db.rls import enable_tenant_isolation
    enable_tenant_isolation("machines")

From then on the application role only sees and writes rows whose ``organization_id``
matches the tenant bound to the current transaction (see ``app.db.session``).
"""

from alembic import op

from app.db.session import TENANT_SETTING

POLICY_NAME = "tenant_isolation"


def tenant_isolation_sql(table: str) -> list[str]:
    predicate = f"organization_id = NULLIF(current_setting('{TENANT_SETTING}', true), '')::uuid"
    return [
        f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY',
        # FORCE also applies the policy to the table owner, so even a mistakenly
        # privileged connection cannot read across tenants.
        f'ALTER TABLE "{table}" FORCE ROW LEVEL SECURITY',
        f'CREATE POLICY {POLICY_NAME} ON "{table}" USING ({predicate}) WITH CHECK ({predicate})',
    ]


def enable_tenant_isolation(table: str) -> None:
    for statement in tenant_isolation_sql(table):
        op.execute(statement)


def disable_tenant_isolation(table: str) -> None:
    op.execute(f'DROP POLICY IF EXISTS {POLICY_NAME} ON "{table}"')
    op.execute(f'ALTER TABLE "{table}" NO FORCE ROW LEVEL SECURITY')
    op.execute(f'ALTER TABLE "{table}" DISABLE ROW LEVEL SECURITY')
