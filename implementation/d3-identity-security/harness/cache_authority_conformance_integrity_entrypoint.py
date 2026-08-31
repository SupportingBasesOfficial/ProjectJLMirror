from __future__ import annotations

import hashlib
import json
import threading
import time

import cache_authority_conformance_integrity_runner as integrity

final = integrity.final
core = integrity.core
review = integrity.review
closure = integrity.closure

_ORDER = ("identity", "membership", "authz", "platform")
_ID_FIELDS = ("session_id", "membership_id", "authz_id", "platform_id")
_GEN_FIELDS = ("session_gen", "membership_gen", "authz_gen", "platform_gen")
_ORIGINAL_FINALIZE_SCOPE_EXCLUSION = core.finalize_scope_exclusion


COMPOSED_TUPLE_ADMISSION_SCRIPT = r"""
local identity=redis.call('HMGET',KEYS[1],'state','generation','admission_epoch')
local membership=redis.call('HMGET',KEYS[2],'state','generation','admission_epoch')
local authz=redis.call('HMGET',KEYS[3],'state','generation','admission_epoch')
local platform=redis.call('HMGET',KEYS[4],'state','generation','admission_epoch')
local positive=redis.call('HMGET',KEYS[5],
  'active',
  'session_id','membership_id','authz_id','platform_id',
  'session_gen','membership_gen','authz_gen','platform_gen')
local authorities={identity,membership,authz,platform}
if positive[1]~='1' then return 'DENY' end
for i=1,4 do
  if authorities[i][1]~='current' then return 'DENY' end
  if positive[i+1]~=ARGV[i+4] then return 'DENY' end
  if authorities[i][2]~=positive[i+5] then return 'DENY' end
  if authorities[i][3]~=ARGV[i] then return 'DENY' end
end
return 'ALLOW'
"""


def _require_resources(resources: dict[str, str]) -> None:
    if set(resources) != set(_ORDER):
        raise RuntimeError("composed authority tuple must contain exactly identity/membership/authz/platform")
    for owner in _ORDER:
        if not isinstance(resources[owner], str) or not resources[owner]:
            raise RuntimeError(f"composed authority tuple has invalid {owner} resource identity")


def _tuple_canonical(resources: dict[str, str]) -> str:
    _require_resources(resources)
    return json.dumps(
        [resources[owner] for owner in _ORDER],
        ensure_ascii=False,
        separators=(",", ":"),
    )


def composed_positive_key(resources: dict[str, str]) -> str:
    # The key is collision-resistant over an unambiguous canonical tuple. The
    # positive hash also stores and revalidates all four exact resource IDs, so
    # correctness does not rely on the digest alone.
    digest = hashlib.sha256(_tuple_canonical(resources).encode("utf-8")).hexdigest()
    return f"positive:composed:v2:{digest}"


def fill_composed_positive(resources: dict[str, str], generations: dict[str, int]) -> None:
    _require_resources(resources)
    if set(generations) != set(_ORDER):
        raise RuntimeError("composed positive fill requires one generation for every authority owner")
    args: list[str] = ["HSET", composed_positive_key(resources), "active", "1"]
    for owner, field in zip(_ORDER, _ID_FIELDS):
        args.extend((field, resources[owner]))
    for owner, field in zip(_ORDER, _GEN_FIELDS):
        args.extend((field, str(generations[owner])))
    core.cache_cmd(*args)


def composed_admit(
    resources: dict[str, str],
    leases: dict[str, core.BffLease],
    tick: int,
) -> str:
    _require_resources(resources)
    if set(leases) != set(_ORDER):
        return "DENY"
    selected = [leases[owner] for owner in _ORDER]
    for owner, lease in zip(_ORDER, selected):
        if lease.scope_key != core.scope_key(owner, resources[owner]):
            return "DENY"
    if not integrity._begin_admission(selected, tick):
        return "DENY"
    try:
        return core.cache_scalar(
            "EVAL",
            COMPOSED_TUPLE_ADMISSION_SCRIPT,
            "5",
            *(core.authority_key(owner, resources[owner]) for owner in _ORDER),
            composed_positive_key(resources),
            *(str(leases[owner].epoch) for owner in _ORDER),
            *(resources[owner] for owner in _ORDER),
        )
    finally:
        review._end_admission(selected)


