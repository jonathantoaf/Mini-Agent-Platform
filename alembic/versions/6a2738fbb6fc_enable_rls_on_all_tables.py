"""enable RLS on all tables

NOTE: Future migrations that perform DML (INSERT/UPDATE/DELETE) on tenant-scoped
tables must either SET LOCAL app.current_tenant_id first, or temporarily disable
RLS within the migration. DDL operations (CREATE TABLE, ALTER TABLE, etc.) are
not affected by RLS.

Revision ID: 6a2738fbb6fc
Revises: 01a49cc917ee
Create Date: 2026-03-27 17:35:32.413575
"""

from collections.abc import Sequence

from sqlalchemy import text

from alembic import op

revision: str = "6a2738fbb6fc"
down_revision: str | None = "01a49cc917ee"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TENANT_TABLES = ("agents", "tools", "executions")
APP_ROLE = "app_user"


def _get_db_name() -> str:
    """Resolve current database name dynamically (avoids hardcoding)."""
    conn = op.get_bind()
    return conn.execute(text("SELECT current_database()")).scalar_one()


def _role_exists(role: str) -> bool:
    """Check if a PostgreSQL role already exists."""
    conn = op.get_bind()
    result = conn.execute(text("SELECT 1 FROM pg_roles WHERE rolname = :role"), {"role": role})
    return result.scalar() is not None


def upgrade() -> None:
    # Create a non-superuser role for the application.
    # Superusers always bypass RLS, so the app must connect as a regular user.
    if not _role_exists(APP_ROLE):
        op.execute(f"CREATE ROLE {APP_ROLE} LOGIN PASSWORD 'app_user' NOINHERIT")

    db_name = _get_db_name()
    op.execute(f"GRANT CONNECT ON DATABASE {db_name} TO {APP_ROLE}")
    op.execute(f"GRANT USAGE ON SCHEMA public TO {APP_ROLE}")
    op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {APP_ROLE}")
    op.execute(
        f"ALTER DEFAULT PRIVILEGES IN SCHEMA public"
        f" GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO {APP_ROLE}"
    )

    for table in TENANT_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY tenant_isolation_policy ON {table}"
            f" FOR ALL TO {APP_ROLE}"
            f" USING (tenant_id = current_setting('app.current_tenant_id', true))"
            f" WITH CHECK (tenant_id = current_setting('app.current_tenant_id', true))"
        )


def downgrade() -> None:
    for table in TENANT_TABLES:
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation_policy ON {table}")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")

    db_name = _get_db_name()
    op.execute(f"ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON TABLES FROM {APP_ROLE}")
    op.execute(f"REVOKE ALL ON ALL TABLES IN SCHEMA public FROM {APP_ROLE}")
    op.execute(f"REVOKE USAGE ON SCHEMA public FROM {APP_ROLE}")
    op.execute(f"REVOKE CONNECT ON DATABASE {db_name} FROM {APP_ROLE}")
    op.execute(f"DROP ROLE IF EXISTS {APP_ROLE}")
