from __future__ import annotations

import threading

import cache_authority_conformance_runner as base


_ORIGINAL_SETUP = base.setup_postgres
_ORIGINAL_ADMIT = base.admit
_ORIGINAL_ISSUE_LEASE = base.issue_lease
_ORIGINAL_RETIRE_LEASE = base.retire_lease
_ORIGINAL_EXCLUSION_SAFE = base.exclusion_safe
_ORIGINAL_COMMIT = base.commit_transition
_ORIGINAL_MARK_RECONCILED = base.mark_reconciled
_ORIGINAL_START_STALE_REPLICA = base.start_stale_replica
_ORIGINAL_START_RESTORE = base.start_restore_container
_ORIGINAL_ADMIT_NEW_EPOCH = base.admit_new_epoch

_ISSUED_LEASES: dict[str, base.BffLease] = {}
_RETIRED_REPLICAS: set[str] = set()


def setup_postgres() -> None:
    _ORIGINAL_SETUP()
    role, password = base.CONTROL_ROLE
    base.pg_role(
        role,
        password,
        """
ALTER TABLE cache_control.admission_state
ADD COLUMN hold_transition_id text;
""",
    )


def issue_lease(replica_id: str, epoch: int, valid_until_tick: int) -> base.BffLease:
    lease = _ORIGINAL_ISSUE_LEASE(replica_id, epoch, valid_until_tick)
    _ISSUED_LEASES[replica_id] = lease
    _RETIRED_REPLICAS.discard(replica_id)
    return lease


def retire_lease(replica_id: str) -> None:
    _ORIGINAL_RETIRE_LEASE(replica_id)
    # Durable acknowledgement means that replica has discarded its local
    # expected-admission lease before the fleet barrier counts it retired.
    _RETIRED_REPLICAS.add(replica_id)


def admit(
    owner: str,
    resource_id: str,
    lease: base.BffLease,
    tick: int,
    *,
    container: str | None = None,
    cli: str | None = None,
) -> str:
    if lease.replica_id in _RETIRED_REPLICAS:
        return "DENY"
    return _ORIGINAL_ADMIT(
        owner,
        resource_id,
        lease,
        tick,
        container=container,
        cli=cli,
    )


def begin_exclusion(target_epoch: int) -> None:
    role, password = base.CONTROL_ROLE
    result = base.pg_role(
        role,
        password,
        f"""
UPDATE cache_control.admission_state
SET state='excluding',
    target_epoch={target_epoch},
    safe_after_tick=NULL,
    hold_transition_id='transition-degraded'
WHERE singleton=true
  AND state='admitted'
  AND current_epoch={target_epoch - 1}
  AND hold_transition_id IS NULL
RETURNING current_epoch;
""",
    )
    if base.scalar(result) == "":
        raise RuntimeError("fleet exclusion could not atomically reserve its transition hold")


def exclusion_safe(tick: int) -> bool:
    safe = _ORIGINAL_EXCLUSION_SAFE(tick)
    if tick == 30:
        lease = _ISSUED_LEASES.get("bff-c")
        if lease is None:
            raise RuntimeError("unacknowledged BFF lease was not issued")
        if admit("identity", "session-fleet", lease, tick) != "ALLOW":
            raise RuntimeError(
                "fleet-barrier negative control failed: unretired live old lease was not genuinely authorizing"
            )
        if safe:
            raise RuntimeError("fleet barrier became safe while a genuine old positive lease still authorized")
    return safe


def _control_hold_state() -> tuple[str, int, str | None]:
    raw = base.control_scalar(
        """
SELECT state||'|'||current_epoch||'|'||COALESCE(hold_transition_id,'')
FROM cache_control.admission_state
WHERE singleton=true;
"""
    )
    state, epoch, hold = raw.split("|")
    return state, int(epoch), hold or None


def admit_new_epoch() -> bool:
    state, _epoch, hold = _control_hold_state()
    if state == "excluded" and hold is not None:
        return False
    return _ORIGINAL_ADMIT_NEW_EPOCH()