def _copy_positive_bytes(source_resources: dict[str, str], target_resources: dict[str, str]) -> None:
    values = core.cache_cmd("HGETALL", composed_positive_key(source_resources)).stdout.splitlines()
    if not values or len(values) % 2:
        raise RuntimeError("tuple-positive negative control could not capture source bytes")
    core.cache_cmd("HSET", composed_positive_key(target_resources), *values)


def prove_composed_multi_owner_admission() -> None:
    resources = {
        "identity": "composed-session",
        "membership": "composed-membership",
        "authz": "composed-permission",
        "platform": "composed-tenant",
    }
    leases: dict[str, core.BffLease] = {}
    for owner, resource_id in resources.items():
        core.insert_resource(owner, resource_id)
        core.set_cache_current(owner, resource_id, 1, 1)
        leases[owner] = final.issue_scope_lease(
            core.scope_key(owner, resource_id),
            f"bff-composed-{owner}",
            1,
            100,
        )

    generations = {owner: 1 for owner in _ORDER}
    fill_composed_positive(resources, generations)
    if composed_admit(resources, leases, 10) != "ALLOW":
        raise RuntimeError("healthy tuple-bound composed multi-owner admission did not authorize")

    # P1 negative: keep the exact same Identity/session and generation/epoch
    # numbers, but substitute Membership/AuthZ/tenant resources. Generation
    # equality is deliberately insufficient to authorize the alternate tuple.
    alternate = dict(resources)
    alternate.update(
        membership="composed-membership-alternate",
        authz="composed-permission-alternate",
        platform="composed-tenant-alternate",
    )
    alternate_leases = dict(leases)
    for owner in ("membership", "authz", "platform"):
        core.insert_resource(owner, alternate[owner])
        core.set_cache_current(owner, alternate[owner], 1, 1)
        alternate_leases[owner] = final.issue_scope_lease(
            core.scope_key(owner, alternate[owner]),
            f"bff-composed-alternate-{owner}",
            1,
            100,
        )

    if composed_admit(alternate, alternate_leases, 10) != "DENY":
        raise RuntimeError("same-generation alternate authority tuple reused another tuple's positive")

    # Key separation is not the only defense: even if stale/misrouted bytes are
    # copied into the alternate tuple key, their embedded resource identities
    # must fail the single-EVAL admission check.
    _copy_positive_bytes(resources, alternate)
    if composed_admit(alternate, alternate_leases, 10) != "DENY":
        raise RuntimeError("misrouted positive bytes bypassed exact tuple identity validation")

    fill_composed_positive(alternate, generations)
    if composed_admit(alternate, alternate_leases, 10) != "ALLOW":
        raise RuntimeError("exact alternate tuple did not authorize after its own positive fill")
    if composed_admit(resources, leases, 10) != "ALLOW":
        raise RuntimeError("alternate tuple fill disturbed original tuple positive authority")

    print(
        "d3_b_composed_tuple_binding=PASS "
        "canonical_complete_tuple_key=true positive_embeds_complete_resource_identity=true "
        "same_generation_alternate_tuple_denied=true misrouted_positive_denied=true "
        "exact_tuple_fill_required=true"
    )

    # Preserve the prior mixed-generation and broad-scope fence vectors.
    core.cache_cmd(
        "HSET",
        core.authority_key("authz", resources["authz"]),
        "state", "current",
        "generation", "2",
        "transition_id", "",
        "admission_epoch", "1",
    )
    if composed_admit(resources, leases, 10) != "DENY":
        raise RuntimeError("mixed Authorization generation was admitted as current")
    core.set_cache_current("authz", resources["authz"], 1, 1)

    if core.install_fence(
        "membership",
        resources["membership"],
        1,
        "transition-composed-membership",
        1,
    ) != "FENCED":
        raise RuntimeError("composed membership fence negative vector could not be installed")
    if composed_admit(resources, leases, 10) != "DENY":
        raise RuntimeError("membership fence did not affect composed protected admission")
    if core.cache_scalar("HGET", core.authority_key("identity", resources["identity"]), "state") != "current":
        raise RuntimeError("composed membership vector accidentally changed session authority")

    print(
        "d3_b_composed_multi_owner_admission=PASS single_eval_read_set=true "
        "identity_membership_authz_platform_join=true complete_authority_tuple_bound=true "
        "mixed_owner_generation_denied=true membership_fence_denies_with_session_current=true"
    )


