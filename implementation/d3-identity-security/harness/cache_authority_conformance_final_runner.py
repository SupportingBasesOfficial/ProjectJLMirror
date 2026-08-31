from __future__ import annotations

import cache_authority_conformance_gate_runner as core


_ORIGINAL_ISSUE = core.issue_scope_lease
_ORIGINAL_RETIRE = core.retire_scope_lease
_ORIGINAL_ADMIT = core.admit
_ACTIVE_LOCAL_LEASE: dict[tuple[str, str], int] = {}


def issue_scope_lease(
    scope: str,
    replica_id: str,
    epoch: int,
    valid_until_tick: int,
) -> core.BffLease:
    """Issue trusted local expected-admission evidence with one exact latch identity.

    Durable cache-control state decides whether the scope/epoch is issuable. The
    BFF-local latch identity makes an older in-memory lease permanently stale when
    the same replica receives replacement evidence after retirement/re-entry.
    """
    lease = _ORIGINAL_ISSUE(scope, replica_id, epoch, valid_until_tick)
    _ACTIVE_LOCAL_LEASE[(scope, replica_id)] = id(lease)
    return lease


def retire_scope_lease(lease: core.BffLease) -> None:
    _ORIGINAL_RETIRE(lease)
    key = (lease.scope_key, lease.replica_id)
    if _ACTIVE_LOCAL_LEASE.get(key) == id(lease):
        del _ACTIVE_LOCAL_LEASE[key]


def admit(
    owner: str,
    resource_id: str,
    lease: core.BffLease,
    tick: int,
    *,
    container: str | None = None,
    cli: str | None = None,
) -> str:
    # No durable lookup is added to the healthy request path: this is local
    # expected-evidence identity. A replacement lease for the same replica changes
    # the latch and therefore cannot revive the predecessor capability.
    if _ACTIVE_LOCAL_LEASE.get((lease.scope_key, lease.replica_id)) != id(lease):
        return "DENY"
    return _ORIGINAL_ADMIT(
        owner,
        resource_id,
        lease,
        tick,
        container=container,
        cli=cli,
    )


# Install the hardened local expected-evidence boundary before any core scenario runs.
core.issue_scope_lease = issue_scope_lease
core.retire_scope_lease = retire_scope_lease
core.admit = admit


def prove_same_replica_reissue_cannot_revive_retired_lease() -> None:
    owner = "identity"
    resource_id = "session-lease-reissue"
    scope = core.scope_key(owner, resource_id)
    core.insert_resource(owner, resource_id)
    core.set_cache_current(owner, resource_id, 1, 1)

    old = issue_scope_lease(scope, "bff-reused", 1, 100)
    core.reserve_transition(
        owner,
        "transition-lease-reissue",
        resource_id,
        1,
        "lease-reissue:v1",
        "writer-lease-reissue",
        5,
    )
    core.begin_scope_exclusion(scope, "transition-lease-reissue")

    # Explicit retirement is what allows this barrier to finish before the old
    # lease's natural valid-until horizon. Therefore the retirement ACK must also
    # make the local predecessor capability permanently unusable.
    retire_scope_lease(old)
    if not core.finalize_scope_exclusion(scope, "transition-lease-reissue", 10):
        raise RuntimeError("retired old lease did not permit the bounded barrier to finish")
    if not core.cancel_transition(owner, "transition-lease-reissue", 10):
        raise RuntimeError("lease-reissue transition did not reach cancelled terminal state")

    state, current_epoch, _target, hold = core.scope_state(scope)
    if state != "excluded" or current_epoch != 2 or hold != "transition-lease-reissue":
        raise RuntimeError("lease-reissue barrier lost its exact excluded hold")

    # Source truth never changed; restore it at the new cache epoch, then release
    # only through the exact cancelled terminal transition.
    core.set_cache_current(owner, resource_id, 1, current_epoch)
    released = core.release_scope_after_terminal(
        owner,
        "transition-lease-reissue",
        cancelled=True,
    )
    if released != 2:
        raise RuntimeError("cancelled lease-reissue barrier changed the current epoch")

    replacement = issue_scope_lease(scope, "bff-reused", 2, 200)
    if id(replacement) == id(old):
        raise RuntimeError("lease identity negative control unexpectedly reused the predecessor object")

    # Reintroduce a genuinely authorizing old-epoch cache dataset. The raw cache
    # protocol would still accept the old predecessor at tick 20; the final BFF
    # admission boundary must reject it solely because replacement evidence rotated
    # the local latch identity.
    core.set_cache_current(owner, resource_id, 1, 1)
    if core.raw_admit(owner, resource_id, old, 20) != "ALLOW":
        raise RuntimeError("old lease negative control was not genuinely authorizing against stale bytes")
    if admit(owner, resource_id, old, 20) != "DENY":
        raise RuntimeError("replacement lease revived retired predecessor capability")
    if admit(owner, resource_id, replacement, 20) != "DENY":
        raise RuntimeError("replacement epoch admitted stale old-epoch cache bytes")

    core.set_cache_current(owner, resource_id, 1, 2)
    if admit(owner, resource_id, replacement, 20) != "ALLOW":
        raise RuntimeError("current replacement lease did not authorize current source-derived cache state")

    print(
        "d3_b_lease_identity_rotation=PASS "
        "retirement_before_expiry=true same_replica_reissue=true predecessor_raw_negative_control_allow=true "
        "predecessor_final_admission_denied=true replacement_epoch_blocks_stale_bytes=true "
        "replacement_current_state_admitted=true"
    )


def main() -> int:
    if core.main() != 0:
        raise RuntimeError("core D3-B conformance gate failed")
    prove_same_replica_reissue_cannot_revive_retired_lease()
    print(
        "d3_b_session_cache_conformance_final=PASS "
        "monotonic_scope_commit_permit=true lease_latch_identity_rotates=true "
        "old_lease_cannot_revive_after_same_replica_reissue=true "
        "reconciliation_exact_non_authority=true restore_failover_nonresurrection=true"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
