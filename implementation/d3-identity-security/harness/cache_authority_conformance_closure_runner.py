from __future__ import annotations

import threading
import time

import cache_authority_conformance_review_runner as review

core = review.core
final = review.final

_LEASE_MUTATION_KEYS: set[tuple[str, str]] = set()


def _enter_lease_mutation(key: tuple[str, str]) -> None:
    with review._LEASE_COND:
        while key in _LEASE_MUTATION_KEYS:
            review._LEASE_COND.wait(timeout=1.0)
        _LEASE_MUTATION_KEYS.add(key)


def _leave_lease_mutation(key: tuple[str, str]) -> None:
    with review._LEASE_COND:
        if key not in _LEASE_MUTATION_KEYS:
            raise RuntimeError("lease lifecycle mutation ownership was lost")
        _LEASE_MUTATION_KEYS.remove(key)
        review._LEASE_COND.notify_all()


def issue_scope_lease(
    scope: str,
    replica_id: str,
    epoch: int,
    valid_until_tick: int,
) -> core.BffLease:
    key = (scope, replica_id)
    _enter_lease_mutation(key)
    try:
        return review.issue_scope_lease(scope, replica_id, epoch, valid_until_tick)
    finally:
        _leave_lease_mutation(key)


def retire_scope_lease(lease: core.BffLease) -> None:
    key = (lease.scope_key, lease.replica_id)
    _enter_lease_mutation(key)
    try:
        review.retire_scope_lease(lease)
    finally:
        _leave_lease_mutation(key)


def install_closure_patches() -> None:
    review.install_patches()
    core.issue_scope_lease = issue_scope_lease
    core.retire_scope_lease = retire_scope_lease
    final.issue_scope_lease = issue_scope_lease
    final.retire_scope_lease = retire_scope_lease


def prove_retire_reissue_same_replica_serialization() -> None:
    owner = "identity"
    rid = "session-retire-reissue-race"
    scope = core.scope_key(owner, rid)
    replica = "bff-retire-reissue-race"
    core.insert_resource(owner, rid)
    core.set_cache_current(owner, rid, 1, 1)
    old = issue_scope_lease(scope, replica, 1, 50)

    entered = threading.Event()
    release_reader = threading.Event()
    reader_result: list[str] = []

    def sleeping_reader() -> None:
        if not review._begin_admission([old], 10):
            raise RuntimeError("retire/reissue negative control could not enter admission")
        entered.set()
        try:
            if not release_reader.wait(10):
                raise RuntimeError("retire/reissue sleeping reader timed out")
            reader_result.append(review._ORIGINAL_ADMIT(owner, rid, old, 10))
        finally:
            review._end_admission([old])

    reader = threading.Thread(target=sleeping_reader)
    reader.start()
    if not entered.wait(10):
        raise RuntimeError("retire/reissue sleeping reader did not become in-flight")

    retire_done = threading.Event()

    def retire_old() -> None:
        retire_scope_lease(old)
        retire_done.set()

    retire_thread = threading.Thread(target=retire_old)
    retire_thread.start()

    # Wait until retirement owns the lifecycle key and has invalidated the local latch.
    for _ in range(100):
        with review._LEASE_COND:
            owns = (scope, replica) in _LEASE_MUTATION_KEYS
            latch_present = final._ACTIVE_LOCAL_LEASE.get((scope, replica)) == id(old)
        if owns and not latch_present:
            break
        time.sleep(0.02)
    else:
        raise RuntimeError("retirement did not enter drain-owned lifecycle state")

    replacement_box: list[core.BffLease] = []

    def reissue() -> None:
        replacement_box.append(issue_scope_lease(scope, replica, 1, 120))

    reissue_thread = threading.Thread(target=reissue)
    reissue_thread.start()
    time.sleep(0.2)

    if retire_done.is_set() or replacement_box:
        raise RuntimeError("retirement/reissue escaped sleeping-reader lifecycle serialization")
    durable = core.control_scalar(
        f"SELECT valid_until_tick||'|'||CASE WHEN retired THEN '1' ELSE '0' END "
        f"FROM cache_control.scope_lease WHERE scope_key={core.q(scope)} AND replica_id={core.q(replica)};"
    )
    if durable != "50|0":
        raise RuntimeError(f"durable lease changed before old admission drained: {durable!r}")

    release_reader.set()
    reader.join(20)
    retire_thread.join(20)
    reissue_thread.join(20)
    if reader.is_alive() or retire_thread.is_alive() or reissue_thread.is_alive():
        raise RuntimeError("retirement/reissue race did not terminate")
    if reader_result != ["ALLOW"] or not retire_done.is_set() or len(replacement_box) != 1:
        raise RuntimeError("retirement/reissue race lost a required negative control")

    replacement = replacement_box[0]
    durable_after = core.control_scalar(
        f"SELECT valid_until_tick||'|'||CASE WHEN retired THEN '1' ELSE '0' END "
        f"FROM cache_control.scope_lease WHERE scope_key={core.q(scope)} AND replica_id={core.q(replica)};"
    )
    if durable_after != "120|0":
        raise RuntimeError(f"stale retirement ACK clobbered replacement lease: {durable_after!r}")
    if review.admit(owner, rid, old, 20) != "DENY":
        raise RuntimeError("retired predecessor revived after concurrent reissue")
    if review.admit(owner, rid, replacement, 20) != "ALLOW":
        raise RuntimeError("serialized replacement lease did not become current")

    print(
        "d3_b_same_replica_retire_reissue_serialization=PASS "
        "one_lifecycle_mutator_per_scope_replica=true retirement_owns_drain_window=true "
        "reissue_waits_for_retirement_ack=true stale_retirement_cannot_clobber_replacement=true "
        "predecessor_denied_replacement_admitted=true"
    )


def main() -> int:
    install_closure_patches()

    # Run the full prior chain under the stronger per-replica lifecycle serializer.
    if final.main() != 0:
        raise RuntimeError("prior final D3-B conformance failed under closure patches")
    review.prove_forged_commit_permit_rejected()
    review.prove_retirement_drains_inflight_admissions()
    review.prove_same_replica_reissue_waits_for_inflight()
    review.prove_current_epoch_stale_restore_cannot_resurrect()
    prove_retire_reissue_same_replica_serialization()

    print(
        "d3_b_session_cache_conformance_closure=PASS "
        "prior_review_vectors_preserved=true per_replica_lifecycle_serialized=true "
        "retire_reissue_race_closed=true"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
