"""JLMIRROR SQL migration runner.

Applies the canonical SQL migrations under sql/ in dependency order:
    wave1 -> wave2 -> wave4 -> integration -> d2-open-rel-030

Tracks applied migrations in a `platform._migration_log` table so repeated
runs are idempotent. Runs as the migration/admin role (DATABASE_MIGRATION_URL),
which must be a superuser or have DDL + role-creation authority.

Usage:
    python scripts/migrate.py apply    # apply pending migrations
    python scripts/migrate.py status    # show applied / pending migrations
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import psycopg

REPO_ROOT = Path(__file__).resolve().parents[1]
SQL_DIR = REPO_ROOT / "sql"

# Canonical migration order: each tuple is (group, directory).
# Within each group, files are applied in lexicographic order, which matches
# the numeric-prefixed naming convention used by the repository.
MIGRATION_GROUPS: tuple[tuple[str, str], ...] = (
    ("wave1", "wave1"),
    ("wave2", "wave2"),
    ("wave4", "wave4"),
    ("integration", "integration"),
    ("d2-open-rel-030", "d2-open-rel-030"),
)

TRACKING_SCHEMA = "platform"
TRACKING_TABLE = "_migration_log"


@dataclass(frozen=True)
class Migration:
    group: str
    filename: str
    path: Path

    @property
    def key(self) -> str:
        return f"{self.group}/{self.filename}"

    @property
    def sql(self) -> str:
        return self.path.read_text(encoding="utf-8")


def _strip_psql_meta_commands(sql: str) -> str:
    """Remove psql meta-commands (lines starting with \\) — they are not valid SQL
    and cause psycopg to raise SyntaxError when passed to cur.execute()."""
    return "\n".join(
        line for line in sql.splitlines()
        if not line.strip().startswith("\\")
    )


def discover_migrations() -> list[Migration]:
    """Return all migrations in canonical order."""
    migrations: list[Migration] = []
    for group_name, dir_name in MIGRATION_GROUPS:
        group_dir = SQL_DIR / dir_name
        if not group_dir.is_dir():
            continue
        for sql_file in sorted(group_dir.glob("*.sql")):
            migrations.append(Migration(group_name, sql_file.name, sql_file))
    return migrations


def ensure_tracking_table(conn: psycopg.Connection) -> None:
    """Create the migration tracking table if it does not exist."""
    with conn.cursor() as cur:
        cur.execute(f"CREATE SCHEMA IF NOT EXISTS {TRACKING_SCHEMA}")
        cur.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {TRACKING_SCHEMA}.{TRACKING_TABLE} (
                migration_key  TEXT PRIMARY KEY,
                applied_at    TIMESTAMPTZ NOT NULL DEFAULT now()
            )
            """
        )
    conn.commit()


def applied_keys(conn: psycopg.Connection) -> set[str]:
    with conn.cursor() as cur:
        cur.execute(
            f"SELECT migration_key FROM {TRACKING_SCHEMA}.{TRACKING_TABLE}"
        )
        return {row[0] for row in cur.fetchall()}


def apply_migration(conn: psycopg.Connection, migration: Migration) -> None:
    """Apply a single migration file in its own transaction boundary.

    The SQL files already manage their own BEGIN/COMMIT blocks, so we execute
    the full script content as-is. If the script fails, the transaction is
    rolled back and the error is raised.
    """
    print(f"  applying: {migration.key}")
    with conn.cursor() as cur:
        cur.execute(_strip_psql_meta_commands(migration.sql))
        cur.execute(
            f"INSERT INTO {TRACKING_SCHEMA}.{TRACKING_TABLE} (migration_key) VALUES (%s)",
            (migration.key,),
        )
    conn.commit()


def migration_url() -> str:
    url = os.environ.get("DATABASE_MIGRATION_URL") or os.environ.get("DATABASE_URL")
    if not url:
        print("ERROR: DATABASE_MIGRATION_URL or DATABASE_URL is not set.", file=sys.stderr)
        sys.exit(2)
    return url


def cmd_apply() -> int:
    migrations = discover_migrations()
    if not migrations:
        print("No migration files found.")
        return 0

    url = migration_url()
    with psycopg.connect(url, autocommit=False) as conn:
        ensure_tracking_table(conn)
        already = applied_keys(conn)
        pending = [m for m in migrations if m.key not in already]

        if not pending:
            print(f"All {len(migrations)} migrations already applied. Nothing to do.")
            return 0

        print(f"Applying {len(pending)} of {len(migrations)} pending migrations...")
        for migration in pending:
            try:
                apply_migration(conn, migration)
            except Exception as exc:
                conn.rollback()
                print(f"FAILED at {migration.key}: {exc}", file=sys.stderr)
                return 1

        print(f"Done. {len(pending)} migrations applied successfully.")
    return 0


def cmd_status() -> int:
    migrations = discover_migrations()
    url = migration_url()
    with psycopg.connect(url) as conn:
        ensure_tracking_table(conn)
        already = applied_keys(conn)

    print(f"{'Migration':<55} {'Status'}")
    print("-" * 70)
    applied_count = 0
    for m in migrations:
        is_applied = m.key in already
        if is_applied:
            applied_count += 1
        status = "applied" if is_applied else "pending"
        print(f"{m.key:<55} {status}")
    print("-" * 70)
    print(f"Applied: {applied_count}/{len(migrations)}")
    return 0


def main() -> int:
    if len(sys.argv) < 2 or sys.argv[1] not in ("apply", "status"):
        print(__doc__)
        return 2
    if sys.argv[1] == "apply":
        return cmd_apply()
    return cmd_status()


if __name__ == "__main__":
    sys.exit(main())