def prove_scope_binding() -> None:
    owner = "identity"
    rid_a = "session-scope-a"
    rid_b = "session-scope-b"
    core.insert_resource(owner, rid_a)
    core.insert_resource(owner, rid_b)
    core.set_cache_current(owner, rid_a, 1, 1)
    core.set_cache_current(owner, rid_b, 1, 1)
    lease_a = integrity.issue_scope_lease(core.scope_key(owner, rid_a), "bff-scope-a", 1, 100)
    if core.raw_admit(owner, rid_b, lease_a, 10) != "ALLOW":
        raise RuntimeError("cross-scope negative control was not otherwise cache-authorizing")
    if integrity.admit(owner, rid_b, lease_a, 10) != "DENY":
        raise RuntimeError("lease for scope A authorized protected resource B")

    resources = {
        "identity": "joined-scope-session",
        "membership": "joined-scope-membership",
        "authz": "joined-scope-authz",
        "platform": "joined-scope-tenant",
    }
    leases: dict[str, core.BffLease] = {}
    for joined_owner, joined_rid in resources.items():
        core.insert_resource(joined_owner, joined_rid)
        core.set_cache_current(joined_owner, joined_rid, 1, 1)
        leases[joined_owner] = integrity.issue_scope_lease(
            core.scope_key(joined_owner, joined_rid),
            f"bff-joined-{joined_owner}",
            1,
            120,
        )
    generations = {joined_owner: 1 for joined_owner in _ORDER}
    fill_composed_positive(resources, generations)
    if composed_admit(resources, leases, 10) != "ALLOW":
        raise RuntimeError("correctly bound composed read set did not authorize")

    other_membership = "joined-scope-membership-other"
    core.insert_resource("membership", other_membership)
    core.set_cache_current("membership", other_membership, 1, 1)
    wrong_membership_lease = integrity.issue_scope_lease(
        core.scope_key("membership", other_membership),
        "bff-joined-membership-other",
        1,
        120,
    )
    misbound = dict(leases)
    misbound["membership"] = wrong_membership_lease

    # The Redis tuple itself is still otherwise current because the wrong lease
    # carries the same epoch. The local trusted-evidence scope check must be the
    # reason this forged lease substitution fails.
    raw = core.cache_scalar(
        "EVAL",
        COMPOSED_TUPLE_ADMISSION_SCRIPT,
        "5",
        *(core.authority_key(joined_owner, resources[joined_owner]) for joined_owner in _ORDER),
        composed_positive_key(resources),
        *(str(misbound[joined_owner].epoch) for joined_owner in _ORDER),
        *(resources[joined_owner] for joined_owner in _ORDER),
    )
    if raw != "ALLOW":
        raise RuntimeError("composed cross-scope negative control was not epoch/tuple-equivalent")
    if composed_admit(resources, misbound, 10) != "DENY":
        raise RuntimeError("composed admission accepted a lease from the wrong membership scope")

    print(
        "d3_b_lease_scope_binding=PASS single_scope_cross_resource_denied=true "
        "composed_each_owner_scope_bound=true epoch_equivalence_cannot_substitute_scope_identity=true"
    )


def expire_local_scope_lease(lease: core.BffLease, tick: int) -> None:
    """Publish expiry only after local invalidation and in-flight drain.

    Expiration itself is not barrier-visible proof. The BFF that owns the exact
    durable issuance must first stop new admissions and drain every admission
    that began while the lease was valid; only then may its lease_instance be
    retired durably. A missing/remote owner therefore remains conservatively
    unretired and continues to block fleet exclusion.
    """
    if tick < lease.valid_until_tick:
        raise RuntimeError("lease cannot publish expiry before its validity horizon")
    integrity.retire_scope_lease(lease)


