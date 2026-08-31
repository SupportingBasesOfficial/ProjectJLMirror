from __future__ import annotations

import threading
import time

import cache_authority_conformance_final_runner as final

core = final.core

_ORIGINAL_ACQUIRE_PERMIT = core.acquire_commit_permit
_ORIGINAL_COMMIT_SOURCE = core.commit_source
_ORIGINAL_RELEASE_SCOPE = core.release_scope_after_terminal
_ORIGINAL_ISSUE_LEASE = final._ORIGINAL_ISSUE
_ORIGINAL_RETIRE_LEASE = final._ORIGINAL_RETIRE
_ORIGINAL_ADMIT = final._ORIGINAL_ADMIT

_ISSUED_PERMITS: dict[int, core.CommitPermit] = {}
_LEASE_COND = threading.Condition()
_INFLIGHT_BY_LEASE: dict[int, int] = {}


def acquire_commit_permit(owner: str, transition_id: str) -> core.CommitPermit:
    permit = _ORIGINAL_ACQUIRE_PERMIT(owner, transition_id)
    _ISSUED_PERMITS[id(permit)] = permit
    return permit


def commit_source(
    owner: str,
    transition_id: str,
    owner_token: str,
    tick: int,
    permit: core.CommitPermit | None = None,
) -> bool:
    try:
        permit = permit or acquire_commit_permit(owner, transition_id)
    except RuntimeError:
        return False
    if _ISSUED_PERMITS.get(id(permit)) is not permit:
        return False
    if permit.transition_id != transition_id:
        return False
    state, epoch, target, hold = core.scope_state(permit.scope_key)
    if state != "excluded" or target != epoch or hold != transition_id or epoch != permit.epoch:
        return False
    return _ORIGINAL_COMMIT_SOURCE(owner, transition_id, owner_token, tick, permit)


