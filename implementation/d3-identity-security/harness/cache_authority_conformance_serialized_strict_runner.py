from __future__ import annotations

import threading

import cache_authority_conformance_serialized_runner as base


_ORIGINAL_FINALIZE_SOURCE_RECONCILIATION = base.finalize_source_reconciliation


def _transition_details(owner: str, transition_id: str) -> tuple[str, int]:
    raw = base.owner_scalar(
        owner,
        f"SELECT resource_id||'|'||COALESCE(committed_generation::text,'') FROM {owner}.security_cache_transition WHERE transition_id={base.q(transition_id)};",
    )
    if not raw:
        raise RuntimeError("transition details absent")
    resource_id, generation = raw.split("|")
    if not generation:
        raise RuntimeError("transition has no committed generation")
    return resource_id, int(generation)


def _cache_revocation_exact(owner: str, resource_id: str, generation: int, epoch: int, transition_id: str) -> bool:
    result = base.cache_cmd(
        "HMGET",
        base.authority_key(owner, resource_id),
        "state",
        "generation",
        "transition_id",
        "admission_epoch",
    )
    values = [line.strip() for line in result.stdout.splitlines()]
    return values == ["revoked", str(generation), transition_id, str(epoch)]


def finalize_source_reconciliation(owner: str, transition_id: str) -> None:
    resource_id, generation = _transition_details(owner, transition_id)
    scope = base.scope_key(owner, resource_id)
    state, epoch, target, hold = base.scope_state(scope)
    if state != "excluded" or target != epoch or hold != transition_id:
        raise RuntimeError("reconciliation attempted without exact durable exclusion hold")
    if not _cache_revocation_exact(owner, resource_id, generation, epoch, transition_id):
        raise RuntimeError("reconciliation cannot complete before exact non-authorizing cache convergence")
    _ORIGINAL_FINALIZE_SOURCE_RECONCILIATION(owner, transition_id)