def finalize_scope_exclusion(scope: str, transition_id: str, tick: int) -> bool:
    """Complete exclusion only after every old issuance has a durable drain ACK."""
    state, current_epoch, target_epoch, hold = core.scope_state(scope)
    if state != "excluding" or target_epoch is None or hold != transition_id:
        return False

    # In this evidence process we own several BFF replica capabilities. Expired
    # local issuances are converted to durable retirement only through the same
    # invalidation+drain path as explicit retirement. A durable issuance that is
    # not locally owned is never reaped here merely because its timestamp passed.
    local_expired = [
        lease
        for (lease_scope, _replica), lease in list(integrity._ACTIVE_LEASE_OBJECT.items())
        if lease_scope == scope
        and lease.epoch == current_epoch
        and tick >= lease.valid_until_tick
    ]
    for lease in local_expired:
        expire_local_scope_lease(lease, tick)

    unacked = int(
        core.control_scalar(
            "SELECT count(*) FROM cache_control.scope_lease "
            f"WHERE scope_key={core.q(scope)} AND epoch={current_epoch} AND retired=false;"
        )
    )
    if unacked != 0:
        return False

    # No lease can be issued while the scope row is 'excluding', so after the
    # durable zero-unacked check there is no admission-capability creator racing
    # the original serialized scope-row transition.
    return _ORIGINAL_FINALIZE_SCOPE_EXCLUSION(scope, transition_id, tick)


