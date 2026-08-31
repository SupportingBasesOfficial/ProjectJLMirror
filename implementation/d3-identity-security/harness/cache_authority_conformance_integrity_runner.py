from __future__ import annotations

import secrets

import cache_authority_conformance_closure_runner as closure

review = closure.review
final = closure.final
core = closure.core

_ORIGINAL_SETUP = core.setup_postgres
_ACTIVE_LEASE_OBJECT: dict[tuple[str, str], core.BffLease] = {}
_LEASE_ISSUANCE_TOKEN: dict[int, str] = {}


def setup_postgres() -> None:
    _ORIGINAL_SETUP()
    role, password = core.CONTROL_ROLE
    core.pg_role(
        role,
        password,
        "ALTER TABLE cache_control.scope_lease ADD COLUMN IF NOT EXISTS lease_instance text;",
    )


def _durable_issue(
    scope: str,
    replica_id: str,
    epoch: int,
    valid_until_tick: int,
    new_token: str,
    predecessor_token: str | None,
) -> None:
    role, password = core.CONTROL_ROLE
    predecessor_sql = "NULL" if predecessor_token is None else core.q(predecessor_token)
    result = core.pg_role(
        role,
        password,
        f"""
DO $d3$
DECLARE
  v_state text;
  v_epoch bigint;
  v_existing_token text;
  v_retired boolean;
BEGIN
  SELECT state,current_epoch INTO v_state,v_epoch
  FROM cache_control.scope_admission
  WHERE scope_key={core.q(scope)} FOR UPDATE;
  IF NOT FOUND OR v_state <> 'admitted' OR v_epoch <> {epoch} THEN
    RAISE EXCEPTION 'requested scope epoch is not currently issuable';
  END IF;

  SELECT lease_instance,retired INTO v_existing_token,v_retired
  FROM cache_control.scope_lease
  WHERE scope_key={core.q(scope)} AND replica_id={core.q(replica_id)}
  FOR UPDATE;

  IF FOUND AND NOT v_retired THEN
    IF {predecessor_sql} IS NULL OR v_existing_token IS DISTINCT FROM {predecessor_sql} THEN
      RAISE EXCEPTION 'live replica identity is owned by another issuance/incarnation';
    END IF;
  END IF;

  INSERT INTO cache_control.scope_lease
    (scope_key,replica_id,epoch,valid_until_tick,retired,lease_instance)
  VALUES
    ({core.q(scope)},{core.q(replica_id)},{epoch},{valid_until_tick},false,{core.q(new_token)})
  ON CONFLICT (scope_key,replica_id) DO UPDATE SET
    epoch=EXCLUDED.epoch,
    valid_until_tick=EXCLUDED.valid_until_tick,
    retired=false,
    lease_instance=EXCLUDED.lease_instance;
END
$d3$;
""",
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError("lease issuance/reissue rejected by durable incarnation ownership")


def issue_scope_lease(
    scope: str,
    replica_id: str,
    epoch: int,
    valid_until_tick: int,
) -> core.BffLease:
    key = (scope, replica_id)
    closure._enter_lease_mutation(key)
    predecessor: core.BffLease | None = None
    try:
        with review._LEASE_COND:
            predecessor = _ACTIVE_LEASE_OBJECT.pop(key, None)
            if predecessor is not None:
                if final._ACTIVE_LOCAL_LEASE.get(key) == id(predecessor):
                    final._ACTIVE_LOCAL_LEASE.pop(key, None)
                review._wait_drained(id(predecessor))
            predecessor_token = (
                _LEASE_ISSUANCE_TOKEN.get(id(predecessor)) if predecessor is not None else None
            )
            if predecessor is not None and predecessor_token is None:
                raise RuntimeError("active predecessor has no durable issuance identity")

            new_token = secrets.token_hex(24)
            try:
                _durable_issue(
                    scope,
                    replica_id,
                    epoch,
                    valid_until_tick,
                    new_token,
                    predecessor_token,
                )
            except Exception:
                if predecessor is not None:
                    _ACTIVE_LEASE_OBJECT[key] = predecessor
                    final._ACTIVE_LOCAL_LEASE[key] = id(predecessor)
                raise

            lease = core.BffLease(scope, replica_id, epoch, valid_until_tick)
            _ACTIVE_LEASE_OBJECT[key] = lease
            final._ACTIVE_LOCAL_LEASE[key] = id(lease)
            _LEASE_ISSUANCE_TOKEN[id(lease)] = new_token
            core._LOCAL_RETIRED.discard(key)
            return lease
    finally:
        closure._leave_lease_mutation(key)


def retire_scope_lease(lease: core.BffLease) -> None:
    key = (lease.scope_key, lease.replica_id)
    closure._enter_lease_mutation(key)
    try:
        with review._LEASE_COND:
            active = _ACTIVE_LEASE_OBJECT.get(key)
            if active is lease:
                _ACTIVE_LEASE_OBJECT.pop(key, None)
                if final._ACTIVE_LOCAL_LEASE.get(key) == id(lease):
                    final._ACTIVE_LOCAL_LEASE.pop(key, None)
            review._wait_drained(id(lease))
            token = _LEASE_ISSUANCE_TOKEN.get(id(lease))
            if token is None:
                raise RuntimeError("retirement rejected for unissued/forged lease object")

            role, password = core.CONTROL_ROLE
            result = core.pg_role(
                role,
                password,
                f"""
UPDATE cache_control.scope_lease
SET retired=true
WHERE scope_key={core.q(lease.scope_key)}
  AND replica_id={core.q(lease.replica_id)}
  AND epoch={lease.epoch}
  AND lease_instance={core.q(token)}
RETURNING lease_instance;
""",
                check=False,
            )
            matched = core.scalar(result) == token
            if matched:
                _LEASE_ISSUANCE_TOKEN.pop(id(lease), None)
                if active is lease:
                    core._LOCAL_RETIRED.add(key)
            # A stale predecessor retirement is a safe no-op. It must never
            # change the replacement's durable row or local currentness.
    finally:
        closure._leave_lease_mutation(key)


def _begin_admission(leases: list[core.BffLease], tick: int) -> bool:
    unique: dict[int, core.BffLease] = {id(lease): lease for lease in leases}
    with review._LEASE_COND:
        for lease_id, lease in unique.items():
            if tick >= lease.valid_until_tick:
                return False
            key = (lease.scope_key, lease.replica_id)
            if _ACTIVE_LEASE_OBJECT.get(key) is not lease:
                return False
            if _LEASE_ISSUANCE_TOKEN.get(lease_id) is None:
                return False
        for lease_id in unique:
            review._INFLIGHT_BY_LEASE[lease_id] = review._INFLIGHT_BY_LEASE.get(lease_id, 0) + 1
        return True


def _local_lease_current(lease: core.BffLease, tick: int) -> bool:
    with review._LEASE_COND:
        return (
            tick < lease.valid_until_tick
            and _ACTIVE_LEASE_OBJECT.get((lease.scope_key, lease.replica_id)) is lease
            and _LEASE_ISSUANCE_TOKEN.get(id(lease)) is not None
        )


def _scope_matches(owner: str, resource_id: str, lease: core.BffLease) -> bool:
    return lease.scope_key == core.scope_key(owner, resource_id)


def admit(
    owner: str,
    resource_id: str,
    lease: core.BffLease,
    tick: int,
    *,
    container: str | None = None,
    cli: str | None = None,
) -> str:
    if not _scope_matches(owner, resource_id, lease):
        return "DENY"
    if not _begin_admission([lease], tick):
        return "DENY"
    try:
        return core.raw_admit(
            owner,
            resource_id,
            lease,
            tick,
            container=container,
            cli=cli,
        )
    finally:
        review._end_admission([lease])


def composed_admit(
    resources: dict[str, str],
    leases: dict[str, core.BffLease],
    tick: int,
) -> str:
    order = ("identity", "membership", "authz", "platform")
    selected = [leases[owner] for owner in order]
    for owner, lease in zip(order, selected):
        if not _scope_matches(owner, resources[owner], lease):
            return "DENY"
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
        review._end_admission(selected)


def degraded_owner_read_and_fill(
    owner: str,
    resource_id: str,
    lease: core.BffLease,
    bulkhead: core.OwnerReadBulkhead,
) -> str:
    if not _scope_matches(owner, resource_id, lease):
        return "DENY"
    if not _begin_admission([lease], 20):
        return "DENY"
    try:
        def read_then_fill() -> str:
            generation, active = core.resource_state(owner, resource_id)
            if not active:
                return "DENY"
            if final.fill_positive_if_current(owner, resource_id, generation, lease.epoch) != "FILLED":
                return "DENY"
            return core.raw_admit(owner, resource_id, lease, 20)

        admitted_owner, result = bulkhead.try_read(read_then_fill)
        if not admitted_owner or result != "ALLOW":
            return "DENY"
        return "ALLOW"
    finally:
        review._end_admission([lease])


def install_integrity_patches() -> None:
    review.install_patches()
    core.setup_postgres = setup_postgres
    core.issue_scope_lease = issue_scope_lease
    core.retire_scope_lease = retire_scope_lease
    core.admit = admit

    final.issue_scope_lease = issue_scope_lease
    final.retire_scope_lease = retire_scope_lease
    final._local_lease_current = _local_lease_current
    final.admit = admit
    final.composed_admit = composed_admit
    final.degraded_owner_read_and_fill = degraded_owner_read_and_fill

    review.issue_scope_lease = issue_scope_lease
    review.retire_scope_lease = retire_scope_lease
    review._begin_admission = _begin_admission
    review._local_lease_current = _local_lease_current
    review.admit = admit
    review.composed_admit = composed_admit
    review.degraded_owner_read_and_fill = degraded_owner_read_and_fill

    closure.issue_scope_lease = issue_scope_lease
    closure.retire_scope_lease = retire_scope_lease


def prove_actual_object_capability() -> None:
    owner = "identity"
    rid = "session-object-capability"
    scope = core.scope_key(owner, rid)
    core.insert_resource(owner, rid)
    core.set_cache_current(owner, rid, 1, 1)
    legitimate = issue_scope_lease(scope, "bff-object-capability", 1, 100)
    forged = core.BffLease(scope, "bff-object-capability", 1, 1000)
    if core.raw_admit(owner, rid, forged, 10) != "ALLOW":
        raise RuntimeError("forged-object negative control was not otherwise cache-authorizing")
    if admit(owner, rid, forged, 10) != "DENY":
        raise RuntimeError("caller-constructed equal-field lease bypassed issued-object identity")
    if admit(owner, rid, legitimate, 10) != "ALLOW":
        raise RuntimeError("actual issued lease object was not admitted")
    if _ACTIVE_LEASE_OBJECT.get((scope, "bff-object-capability")) is not legitimate:
        raise RuntimeError("active lease registry does not hold strong object capability")
    print(
        "d3_b_lease_object_capability=PASS "
        "active_registry_holds_actual_object=true caller_constructed_equal_fields_rejected=true "
        "object_identity_not_reusable_while_active=true"
    )


def prove_scope_binding() -> None:
    owner = "identity"
    rid_a = "session-scope-a"
    rid_b = "session-scope-b"
    core.insert_resource(owner, rid_a)
    core.insert_resource(owner, rid_b)
    core.set_cache_current(owner, rid_a, 1, 1)
    core.set_cache_current(owner, rid_b, 1, 1)
    lease_a = issue_scope_lease(core.scope_key(owner, rid_a), "bff-scope-a", 1, 100)
    if core.raw_admit(owner, rid_b, lease_a, 10) != "ALLOW":
        raise RuntimeError("cross-scope negative control was not otherwise cache-authorizing")
    if admit(owner, rid_b, lease_a, 10) != "DENY":
        raise RuntimeError("lease for scope A authorized protected resource B")

    resources = {
        "identity": "joined-scope-session",
        "membership": "joined-scope-membership",
        "authz": "joined-scope-authz",
        "platform": "joined-scope-tenant",
    }
    for joined_owner, joined_rid in resources.items():
        core.insert_resource(joined_owner, joined_rid)
        core.set_cache_current(joined_owner, joined_rid, 1, 1)
    leases = {
        joined_owner: issue_scope_lease(
            core.scope_key(joined_owner, joined_rid),
            f"bff-joined-{joined_owner}",
            1,
            120,
        )
        for joined_owner, joined_rid in resources.items()
    }
    generations = {joined_owner: 1 for joined_owner in resources}
    final.fill_composed_positive(resources, generations)
    if composed_admit(resources, leases, 10) != "ALLOW":
        raise RuntimeError("correctly bound composed read set did not authorize")

    other_membership = "joined-scope-membership-other"
    core.insert_resource("membership", other_membership)
    core.set_cache_current("membership", other_membership, 1, 1)
    wrong_membership_lease = issue_scope_lease(
        core.scope_key("membership", other_membership),
        "bff-joined-membership-other",
        1,
        120,
    )
    misbound = dict(leases)
    misbound["membership"] = wrong_membership_lease
    raw = core.cache_scalar(
        "EVAL",
        final.COMPOSED_ADMISSION_SCRIPT,
        "5",
        *(core.authority_key(joined_owner, resources[joined_owner]) for joined_owner in ("identity", "membership", "authz", "platform")),
        final.composed_positive_key(resources["identity"]),
        *(str(misbound[joined_owner].epoch) for joined_owner in ("identity", "membership", "authz", "platform")),
    )
    if raw != "ALLOW":
        raise RuntimeError("composed cross-scope negative control was not epoch-equivalent")
    if composed_admit(resources, misbound, 10) != "DENY":
        raise RuntimeError("composed admission accepted a lease from the wrong membership scope")

    print(
        "d3_b_lease_scope_binding=PASS "
        "single_scope_cross_resource_denied=true composed_each_owner_scope_bound=true "
        "epoch_equivalence_cannot_substitute_scope_identity=true"
    )


def prove_stale_retirement_cannot_clobber_replacement() -> None:
    owner = "identity"
    rid = "session-stale-retirement-token"
    scope = core.scope_key(owner, rid)
    replica = "bff-stale-retirement-token"
    core.insert_resource(owner, rid)
    core.set_cache_current(owner, rid, 1, 1)
    old = issue_scope_lease(scope, replica, 1, 50)
    old_token = _LEASE_ISSUANCE_TOKEN[id(old)]
    replacement = issue_scope_lease(scope, replica, 1, 120)
    replacement_token = _LEASE_ISSUANCE_TOKEN[id(replacement)]
    if old_token == replacement_token:
        raise RuntimeError("same-replica reissue did not rotate durable issuance identity")

    retire_scope_lease(old)
    durable = core.control_scalar(
        f"SELECT lease_instance||'|'||valid_until_tick||'|'||CASE WHEN retired THEN '1' ELSE '0' END "
        f"FROM cache_control.scope_lease WHERE scope_key={core.q(scope)} AND replica_id={core.q(replica)};"
    )
    if durable != f"{replacement_token}|120|0":
        raise RuntimeError(f"stale retirement clobbered replacement durable row: {durable!r}")
    if admit(owner, rid, replacement, 20) != "ALLOW":
        raise RuntimeError("replacement lease lost currentness after stale retirement no-op")
    if admit(owner, rid, old, 20) != "DENY":
        raise RuntimeError("predecessor revived after replacement")

    retire_scope_lease(replacement)
    retired = core.control_scalar(
        f"SELECT CASE WHEN retired THEN '1' ELSE '0' END FROM cache_control.scope_lease "
        f"WHERE scope_key={core.q(scope)} AND replica_id={core.q(replica)} AND lease_instance={core.q(replacement_token)};"
    )
    if retired != "1":
        raise RuntimeError("current issuance could not retire its own durable lease row")

    print(
        "d3_b_durable_lease_issuance_identity=PASS "
        "issuance_token_rotates_on_reissue=true stale_retirement_token_noop=true "
        "replacement_row_not_clobbered=true current_issuance_can_retire=true"
    )


def prove_unowned_replica_id_reuse_rejected() -> None:
    owner = "identity"
    rid = "session-incarnation-reuse"
    scope = core.scope_key(owner, rid)
    replica = "bff-incarnation-reuse"
    core.insert_resource(owner, rid)
    core.set_cache_current(owner, rid, 1, 1)
    old = issue_scope_lease(scope, replica, 1, 200)

    # Model a new process incarnation that does not possess the predecessor
    # capability while the durable lease is still live/unretired.
    with review._LEASE_COND:
        _ACTIVE_LEASE_OBJECT.pop((scope, replica), None)
        final._ACTIVE_LOCAL_LEASE.pop((scope, replica), None)
    try:
        issue_scope_lease(scope, replica, 1, 300)
    except RuntimeError:
        pass
    else:
        raise RuntimeError("independent incarnation reused a live replica identity without predecessor ownership")

    # Restore the predecessor capability only to retire the modeled old incarnation.
    with review._LEASE_COND:
        _ACTIVE_LEASE_OBJECT[(scope, replica)] = old
        final._ACTIVE_LOCAL_LEASE[(scope, replica)] = id(old)
    retire_scope_lease(old)
    fresh = issue_scope_lease(scope, replica, 1, 300)
    if admit(owner, rid, fresh, 20) != "ALLOW":
        raise RuntimeError("replica identity could not be reused after exact predecessor retirement")

    print(
        "d3_b_replica_incarnation_ownership=PASS "
        "live_replica_id_not_stealable=true predecessor_capability_required_for_live_reissue=true "
        "independent_incarnation_must_use_new_or_retired_replica_identity=true"
    )


def main() -> int:
    install_integrity_patches()

    if final.main() != 0:
        raise RuntimeError("prior final D3-B conformance failed under integrity patches")
    review.prove_forged_commit_permit_rejected()
    review.prove_retirement_drains_inflight_admissions()
    review.prove_same_replica_reissue_waits_for_inflight()
    review.prove_current_epoch_stale_restore_cannot_resurrect()
    closure.prove_retire_reissue_same_replica_serialization()

    prove_actual_object_capability()
    prove_scope_binding()
    prove_stale_retirement_cannot_clobber_replacement()
    prove_unowned_replica_id_reuse_rejected()

    print(
        "d3_b_session_cache_conformance_integrity=PASS "
        "actual_lease_object_capability=true scope_binding=true durable_issuance_identity=true "
        "stale_retirement_noop=true incarnation_ownership=true"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
