#!/usr/bin/env python3
"""Real multi-connection falsifier for the OPEN-REL-030 Tier 1 transaction.

The script intentionally has no database driver dependency. Every worker starts an
independent `psql` process inside the ephemeral PostgreSQL evidence container, so
success cannot be explained by a shared in-process lock or connection.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
import subprocess
import sys

WORKERS = 24
TENANT = "11111111-1111-1111-1111-111111111111"
METRIC = "22222222-2222-2222-2222-222222222222"
SOURCE_GENERATION = "33333333-3333-3333-3333-333333333333"
OBSERVATION = "44444444-4444-4444-4444-444444444444"


def run_psql(container: str, sql: str) -> str:
    command = [
        "docker",
        "exec",
        "-e",
        "PGPASSWORD=evidence",
        container,
        "psql",
        "-X",
        "-v",
        "ON_ERROR_STOP=1",
        "-U",
        "postgres",
        "-d",
        "jlmirror",
        "-Atq",
        "-c",
        sql,
    ]
    result = subprocess.run(command, text=True, capture_output=True, check=False)
    if result.returncode != 0:
        raise RuntimeError(
            f"psql worker failed rc={result.returncode}: {result.stderr.strip()}"
        )
    return result.stdout.strip()


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("usage: tier1_concurrency.py <postgres-container-name>")

    container = sys.argv[1]
    sql = f"""
        SELECT newly_accepted, ordering_advanced, semantic_transition
        FROM tel_evidence.accept_observation(
            '{TENANT}'::uuid,
            'zabbix:source:metric',
            '{OBSERVATION}'::uuid,
            '{METRIC}'::uuid,
            '{SOURCE_GENERATION}'::uuid,
            '{SOURCE_GENERATION}'::uuid,
            10,
            100,
            '2026-08-28T12:00:00Z'::timestamptz,
            42.0,
            true,
            NULL
        );
    """

    outputs: list[str] = []
    with ThreadPoolExecutor(max_workers=WORKERS) as executor:
        futures = [executor.submit(run_psql, container, sql) for _ in range(WORKERS)]
        for future in as_completed(futures):
            outputs.append(future.result())

    triples = [tuple(output.split("|")) for output in outputs]
    if any(len(triple) != 3 for triple in triples):
        raise AssertionError(f"unexpected worker result(s): {outputs!r}")

    newly_accepted = sum(triple[0] == "t" for triple in triples)
    ordering_advanced = sum(triple[1] == "t" for triple in triples)
    semantic_transition = sum(triple[2] == "t" for triple in triples)

    if newly_accepted != 1:
        raise AssertionError(
            f"atomic create-or-observe violated: expected 1 new acceptance, got {newly_accepted}"
        )
    if ordering_advanced != 1:
        raise AssertionError(
            f"single-winner current ordering violated: expected 1 advance, got {ordering_advanced}"
        )
    if semantic_transition != 1:
        raise AssertionError(
            f"semantic transition idempotence violated: expected 1 transition, got {semantic_transition}"
        )

    print(
        "tier1_concurrency=PASS "
        f"workers={WORKERS} newly_accepted={newly_accepted} "
        f"ordering_advanced={ordering_advanced} semantic_transition={semantic_transition}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
