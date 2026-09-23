"""PostgreSQL connection pool and tenant context helpers.

Implements ADR-003 (tenant isolation) by setting a transaction-local tenant
context via ``set_config`` so RLS policies can enforce isolation as a
defense-in-depth layer. The application path resolves the tenant through
trusted authority (``TenantContext``); the database layer re-checks it.
"""

from __future__ import annotations

from typing import Any

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from app.config import settings

_pool: ConnectionPool | None = None


def get_pool() -> ConnectionPool:
    global _pool
    if _pool is None:
        _pool = ConnectionPool(
            conninfo=settings.database_url,
            min_size=2,
            max_size=10,
            kwargs={"row_factory": dict_row},
            open=True,
        )
    return _pool


def close_pool() -> None:
    global _pool
    if _pool is not None:
        _pool.close()
        _pool = None


def set_tenant_context(conn: psycopg.Connection, tenant_id: str) -> None:
    """Set the transaction-local tenant GUC for RLS enforcement (ADR-003).

    ``is_local`` ensures the setting is scoped to the current transaction and
    cannot leak across requests. RLS policies read this via
    ``current_setting('jlmirror.tenant_id', true)``.
    """
    with conn.cursor() as cur:
        cur.execute("SELECT set_config('jlmirror.tenant_id', %s, true)", (tenant_id,))


def get_tenant_context(conn: psycopg.Connection) -> str | None:
    with conn.cursor() as cur:
        cur.execute("SELECT current_setting('jlmirror.tenant_id', true)")
        row = cur.fetchone()
        value = row[0] if row else None
        return value if value else None