def commit_transition(
    owner: str,
    *,
    transition_id: str,
    owner_token: str,
    tick: int,
    cache_eligible: bool,
) -> bool:
    if transition_id == "transition-degraded":
        state, epoch, hold = _control_hold_state()
        durable_eligible = state == "excluded" and epoch == 2 and hold == transition_id
        if tick >= 61 and admit_new_epoch():
            raise RuntimeError("fleet exclusion hold did not block pre-commit cache re-entry")
        cache_eligible = cache_eligible and durable_eligible
    return _ORIGINAL_COMMIT(
        owner,
        transition_id=transition_id,
        owner_token=owner_token,
        tick=tick,
        cache_eligible=cache_eligible,
    )


def mark_reconciled(owner: str, transition_id: str) -> None:
    _ORIGINAL_MARK_RECONCILED(owner, transition_id)
    if transition_id != "transition-degraded":
        return
    if base.transition_state(owner, transition_id) != "finalized|0|1":
        raise RuntimeError("fleet exclusion hold release preceded source-owner finalization")
    role, password = base.CONTROL_ROLE
    result = base.pg_role(
        role,
        password,
        f"""
UPDATE cache_control.admission_state
SET hold_transition_id=NULL
WHERE singleton=true
  AND state='excluded'
  AND hold_transition_id={base.q(transition_id)}
RETURNING current_epoch;
""",
    )
    if base.scalar(result) != "2":
        raise RuntimeError("fleet exclusion hold was not released by exact finalized transition")


def start_stale_replica(resource_id: str, lease: base.BffLease) -> str:
    container = _ORIGINAL_START_STALE_REPLICA(resource_id, lease)
    # REPLICAOF NO ONE is the actual promotion event. Re-run the old-epoch
    # negative control after promotion so an empty/failed replica cannot pass.
    if _ORIGINAL_ADMIT(
        "identity",
        resource_id,
        lease,
        10,
        container=container,
        cli=base.CACHE_CLI,
    ) != "ALLOW":
        raise RuntimeError("promoted stale replica did not retain genuinely authorizing old positive bytes")
    return container


def start_restore_container(rdb_path):
    container = _ORIGINAL_START_RESTORE(rdb_path)
    old_lease = _ISSUED_LEASES.get("bff-c")
    if old_lease is None:
        raise RuntimeError("restore negative-control lease is absent")
    # Historical tick deliberately proves the restored bytes are complete and
    # would authorize under the retired epoch; the fresh epoch must be the
    # reason the current admission later rejects them.
    if _ORIGINAL_ADMIT(
        "identity",
        "session-fleet",
        old_lease,
        10,
        container=container,
        cli=base.CACHE_CLI,
    ) != "ALLOW":
        raise RuntimeError("stale RDB restore negative control did not reconstruct old positive authority")
    return container


def _takeover_transition(
    owner: str,
    transition_id: str,
    *,
    tick: int,
    new_owner: str,
    lease_until_tick: int,
) -> bool:
    role, password, _ = base.OWNER_CONFIG[owner]
    result = base.pg_role(
        role,
        password,
        f"""
UPDATE {owner}.security_cache_transition
SET owner_token={base.q(new_owner)}, lease_until_tick={lease_until_tick}
WHERE transition_id={base.q(transition_id)}
  AND state='prepared'
  AND lease_until_tick <= {tick}
RETURNING transition_id;
""",
    )
    return base.scalar(result) == transition_id