def release_scope_after_terminal(owner: str, transition_id: str, *, cancelled: bool = False) -> int:
    expected = "cancelled|0|0" if cancelled else "finalized|0|1"
    if base.transition_state(owner, transition_id) != expected:
        raise RuntimeError("scope release attempted before exact durable source terminal state")
    resource_id = base.owner_scalar(
        owner,
        f"SELECT resource_id FROM {owner}.security_cache_transition WHERE transition_id={base.q(transition_id)};",
    )
    if not resource_id:
        raise RuntimeError("scope release transition resource absent")
    scope = base.scope_key(owner, resource_id)
    role, password = base.CONTROL_ROLE
    result = base.pg_role(
        role,
        password,
        f"""
DO $d3$
DECLARE v_state text; v_epoch bigint; v_hold text;
BEGIN
  SELECT state,current_epoch,hold_transition_id INTO v_state,v_epoch,v_hold
  FROM cache_control.scope_admission WHERE scope_key={base.q(scope)} FOR UPDATE;
  IF NOT FOUND THEN RAISE EXCEPTION 'scope admission state absent'; END IF;
  IF v_hold <> {base.q(transition_id)} THEN RAISE EXCEPTION 'scope hold belongs to another transition'; END IF;
  IF {str(cancelled).lower()} THEN
    IF v_state NOT IN ('excluding','excluded') THEN RAISE EXCEPTION 'cancelled transition has no releasable hold'; END IF;
    UPDATE cache_control.scope_admission
    SET state='admitted',target_epoch=NULL,hold_transition_id=NULL,safe_after_tick=NULL
    WHERE scope_key={base.q(scope)} AND hold_transition_id={base.q(transition_id)};
  ELSE
    IF v_state <> 'excluded' THEN RAISE EXCEPTION 'finalized transition must release from excluded state'; END IF;
    UPDATE cache_control.scope_admission
    SET state='admitted',target_epoch=NULL,hold_transition_id=NULL
    WHERE scope_key={base.q(scope)} AND hold_transition_id={base.q(transition_id)};
  END IF;
END
$d3$;
""",
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError("exact terminal transition could not release scope admission hold")
    state, epoch, target, hold = base.scope_state(scope)
    if state != "admitted" or target is not None or hold is not None:
        raise RuntimeError("scope release did not atomically restore admitted state")
    return epoch


def prove_lease_issue_exclusion_serialization() -> None:
    owner = "identity"
    rid = "session-lease-race"
    scope = base.scope_key(owner, rid)
    base.insert_resource(owner, rid)
    base.set_cache_current(owner, rid, 1, 1)
    initial = base.issue_scope_lease(scope, "bff-race", 1, 40)
    base.reserve_transition(owner, "transition-lease-race", rid, 1, "lease-race:v1", "writer-race", 200)

    start = threading.Barrier(3)
    outcomes: dict[str, bool] = {}

    def renew() -> None:
        start.wait()
        try:
            base.issue_scope_lease(scope, "bff-race", 1, 100)
            outcomes["renew"] = True
        except RuntimeError:
            outcomes["renew"] = False

    def exclude() -> None:
        start.wait()
        try:
            base.begin_scope_exclusion(scope, "transition-lease-race")
            outcomes["exclude"] = True
        except RuntimeError:
            outcomes["exclude"] = False

    threads = [threading.Thread(target=renew), threading.Thread(target=exclude)]
    for thread in threads:
        thread.start()
    start.wait()
    for thread in threads:
        thread.join(20)
    if any(thread.is_alive() for thread in threads) or not outcomes.get("exclude"):
        raise RuntimeError(f"lease/exclusion serialization failed: {outcomes!r}")

    try:
        base.issue_scope_lease(scope, "late-old", 1, 150)
    except RuntimeError:
        pass
    else:
        raise RuntimeError("old-epoch lease issued after exclusion transaction")

    if outcomes.get("renew"):
        renewed = base.BffLease(scope, "bff-race", 1, 100)
        if base.raw_admit(owner, rid, renewed, 50) != "ALLOW":
            raise RuntimeError("renewal-first negative control was not genuinely live")
        if base.finalize_scope_exclusion(scope, "transition-lease-race", 50):
            raise RuntimeError("renewal-first lease escaped barrier count")
        if not base.finalize_scope_exclusion(scope, "transition-lease-race", 101):
            raise RuntimeError("barrier did not close after renewed lease horizon")
    else:
        if base.raw_admit(owner, rid, initial, 20) != "ALLOW":
            raise RuntimeError("initial old lease was not genuinely authorizing")
        if not base.finalize_scope_exclusion(scope, "transition-lease-race", 41):
            raise RuntimeError("exclusion-first ordering failed after initial lease horizon")

    if not base.cancel_transition(owner, "transition-lease-race", 201):
        raise RuntimeError("lease-race transition cleanup did not cancel")
    state, epoch, _target, hold = base.scope_state(scope)
    if state != "excluded" or hold != "transition-lease-race":
        raise RuntimeError("lease-race barrier lost exact hold")
    base.set_cache_current(owner, rid, 1, epoch)
    released_epoch = release_scope_after_terminal(owner, "transition-lease-race", cancelled=True)
    fresh = base.issue_scope_lease(scope, "bff-after-cancel", released_epoch, 260)
    if base.admit(owner, rid, fresh, 210) != "ALLOW":
        raise RuntimeError("cancelled transition did not restore admission from unchanged owner truth")

    print(
        "d3_b_lease_issue_exclusion_serialization=PASS "
        "same_row_serialization=true renewal_first_counted=true exclusion_first_rejects_renewal=true "
        "post_exclusion_old_lease_rejected=true cancelled_excluded_release_uses_terminal_api=true"
    )


def prove_reconciliation_readmission_requires_exact_cache_convergence() -> None:
    owner = "identity"
    rid = "session-reconciliation-gate"
    scope = base.scope_key(owner, rid)
    tid = "transition-reconciliation-gate"
    token = "writer-reconciliation-gate"
    base.insert_resource(owner, rid)
    base.set_cache_current(owner, rid, 1, 1)
    base.reserve_transition(owner, tid, rid, 1, "reconciliation-gate:v1", token, 100)
    base.begin_scope_exclusion(scope, tid)
    if not base.finalize_scope_exclusion(scope, tid, 1):
        raise RuntimeError("reconciliation-gate exclusion failed")
    if not base.commit_source(owner, tid, token, 2):
        raise RuntimeError("reconciliation-gate source commit failed")

    try:
        finalize_source_reconciliation(owner, tid)
    except RuntimeError:
        pass
    else:
        raise RuntimeError("reconciliation completed without exact cache convergence")
    try:
        release_scope_after_terminal(owner, tid)
    except RuntimeError:
        pass
    else:
        raise RuntimeError("scope readmitted before durable reconciliation finalization")

    base.set_cache_revoked(owner, rid, 2, 2, tid)
    finalize_source_reconciliation(owner, tid)
    epoch = release_scope_after_terminal(owner, tid)
    fresh = base.issue_scope_lease(scope, "bff-reconciliation-fresh", epoch, 150)
    if base.admit(owner, rid, fresh, 10) != "DENY":
        raise RuntimeError("fresh expected evidence authorized a reconciled revoked owner generation")

    print(
        "d3_b_reconciliation_readmission_exact_cache_convergence=PASS "
        "reconciliation_requires_exact_revoked_generation=true transition_identity_bound=true "
        "scope_hold_persists_until_owner_finalized=true fresh_readmission_remains_non_authorizing=true"
    )


def prove_release_cannot_overtake_source_commit() -> None:
    owner = "identity"
    rid = "session-release-commit-race"
    scope = base.scope_key(owner, rid)
    tid = "transition-release-commit-race"
    token = "writer-release-commit-race"
    base.insert_resource(owner, rid)
    base.set_cache_current(owner, rid, 1, 1)
    base.reserve_transition(owner, tid, rid, 1, "release-commit-race:v1", token, 100)
    base.begin_scope_exclusion(scope, tid)
    if not base.finalize_scope_exclusion(scope, tid, 1):
        raise RuntimeError("release/commit race exclusion failed")

    start = threading.Barrier(3)
    outcomes: dict[str, bool] = {}

    def commit() -> None:
        start.wait()
        outcomes["commit"] = base.commit_source(owner, tid, token, 2)

    def release() -> None:
        start.wait()
        try:
            release_scope_after_terminal(owner, tid)
            outcomes["release"] = True
        except RuntimeError:
            outcomes["release"] = False

    threads = [threading.Thread(target=commit), threading.Thread(target=release)]
    for thread in threads:
        thread.start()
    start.wait()
    for thread in threads:
        thread.join(20)
    if any(thread.is_alive() for thread in threads):
        raise RuntimeError("release/commit race did not terminate")
    if not outcomes.get("commit") or outcomes.get("release"):
        raise RuntimeError(f"scope release overtook source commit eligibility: {outcomes!r}")

    state, epoch, target, hold = base.scope_state(scope)
    if state != "excluded" or epoch != 2 or target != 2 or hold != tid:
        raise RuntimeError("source commit lost exact exclusion hold before reconciliation")
    base.set_cache_revoked(owner, rid, 2, 2, tid)
    finalize_source_reconciliation(owner, tid)
    release_scope_after_terminal(owner, tid)

    print(
        "d3_b_release_source_commit_serialization=PASS "
        "premature_release_rejected=true source_commit_retains_exact_hold=true "
        "post_commit_pre_reconciliation_stays_excluded=true"
    )


def prove_reentry_new_mutation_serialization() -> None:
    owner = "identity"
    rid = "session-reentry-race"
    scope = base.scope_key(owner, rid)
    base.insert_resource(owner, rid)
    base.set_cache_current(owner, rid, 1, 1)

    base.reserve_transition(owner, "transition-a", rid, 1, "a:v1", "writer-a", 100)
    base.begin_scope_exclusion(scope, "transition-a")
    if not base.finalize_scope_exclusion(scope, "transition-a", 1):
        raise RuntimeError("transition-a exclusion failed")
    if not base.commit_source(owner, "transition-a", "writer-a", 2):
        raise RuntimeError("transition-a source commit failed")
    base.set_cache_revoked(owner, rid, 2, 2, "transition-a")
    finalize_source_reconciliation(owner, "transition-a")

    base.reserve_transition(owner, "transition-b", rid, 2, "b:v1", "writer-b", 200)
    start = threading.Barrier(3)
    outcomes: dict[str, bool] = {}

    def readmit() -> None:
        start.wait()
        try:
            release_scope_after_terminal(owner, "transition-a")
            outcomes["readmit"] = True
        except RuntimeError:
            outcomes["readmit"] = False

    def new_exclusion() -> None:
        start.wait()
        try:
            base.begin_scope_exclusion(scope, "transition-b")
            outcomes["exclude_b"] = True
        except RuntimeError:
            outcomes["exclude_b"] = False

    threads = [threading.Thread(target=readmit), threading.Thread(target=new_exclusion)]
    for thread in threads:
        thread.start()
    start.wait()
    for thread in threads:
        thread.join(20)
    if any(thread.is_alive() for thread in threads) or not outcomes.get("readmit"):
        raise RuntimeError(f"readmission/new-mutation race failed: {outcomes!r}")
    if not outcomes.get("exclude_b"):
        base.begin_scope_exclusion(scope, "transition-b")

    state, current, target, hold = base.scope_state(scope)
    if state != "excluding" or hold != "transition-b" or target != current + 1:
        raise RuntimeError("new transition was lost across serialized readmission race")
    if base.commit_source(owner, "transition-b", "writer-b", 3):
        raise RuntimeError("new mutation committed before its own lease barrier")
    if not base.cancel_transition(owner, "transition-b", 201):
        raise RuntimeError("new transition cleanup did not cancel")
    release_scope_after_terminal(owner, "transition-b", cancelled=True)

    print(
        "d3_b_reentry_new_mutation_serialization=PASS "
        "readmission_and_new_exclusion_same_row_serialized=true no_new_source_commit_without_own_barrier=true "
        "prepared_obligation_not_lost=true cancellation_release_uses_terminal_api=true"
    )


def main() -> int:
    base.finalize_source_reconciliation = finalize_source_reconciliation
    base.release_scope_after_terminal = release_scope_after_terminal
    base.prove_lease_issue_exclusion_serialization = prove_lease_issue_exclusion_serialization
    base.prove_reentry_new_mutation_serialization = prove_reentry_new_mutation_serialization

    base.wait_cache(base.CACHE_CONTAINER, base.CACHE_CLI)
    base.setup_postgres()
    base.prove_owner_boundaries()
    base.prove_partial_write_and_single_winner()
    prove_lease_issue_exclusion_serialization()
    base.prove_cleanup_takeover_actual_concurrency()
    base.prove_fleet_barrier_and_restore()
    prove_reconciliation_readmission_requires_exact_cache_convergence()
    prove_release_cannot_overtake_source_commit()
    prove_reentry_new_mutation_serialization()
    base.prove_bulkhead()
    base.prove_cross_owner_transitions()

    print(
        "d3_b_session_cache_conformance_serialized_strict=PASS "
        "source_commit_uses_fleet_scope_barrier=true fence_to_commit_toctou_removed=true "
        "lease_issue_exclusion_serialized=true exact_cache_convergence_precedes_readmission=true "
        "release_cannot_overtake_source_commit=true readmission_new_mutation_serialized=true "
        "restore_failover_nonresurrection=true owner_bulkhead_fail_closed=true"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