def release_scope_after_terminal(owner: str, transition_id: str, *, cancelled: bool = False) -> int:
    if cancelled:
        return _ORIGINAL_RELEASE_SCOPE(owner, transition_id, cancelled=True)
    if core.transition_state(owner, transition_id) != "finalized|0|1":
        raise RuntimeError("scope release attempted before exact finalized source terminal state")
    resource_id = core.owner_scalar(
        owner,
        f"SELECT resource_id FROM {owner}.security_cache_transition WHERE transition_id={core.q(transition_id)};",
    )
    if not resource_id:
        raise RuntimeError("finalized scope release resource absent")
    scope = core.scope_key(owner, resource_id)
    role, password = core.CONTROL_ROLE
    result = core.pg_role(
        role,
        password,
        f"""
DO $d3$
DECLARE v_state text; v_epoch bigint; v_hold text;
BEGIN
  SELECT state,current_epoch,hold_transition_id INTO v_state,v_epoch,v_hold
  FROM cache_control.scope_admission WHERE scope_key={core.q(scope)} FOR UPDATE;
  IF NOT FOUND OR v_state <> 'excluded' OR v_hold <> {core.q(transition_id)} THEN
    RAISE EXCEPTION 'exact finalized exclusion hold is absent';
  END IF;
  UPDATE cache_control.scope_admission
  SET state='admitted',current_epoch=v_epoch+1,target_epoch=NULL,hold_transition_id=NULL,safe_after_tick=NULL
  WHERE scope_key={core.q(scope)} AND state='excluded' AND hold_transition_id={core.q(transition_id)};
END
$d3$;
""",
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError("finalized scope could not rotate readmission epoch atomically")
    state, epoch, target, hold = core.scope_state(scope)
    if state != "admitted" or target is not None or hold is not None:
        raise RuntimeError("finalized scope release did not restore admitted state")
    return epoch


def _wait_drained(lease_id: int) -> None:
    while _INFLIGHT_BY_LEASE.get(lease_id, 0) > 0:
        _LEASE_COND.wait(timeout=1.0)


def issue_scope_lease(
    scope: str,
    replica_id: str,
    epoch: int,
    valid_until_tick: int,
) -> core.BffLease:
    key = (scope, replica_id)
    with _LEASE_COND:
        predecessor = final._ACTIVE_LOCAL_LEASE.pop(key, None)
        if predecessor is not None:
            _wait_drained(predecessor)
        lease = _ORIGINAL_ISSUE_LEASE(scope, replica_id, epoch, valid_until_tick)
        final._ACTIVE_LOCAL_LEASE[key] = id(lease)
        return lease


def retire_scope_lease(lease: core.BffLease) -> None:
    key = (lease.scope_key, lease.replica_id)
    lease_id = id(lease)
    with _LEASE_COND:
        if final._ACTIVE_LOCAL_LEASE.get(key) == lease_id:
            del final._ACTIVE_LOCAL_LEASE[key]
        _wait_drained(lease_id)
        _ORIGINAL_RETIRE_LEASE(lease)


def _begin_admission(leases: list[core.BffLease], tick: int) -> bool:
    unique: dict[int, core.BffLease] = {id(lease): lease for lease in leases}
    with _LEASE_COND:
        for lease_id, lease in unique.items():
            if tick >= lease.valid_until_tick:
                return False
            if final._ACTIVE_LOCAL_LEASE.get((lease.scope_key, lease.replica_id)) != lease_id:
                return False
        for lease_id in unique:
            _INFLIGHT_BY_LEASE[lease_id] = _INFLIGHT_BY_LEASE.get(lease_id, 0) + 1
        return True


def _end_admission(leases: list[core.BffLease]) -> None:
    unique_ids = set(map(id, leases))
    with _LEASE_COND:
        for lease_id in unique_ids:
            remaining = _INFLIGHT_BY_LEASE.get(lease_id, 0) - 1
            if remaining <= 0:
                _INFLIGHT_BY_LEASE.pop(lease_id, None)
            else:
                _INFLIGHT_BY_LEASE[lease_id] = remaining
        _LEASE_COND.notify_all()


def _local_lease_current(lease: core.BffLease, tick: int) -> bool:
    with _LEASE_COND:
        return (
            tick < lease.valid_until_tick
            and final._ACTIVE_LOCAL_LEASE.get((lease.scope_key, lease.replica_id)) == id(lease)
        )


def admit(
    owner: str,
    resource_id: str,
    lease: core.BffLease,
    tick: int,
    *,
    container: str | None = None,
    cli: str | None = None,
) -> str:
    if not _begin_admission([lease], tick):
        return "DENY"
    try:
        return _ORIGINAL_ADMIT(
            owner,
            resource_id,
            lease,
            tick,
            container=container,
            cli=cli,
        )
    finally:
        _end_admission([lease])


def composed_admit(
    resources: dict[str, str],
    leases: dict[str, core.BffLease],
    tick: int,
) -> str:
    order = ("identity", "membership", "authz", "platform")
    selected = [leases[owner] for owner in order]
    if not _begin_admission(selected, tick):
        return "DENY"
    try:
        return core.cache_scalar(
            "EVAL",
            final.COMPOSED_ADMISSION_SCRIPT,
            "5",
            *(core.authority_key(owner, resources[owner]) for owner in order),
            final.composed_positive_key(resources["identity"]),
            *(str(leases[owner].epoch) for owner in order),
        )
    finally:
        _end_admission(selected)


def degraded_owner_read_and_fill(
    owner: str,
    resource_id: str,
    lease: core.BffLease,
    bulkhead: core.OwnerReadBulkhead,
) -> str:
    if not _begin_admission([lease], 20):
        return "DENY"
    try:
        def read_then_fill() -> str:
            generation, active = core.resource_state(owner, resource_id)
            if not active:
                return "DENY"
            if final.fill_positive_if_current(owner, resource_id, generation, lease.epoch) != "FILLED":
                return "DENY"
            return _ORIGINAL_ADMIT(owner, resource_id, lease, 20)

        admitted_owner, result = bulkhead.try_read(read_then_fill)
        if not admitted_owner or result != "ALLOW":
            return "DENY"
        return "ALLOW"
    finally:
        _end_admission([lease])


def prove_forged_commit_permit_rejected() -> None:
    owner = "identity"
    rid = "session-forged-permit"
    scope = core.scope_key(owner, rid)
    tid = "transition-forged-permit"
    token = "writer-forged-permit"
    core.insert_resource(owner, rid)
    core.set_cache_current(owner, rid, 1, 1)
    core.reserve_transition(owner, tid, rid, 1, "forged-permit:v1", token, 100)

    forged_before = core.CommitPermit(scope_key=scope, transition_id=tid, epoch=1)
    if commit_source(owner, tid, token, 2, forged_before):
        raise RuntimeError("caller-forged permit committed before fleet exclusion")

    core.begin_scope_exclusion(scope, tid)
    if not core.finalize_scope_exclusion(scope, tid, 1):
        raise RuntimeError("forged-permit vector could not complete exclusion")
    state, epoch, target, hold = core.scope_state(scope)
    if state != "excluded" or target != epoch or hold != tid:
        raise RuntimeError("forged-permit vector lost completed barrier")

    forged_exact = core.CommitPermit(scope_key=scope, transition_id=tid, epoch=epoch)
    if commit_source(owner, tid, token, 2, forged_exact):
        raise RuntimeError("caller-forged exact-field permit bypassed issuance registry")

    legitimate = acquire_commit_permit(owner, tid)
    if not commit_source(owner, tid, token, 2, legitimate):
        raise RuntimeError("barrier-issued permit could not commit exact source transition")
    core.reconcile_cache_and_finalize_source(owner, tid)
    release_scope_after_terminal(owner, tid)

    print(
        "d3_b_commit_permit_provenance=PASS "
        "prebarrier_forgery_rejected=true exact_field_forgery_rejected=true "
        "issued_object_identity_required=true durable_epoch_hold_revalidated=true"
    )


def prove_retirement_drains_inflight_admissions() -> None:
    owner = "identity"
    rid = "session-retirement-drain"
    scope = core.scope_key(owner, rid)
    tid = "transition-retirement-drain"
    core.insert_resource(owner, rid)
    core.set_cache_current(owner, rid, 1, 1)
    lease = issue_scope_lease(scope, "bff-drain", 1, 200)
    core.reserve_transition(owner, tid, rid, 1, "retirement-drain:v1", "writer-drain", 300)
    core.begin_scope_exclusion(scope, tid)

    entered = threading.Event()
    release_reader = threading.Event()
    reader_result: list[str] = []

    def sleeping_reader() -> None:
        if not _begin_admission([lease], 10):
            raise RuntimeError("sleeping-reader negative control could not enter admission")
        entered.set()
        try:
            if not release_reader.wait(10):
                raise RuntimeError("sleeping-reader release timeout")
            reader_result.append(_ORIGINAL_ADMIT(owner, rid, lease, 10))
        finally:
            _end_admission([lease])

    reader = threading.Thread(target=sleeping_reader)
    reader.start()
    if not entered.wait(10):
        raise RuntimeError("sleeping reader did not become in-flight")

    retired = threading.Event()

    def retire() -> None:
        retire_scope_lease(lease)
        retired.set()

    retire_thread = threading.Thread(target=retire)
    retire_thread.start()
    time.sleep(0.2)
    if retired.is_set():
        raise RuntimeError("retirement ACK became durable before in-flight admission drained")
    retired_flag = core.control_scalar(
        f"SELECT CASE WHEN retired THEN '1' ELSE '0' END FROM cache_control.scope_lease WHERE scope_key={core.q(scope)} AND replica_id='bff-drain';"
    )
    if retired_flag != "0":
        raise RuntimeError("durable lease retirement became barrier-visible before local drain")
    if core.finalize_scope_exclusion(scope, tid, 20):
        raise RuntimeError("fleet barrier closed while sleeping old admission remained in-flight")

    release_reader.set()
    reader.join(20)
    retire_thread.join(20)
    if reader.is_alive() or retire_thread.is_alive() or not retired.is_set():
        raise RuntimeError("retirement drain concurrency proof did not terminate")
    if reader_result != ["ALLOW"]:
        raise RuntimeError("pre-retirement in-flight negative control was not genuinely authorizing")
    if not core.finalize_scope_exclusion(scope, tid, 20):
        raise RuntimeError("fleet barrier did not close after in-flight admission drained and ACKed")

    if not core.cancel_transition(owner, tid, 301):
        raise RuntimeError("retirement-drain transition did not cancel")
    current = release_scope_after_terminal(owner, tid, cancelled=True)
    core.set_cache_current(owner, rid, 1, current)

    print(
        "d3_b_lease_retirement_inflight_drain=PASS "
        "local_latch_invalidated_before_ack=true in_flight_admission_drained=true "
        "durable_retired_ack_after_drain=true barrier_waited_for_ack=true"
    )


def prove_same_replica_reissue_waits_for_inflight() -> None:
    owner = "identity"
    rid = "session-reissue-drain"
    scope = core.scope_key(owner, rid)
    core.insert_resource(owner, rid)
    core.set_cache_current(owner, rid, 1, 1)
    old = issue_scope_lease(scope, "bff-reissue-drain", 1, 50)

    entered = threading.Event()
    release_reader = threading.Event()

    def sleeping_reader() -> None:
        if not _begin_admission([old], 10):
            raise RuntimeError("reissue sleeping reader could not enter")
        entered.set()
        try:
            if not release_reader.wait(10):
                raise RuntimeError("reissue sleeping-reader timeout")
            if _ORIGINAL_ADMIT(owner, rid, old, 10) != "ALLOW":
                raise RuntimeError("reissue old reader was not genuinely authorizing")
        finally:
            _end_admission([old])

    reader = threading.Thread(target=sleeping_reader)
    reader.start()
    if not entered.wait(10):
        raise RuntimeError("reissue sleeping reader did not become in-flight")

    replacement_box: list[core.BffLease] = []

    def replace() -> None:
        replacement_box.append(issue_scope_lease(scope, "bff-reissue-drain", 1, 120))

    replacement_thread = threading.Thread(target=replace)
    replacement_thread.start()
    time.sleep(0.2)
    if replacement_box:
        raise RuntimeError("same-replica durable reissue overtook in-flight predecessor")
    valid_until = core.control_scalar(
        f"SELECT valid_until_tick FROM cache_control.scope_lease WHERE scope_key={core.q(scope)} AND replica_id='bff-reissue-drain';"
    )
    if valid_until != "50":
        raise RuntimeError("durable same-replica lease row changed before predecessor drain")

    release_reader.set()
    reader.join(20)
    replacement_thread.join(20)
    if reader.is_alive() or replacement_thread.is_alive() or len(replacement_box) != 1:
        raise RuntimeError("same-replica reissue drain proof did not terminate")
    replacement = replacement_box[0]
    if admit(owner, rid, old, 20) != "DENY":
        raise RuntimeError("drained predecessor revived after same-replica replacement")
    if admit(owner, rid, replacement, 20) != "ALLOW":
        raise RuntimeError("replacement lease failed after predecessor drain")

    print(
        "d3_b_same_replica_reissue_inflight_drain=PASS "
        "predecessor_invalidated_before_reissue=true durable_row_unchanged_until_drain=true "
        "replacement_issued_after_drain=true predecessor_cannot_revive=true"
    )


def prove_current_epoch_stale_restore_cannot_resurrect() -> None:
    owner = "identity"
    rid = "session-current-epoch-restore"
    scope = core.scope_key(owner, rid)
    tid = "transition-current-epoch-restore"
    token = "writer-current-epoch-restore"
    core.insert_resource(owner, rid)
    core.cache_cmd("FLUSHALL")
    core.set_cache_current(owner, rid, 1, 1)
    old = issue_scope_lease(scope, "bff-current-epoch-old", 1, 30)
    core.reserve_transition(owner, tid, rid, 1, "current-epoch-restore:v1", token, 100)
    core.begin_scope_exclusion(scope, tid)
    retire_scope_lease(old)
    if not core.finalize_scope_exclusion(scope, tid, 5):
        raise RuntimeError("current-epoch restore vector could not close exclusion")
    permit = acquire_commit_permit(owner, tid)
    if not commit_source(owner, tid, token, 6, permit):
        raise RuntimeError("current-epoch restore source transition did not commit")

    # Manufacture stale positive bytes carrying the just-completed exclusion epoch.
    core.set_cache_current(owner, rid, 1, permit.epoch)
    stale_epoch_lease = core.BffLease(scope, "negative-control-only", permit.epoch, 200)
    if core.raw_admit(owner, rid, stale_epoch_lease, 10) != "ALLOW":
        raise RuntimeError("current-epoch stale positive negative control was not genuinely authorizing")
    rdb = core.snapshot_rdb()
    standby = core.start_stale_replica(owner, rid, stale_epoch_lease)
    restore: str | None = None
    try:
        core.reconcile_cache_and_finalize_source(owner, tid)
        reentry_epoch = release_scope_after_terminal(owner, tid)
        if reentry_epoch <= permit.epoch:
            raise RuntimeError("finalized readmission did not rotate beyond stale excluded epoch")
        fresh = issue_scope_lease(scope, "bff-current-epoch-fresh", reentry_epoch, 220)
        restore = core.start_restore(rdb, owner, rid, stale_epoch_lease)
        if core.raw_admit(owner, rid, stale_epoch_lease, 10, container=standby, cli=core.CACHE_CLI) != "ALLOW":
            raise RuntimeError("promoted current-epoch stale replica lost its negative-control bytes")
        if core.raw_admit(owner, rid, stale_epoch_lease, 10, container=restore, cli=core.CACHE_CLI) != "ALLOW":
            raise RuntimeError("current-epoch stale RDB lost its negative-control bytes")
        if admit(owner, rid, fresh, 20, container=standby, cli=core.CACHE_CLI) != "DENY":
            raise RuntimeError("promoted current-epoch stale replica resurrected after reentry rotation")
        if admit(owner, rid, fresh, 20, container=restore, cli=core.CACHE_CLI) != "DENY":
            raise RuntimeError("current-epoch stale RDB resurrected after reentry rotation")
    finally:
        if restore is not None:
            core.run(["docker", "rm", "-f", restore], check=False)
        core.run(["docker", "rm", "-f", standby], check=False)
        try:
            rdb.unlink(missing_ok=True)
            rdb.parent.rmdir()
        except OSError:
            pass

    print(
        "d3_b_current_epoch_restore_nonresurrection=PASS "
        "stale_positive_carries_completed_exclusion_epoch=true stale_replica_promoted=true stale_rdb_restored=true "
        "readmission_rotates_epoch_again=true fresh_expected_evidence_blocks_both=true"
    )


def install_patches() -> None:
    core.acquire_commit_permit = acquire_commit_permit
    core.commit_source = commit_source
    core.release_scope_after_terminal = release_scope_after_terminal
    core.issue_scope_lease = issue_scope_lease
    core.retire_scope_lease = retire_scope_lease
    core.admit = admit
    final.issue_scope_lease = issue_scope_lease
    final.retire_scope_lease = retire_scope_lease
    final._local_lease_current = _local_lease_current
    final.admit = admit
    final.composed_admit = composed_admit
    final.degraded_owner_read_and_fill = degraded_owner_read_and_fill


def main() -> int:
    install_patches()
    if final.main() != 0:
        raise RuntimeError("prior final D3-B conformance gate failed")
    prove_forged_commit_permit_rejected()
    prove_retirement_drains_inflight_admissions()
    prove_same_replica_reissue_waits_for_inflight()
    prove_current_epoch_stale_restore_cannot_resurrect()
    print(
        "d3_b_session_cache_conformance_review=PASS "
        "commit_permit_provenance_enforced=true permit_epoch_hold_revalidated=true "
        "retirement_drains_inflight_admissions=true reissue_drains_predecessor=true "
        "finalized_readmission_rotates_epoch=true current_epoch_restore_nonresurrection=true"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