def prove_natural_expiry_drains_before_barrier_visible() -> None:
    owner = "identity"
    resource_id = "session-natural-expiry-drain"
    scope = core.scope_key(owner, resource_id)
    transition_id = "transition-natural-expiry-drain"
    owner_token = "writer-natural-expiry-drain"

    core.insert_resource(owner, resource_id)
    core.set_cache_current(owner, resource_id, 1, 1)
    lease = integrity.issue_scope_lease(scope, "bff-natural-expiry", 1, 10)
    core.reserve_transition(
        owner,
        transition_id,
        resource_id,
        1,
        "natural-expiry-drain:v1",
        owner_token,
        100,
    )
    core.begin_scope_exclusion(scope, transition_id)

    entered_raw = threading.Event()
    resume_raw = threading.Event()
    decision: dict[str, str] = {}
    finalize_result: dict[str, bool] = {}
    errors: list[BaseException] = []
    original_raw_admit = core.raw_admit

    def sleeping_raw_admit(
        raw_owner: str,
        raw_resource_id: str,
        raw_lease: core.BffLease,
        raw_tick: int,
        *,
        container: str | None = None,
        cli: str | None = None,
    ) -> str:
        if raw_owner == owner and raw_resource_id == resource_id and raw_lease is lease:
            entered_raw.set()
            if not resume_raw.wait(timeout=5.0):
                raise RuntimeError("sleeping admission was not released")
        return original_raw_admit(
            raw_owner,
            raw_resource_id,
            raw_lease,
            raw_tick,
            container=container,
            cli=cli,
        )

    def run_admission() -> None:
        try:
            decision["value"] = integrity.admit(owner, resource_id, lease, 9)
        except BaseException as exc:  # surfaced to the main evidence thread below
            errors.append(exc)

    def run_finalize() -> None:
        try:
            finalize_result["value"] = finalize_scope_exclusion(scope, transition_id, 11)
        except BaseException as exc:
            errors.append(exc)

    core.raw_admit = sleeping_raw_admit
    admission_thread = threading.Thread(target=run_admission, name="d3-expiry-sleeping-admission")
    finalize_thread = threading.Thread(target=run_finalize, name="d3-expiry-finalize")
    try:
        admission_thread.start()
        if not entered_raw.wait(timeout=5.0):
            raise RuntimeError("pre-expiry admission did not enter the protected read")

        # At tick 11 the lease is expired, but its pre-expiry admission is still
        # in flight. Finalization must invalidate the local capability and block
        # before publishing durable retirement or the excluded state.
        finalize_thread.start()
        time.sleep(0.2)
        if not finalize_thread.is_alive():
            raise RuntimeError("natural expiry became barrier-visible before in-flight drain")
        state, current_epoch, _target, hold = core.scope_state(scope)
        if state != "excluding" or current_epoch != 1 or hold != transition_id:
            raise RuntimeError("scope advanced while expired admission was still in flight")
        durable_retired = core.control_scalar(
            "SELECT CASE WHEN retired THEN '1' ELSE '0' END FROM cache_control.scope_lease "
            f"WHERE scope_key={core.q(scope)} AND replica_id='bff-natural-expiry';"
        )
        if durable_retired != "0":
            raise RuntimeError("expiry retirement ACK became durable before admission drain")
        if core.commit_source(owner, transition_id, owner_token, 11):
            raise RuntimeError("source revocation committed before expired admission drained")

        # The sleeping request is allowed to finish against the old source state;
        # only after it leaves the in-flight set may expiry publish its durable ACK
        # and the fleet barrier become complete.
        resume_raw.set()
        admission_thread.join(timeout=5.0)
        finalize_thread.join(timeout=5.0)
        if admission_thread.is_alive() or finalize_thread.is_alive():
            raise RuntimeError("expiry drain threads did not terminate")
        if errors:
            raise RuntimeError(f"expiry drain concurrency failed: {errors[0]}")
        if decision.get("value") != "ALLOW":
            raise RuntimeError("pre-expiry sleeping admission negative control was not genuinely authorizing")
        if finalize_result.get("value") is not True:
            raise RuntimeError("barrier did not complete after expired admission drained")
        durable_retired = core.control_scalar(
            "SELECT CASE WHEN retired THEN '1' ELSE '0' END FROM cache_control.scope_lease "
            f"WHERE scope_key={core.q(scope)} AND replica_id='bff-natural-expiry';"
        )
        if durable_retired != "1":
            raise RuntimeError("drained natural expiry did not publish durable retirement ACK")

        permit = core.acquire_commit_permit(owner, transition_id)
        if not core.commit_source(owner, transition_id, owner_token, 12, permit):
            raise RuntimeError("source revocation could not commit after expiry drain barrier")

        # A request that had captured the old start tick/cache pair would still be
        # intrinsically authorizing at the raw cache layer. The retired exact lease
        # capability must be the reason it can no longer re-enter protected admission.
        if original_raw_admit(owner, resource_id, lease, 9) != "ALLOW":
            raise RuntimeError("post-commit stale-reader negative control was not genuinely authorizing")
        if integrity.admit(owner, resource_id, lease, 9) != "DENY":
            raise RuntimeError("expired drained lease capability re-entered protected admission")

        core.reconcile_cache_and_finalize_source(owner, transition_id)
        core.release_scope_after_terminal(owner, transition_id)
    finally:
        core.raw_admit = original_raw_admit
        resume_raw.set()
        admission_thread.join(timeout=1.0)
        finalize_thread.join(timeout=1.0)

    print(
        "d3_b_natural_expiry_inflight_drain=PASS "
        "expiry_timestamp_alone_not_barrier_visible=true local_capability_invalidated_before_ack=true "
        "pre_expiry_inflight_admission_drained=true durable_retired_ack_after_drain=true "
        "source_commit_blocked_before_drain=true source_commit_allowed_after_drain=true "
        "raw_stale_reader_negative_control_allow=true retired_capability_final_admission_denied=true"
    )


def install_tuple_binding_and_expiry_drain() -> None:
    # Patch the effective final/integrity entry surface before any scenario
    # executes. All downstream wrappers then inherit the tuple-bound admission
    # and the drain-aware fleet exclusion barrier.
    final.COMPOSED_ADMISSION_SCRIPT = COMPOSED_TUPLE_ADMISSION_SCRIPT
    final.composed_positive_key = composed_positive_key
    final.fill_composed_positive = fill_composed_positive
    final.composed_admit = composed_admit
    final.prove_composed_multi_owner_admission = prove_composed_multi_owner_admission
    integrity.composed_admit = composed_admit
    integrity.prove_scope_binding = prove_scope_binding
    core.finalize_scope_exclusion = finalize_scope_exclusion


def main() -> int:
    install_tuple_binding_and_expiry_drain()
    result = integrity.main()
    if result != 0:
        return result
    prove_natural_expiry_drains_before_barrier_visible()
    print(
        "d3_b_integrity_entrypoint=PASS complete_authority_tuple_binding=true "
        "generation_only_tuple_substitution_rejected=true natural_expiry_requires_durable_drain_ack=true"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
