from __future__ import annotations

import hashlib
import json

import cache_authority_conformance_integrity_runner as integrity

final = integrity.final
core = integrity.core
review = integrity.review

_ORDER = ("identity", "membership", "authz", "platform")
_ID_FIELDS = ("session_id", "membership_id", "authz_id", "platform_id")
_GEN_FIELDS = ("session_gen", "membership_gen", "authz_gen", "platform_gen")


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


def install_tuple_binding() -> None:
    # Patch the effective final/integrity entry surface before any scenario
    # executes. All downstream wrappers then inherit the tuple-bound script,
    # key, fill and admission functions.
    final.COMPOSED_ADMISSION_SCRIPT = COMPOSED_TUPLE_ADMISSION_SCRIPT
    final.composed_positive_key = composed_positive_key
    final.fill_composed_positive = fill_composed_positive
    final.composed_admit = composed_admit
    final.prove_composed_multi_owner_admission = prove_composed_multi_owner_admission
    integrity.composed_admit = composed_admit
    integrity.prove_scope_binding = prove_scope_binding


def main() -> int:
    install_tuple_binding()
    result = integrity.main()
    if result != 0:
        return result
    print(
        "d3_b_integrity_entrypoint=PASS complete_authority_tuple_binding=true "
        "generation_only_tuple_substitution_rejected=true"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