def prove_actual_cleanup_takeover_race() -> None:
    resource_id = "session-concurrent-race"
    base.insert_resource("identity", resource_id)
    base.set_cache_current("identity", resource_id, 1, 2)
    base.reserve_transition(
        "identity",
        transition_id="transition-concurrent-race",
        resource_id=resource_id,
        expected_generation=1,
        fingerprint="concurrent-race:v1",
        owner_token="writer-old",
        lease_until_tick=10,
    )
    if base.install_fence(
        "identity", resource_id, 1, "transition-concurrent-race", 2
    ) != "FENCED":
        raise RuntimeError("concurrency-race scope fence was not installed")

    start = threading.Barrier(3)
    outcomes: dict[str, bool] = {}

    def cleanup() -> None:
        start.wait()
        outcomes["cancel"] = base.cancel_transition(
            "identity", "transition-concurrent-race", 11
        )

    def recover() -> None:
        start.wait()
        outcomes["takeover"] = _takeover_transition(
            "identity",
            "transition-concurrent-race",
            tick=11,
            new_owner="writer-recovered",
            lease_until_tick=40,
        )

    threads = [threading.Thread(target=cleanup), threading.Thread(target=recover)]
    for thread in threads:
        thread.start()
    start.wait()
    for thread in threads:
        thread.join(timeout=20)
        if thread.is_alive():
            raise RuntimeError("cleanup/takeover concurrency proof did not terminate")

    if outcomes.get("cancel") == outcomes.get("takeover"):
        raise RuntimeError(f"cleanup/takeover race did not produce exactly one winner: {outcomes!r}")

    if outcomes["takeover"]:
        if not _ORIGINAL_COMMIT(
            "identity",
            transition_id="transition-concurrent-race",
            owner_token="writer-recovered",
            tick=12,
            cache_eligible=base.fence_is_exact(
                "identity", resource_id, "transition-concurrent-race"
            ),
        ):
            raise RuntimeError("winning recovered owner could not commit")
        base.set_cache_revoked("identity", resource_id, 2, 2, "transition-concurrent-race")
        _ORIGINAL_MARK_RECONCILED("identity", "transition-concurrent-race")
        if base.resource_state("identity", resource_id) != (2, False):
            raise RuntimeError("takeover winner did not produce one source revocation")
    else:
        if _ORIGINAL_COMMIT(
            "identity",
            transition_id="transition-concurrent-race",
            owner_token="writer-old",
            tick=12,
            cache_eligible=True,
        ):
            raise RuntimeError("cancel winner did not fence stale writer")
        if base.resource_state("identity", resource_id) != (1, True):
            raise RuntimeError("cancel winner allowed source mutation")
        base.set_cache_current("identity", resource_id, 1, 2)

    print(
        "d3_b_cleanup_takeover_actual_concurrency=PASS "
        "simultaneous_source_owner_race=true exactly_one_durable_winner=true "
        "cancel_fences_writer=true takeover_rebinds_owner_lease=true source_effect_at_most_once=true"
    )


def prove_fence_continuity_loss_fail_closed() -> None:
    resource_id = "session-fence-continuity-loss"
    base.insert_resource("identity", resource_id)
    base.set_cache_current("identity", resource_id, 1, 2)
    base.reserve_transition(
        "identity",
        transition_id="transition-fence-loss",
        resource_id=resource_id,
        expected_generation=1,
        fingerprint="fence-loss:v1",
        owner_token="writer-fence-loss",
        lease_until_tick=40,
    )
    if base.install_fence("identity", resource_id, 1, "transition-fence-loss", 2) != "FENCED":
        raise RuntimeError("fence-loss vector could not install initial fence")
    base.cache_cmd("DEL", base.authority_key("identity", resource_id))
    if base.fence_is_exact("identity", resource_id, "transition-fence-loss"):
        raise RuntimeError("deleted cache fence was still treated as commit-eligible")
    if _ORIGINAL_COMMIT(
        "identity",
        transition_id="transition-fence-loss",
        owner_token="writer-fence-loss",
        tick=20,
        cache_eligible=False,
    ):
        raise RuntimeError("source mutation committed after cache-fence continuity loss")
    if base.resource_state("identity", resource_id) != (1, True):
        raise RuntimeError("cache-fence continuity loss mutated source authority")
    print(
        "d3_b_precommit_fence_continuity_loss=PASS "
        "fence_installed_then_lost=true commit_eligibility_invalidated=true source_truth_unchanged=true"
    )


