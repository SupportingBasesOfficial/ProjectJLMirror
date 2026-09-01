#!/usr/bin/env python3
from __future__ import annotations

import concurrent.futures

import replay_recovery_conformance_runner as core


def prove_port_single_winner(port: core.ReplayAuthorityPort) -> None:
    """Prove the shared PostgreSQL port only; this is not token-boundary evidence."""
    args = ("client-a", "jti-a", "fp-a", "session-effect-a", "session-result-a", 1)
    with concurrent.futures.ThreadPoolExecutor(max_workers=16) as pool:
        outcomes = list(pool.map(lambda _: port.consume(*args), range(48)))
    assert outcomes.count("WIN") == 1
    assert outcomes.count("OBSERVE") == 47
    assert port.consume(
        "client-a", "jti-a", "fp-conflict", "session-effect-a", "session-result-a", 1
    ) == "CONFLICT"
    assert core.psql(
        "SELECT count(*) FROM d3e_replay.effect_ledger WHERE effect_id='session-effect-a';"
    ) == "1"
    assert port.consume(
        "client-b", "jti-a", "fp-b", "session-effect-b", "session-result-b", 1
    ) == "WIN"
    print(
        "d3_e_replay_port_atomic_single_winner=PASS "
        "postgres_create_or_observe=true concurrent_workers=48 exactly_one_effect=true "
        "duplicates_observe=true assertion_fingerprint_conflict_rejected=true "
        "client_principal_scope=true token_boundary_claim=false"
    )