def prove_business_owner_transition_isolation() -> None:
    identity_before = base.resource_state("identity", "owner-session")
    cases = (
        ("membership", "owner-membership"),
        ("authz", "owner-permission"),
        ("platform", "owner-tenant"),
    )
    for owner, resource_id in cases:
        base.set_cache_current(owner, resource_id, 1, 2)
        transition_id = f"transition-owner-{owner}"
        owner_token = f"writer-owner-{owner}"
        base.reserve_transition(
            owner,
            transition_id=transition_id,
            resource_id=resource_id,
            expected_generation=1,
            fingerprint=f"owner-boundary:{owner}:v1",
            owner_token=owner_token,
            lease_until_tick=40,
        )
        if base.install_fence(owner, resource_id, 1, transition_id, 2) != "FENCED":
            raise RuntimeError(f"{owner} could not install its own authority-scope cache fence")
        if not _ORIGINAL_COMMIT(
            owner,
            transition_id=transition_id,
            owner_token=owner_token,
            tick=20,
            cache_eligible=base.fence_is_exact(owner, resource_id, transition_id),
        ):
            raise RuntimeError(f"{owner} could not commit its own bounded authority transition")
        base.set_cache_revoked(owner, resource_id, 2, 2, transition_id)
        _ORIGINAL_MARK_RECONCILED(owner, transition_id)
        if base.resource_state(owner, resource_id) != (2, False):
            raise RuntimeError(f"{owner} source truth did not change under its own authority")
        if base.resource_state("identity", "owner-session") != identity_before:
            raise RuntimeError(f"{owner} transition laundered business mutation into session authority")

    print(
        "d3_b_cross_owner_transition_isolation=PASS "
        "membership_transition_owner_local=true authorization_transition_owner_local=true "
        "tenant_transition_owner_local=true identity_session_truth_not_surrogate_owner=true"
    )


def prove_actual_bulkhead_concurrency() -> None:
    resource_id = "session-owner-read"
    bulkhead = base.OwnerReadBulkhead(capacity=2)
    ready = threading.Barrier(3)
    release = threading.Event()
    results: list[tuple[int, bool]] = []
    errors: list[str] = []

    def holder() -> None:
        if not bulkhead.acquire_for_test():
            errors.append("holder could not acquire bulkhead")
            return
        try:
            ready.wait()
            if not release.wait(timeout=10):
                errors.append("holder release timeout")
                return
            results.append(base.resource_state("identity", resource_id))
        finally:
            bulkhead.release_for_test()

    threads = [threading.Thread(target=holder), threading.Thread(target=holder)]
    for thread in threads:
        thread.start()
    ready.wait()

    called = [False]

    def overflow_read():
        called[0] = True
        return base.resource_state("identity", resource_id)

    admitted, value = bulkhead.try_read(overflow_read)
    if admitted or value is not None or called[0]:
        raise RuntimeError("actual concurrent bulkhead overflow reached durable owner I/O")
    release.set()
    for thread in threads:
        thread.join(timeout=20)
        if thread.is_alive():
            raise RuntimeError("bulkhead concurrency holder did not terminate")
    if errors or results != [(1, True), (1, True)]:
        raise RuntimeError(f"bounded concurrent owner reads did not complete cleanly: {errors!r} {results!r}")

    print(
        "d3_b_degraded_owner_bulkhead_actual_concurrency=PASS "
        "two_owner_reads_inflight=true third_denied_before_io=true bounded_slots_released=true"
    )


def main() -> int:
    base.setup_postgres = setup_postgres
    base.issue_lease = issue_lease
    base.retire_lease = retire_lease
    base.admit = admit
    base.begin_exclusion = begin_exclusion
    base.exclusion_safe = exclusion_safe
    base.admit_new_epoch = admit_new_epoch
    base.commit_transition = commit_transition
    base.mark_reconciled = mark_reconciled
    base.start_stale_replica = start_stale_replica
    base.start_restore_container = start_restore_container

    result = base.main()
    prove_actual_cleanup_takeover_race()
    prove_fence_continuity_loss_fail_closed()
    prove_business_owner_transition_isolation()
    prove_actual_bulkhead_concurrency()
    print(
        "d3_b_session_cache_conformance_hardening=PASS "
        "fleet_exclusion_transition_hold=true precommit_reentry_blocked=true "
        "actual_cleanup_takeover_race=true precommit_fence_loss_fail_closed=true "
        "cross_owner_transition_isolation=true actual_bulkhead_concurrency=true "
        "restore_and_promoted_replica_negative_controls=true"
    )
    return result


if __name__ == "__main__":
    raise SystemExit(main())
