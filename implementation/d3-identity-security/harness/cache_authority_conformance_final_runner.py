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
    """Issue trusted local expected-admission evidence with one exact latch identity."""
    lease = _ORIGINAL_ISSUE(scope, replica_id, epoch, valid_until_tick)
    _ACTIVE_LOCAL_LEASE[(scope, replica_id)] = id(lease)
    return lease


def retire_scope_lease(lease: core.BffLease) -> None:
    _ORIGINAL_RETIRE(lease)
    key = (lease.scope_key, lease.replica_id)
    if _ACTIVE_LOCAL_LEASE.get(key) == id(lease):
        del _ACTIVE_LOCAL_LEASE[key]


def _local_lease_current(lease: core.BffLease, tick: int) -> bool:
    return (
        tick < lease.valid_until_tick
        and _ACTIVE_LOCAL_LEASE.get((lease.scope_key, lease.replica_id)) == id(lease)
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
    # No durable lookup is added to the healthy request path: this is local
    # expected-evidence identity. A replacement lease for the same replica changes
    # the latch and therefore cannot revive the predecessor capability.
    if not _local_lease_current(lease, tick):
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


COMPOSED_ADMISSION_SCRIPT = r"""
local identity=redis.call('HMGET',KEYS[1],'state','generation','admission_epoch')
local membership=redis.call('HMGET',KEYS[2],'state','generation','admission_epoch')
local authz=redis.call('HMGET',KEYS[3],'state','generation','admission_epoch')
local platform=redis.call('HMGET',KEYS[4],'state','generation','admission_epoch')
local positive=redis.call('HMGET',KEYS[5],'session_gen','membership_gen','authz_gen','platform_gen')
local authorities={identity,membership,authz,platform}
for i=1,4 do
  if authorities[i][1]~='current' then return 'DENY' end
  if authorities[i][2]~=positive[i] then return 'DENY' end
  if authorities[i][3]~=ARGV[i] then return 'DENY' end
end
return 'ALLOW'
"""


FILL_POSITIVE_SCRIPT = r"""
local authority=redis.call('HMGET',KEYS[1],'state','generation','admission_epoch')
if authority[1]~='current' then return 'DENY' end
if authority[2]~=ARGV[1] then return 'DENY' end
if authority[3]~=ARGV[2] then return 'DENY' end
redis.call('HSET',KEYS[2],'active','1','owner_generation',ARGV[1],'admission_epoch',ARGV[2])
return 'FILLED'
"""


def composed_positive_key(resource_id: str) -> str:
    return f"positive:composed:{resource_id}"


def composed_admit(
    resources: dict[str, str],
    leases: dict[str, core.BffLease],
    tick: int,
) -> str:
    order = ("identity", "membership", "authz", "platform")
    for owner in order:
        if not _local_lease_current(leases[owner], tick):
            return "DENY"
    return core.cache_scalar(
        "EVAL",
        COMPOSED_ADMISSION_SCRIPT,
        "5",
        *(core.authority_key(owner, resources[owner]) for owner in order),
        composed_positive_key(resources["identity"]),
        *(str(leases[owner].epoch) for owner in order),
    )


def fill_positive_if_current(owner: str, resource_id: str, generation: int, epoch: int) -> str:
    return core.cache_scalar(
        "EVAL",
        FILL_POSITIVE_SCRIPT,
        "2",
        core.authority_key(owner, resource_id),
        core.positive_key(owner, resource_id),
        str(generation),
        str(epoch),
    )


def degraded_owner_read_and_fill(
    owner: str,
    resource_id: str,
    lease: core.BffLease,
    bulkhead: core.OwnerReadBulkhead,
) -> str:
    if not _local_lease_current(lease, 20):
        return "DENY"

    def read_then_fill() -> str:
        generation, active = core.resource_state(owner, resource_id)
        if not active:
            return "DENY"
        if fill_positive_if_current(owner, resource_id, generation, lease.epoch) != "FILLED":
            return "DENY"
        return admit(owner, resource_id, lease, 20)

    admitted, result = bulkhead.try_read(read_then_fill)
    if not admitted or result != "ALLOW":
        return "DENY"
    return "ALLOW"


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

    # Explicit retirement allows the barrier to finish before the old lease's
    # natural horizon, so the ACK must also permanently retire the local predecessor.
    retire_scope_lease(old)
    if not core.finalize_scope_exclusion(scope, "transition-lease-reissue", 10):
        raise RuntimeError("retired old lease did not permit the bounded barrier to finish")
    if not core.cancel_transition(owner, "transition-lease-reissue", 10):
        raise RuntimeError("lease-reissue transition did not reach cancelled terminal state")

    state, current_epoch, _target, hold = core.scope_state(scope)
    if state != "excluded" or current_epoch != 2 or hold != "transition-lease-reissue":
        raise RuntimeError("lease-reissue barrier lost its exact excluded hold")

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
        raise RuntimeError("lease identity negative control unexpectedly reused predecessor object")

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
        leases[owner] = issue_scope_lease(
            core.scope_key(owner, resource_id),
            f"bff-composed-{owner}",
            1,
            100,
        )

    core.cache_cmd(
        "HSET",
        composed_positive_key(resources["identity"]),
        "session_gen", "1",
        "membership_gen", "1",
        "authz_gen", "1",
        "platform_gen", "1",
    )
    if composed_admit(resources, leases, 10) != "ALLOW":
        raise RuntimeError("healthy composed multi-owner admission did not authorize")

    # Stale mixed-owner generation must be visible in the same EVAL/read set.
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

    # Membership revocation must deny the protected request even though the session
    # authority itself remains unchanged/current.
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
        "d3_b_composed_multi_owner_admission=PASS single_eval_read_set=true identity_membership_authz_platform_join=true "
        "mixed_owner_generation_denied=true membership_fence_denies_with_session_current=true"
    )


def prove_stale_fill_cannot_overwrite_fence() -> None:
    owner = "identity"
    resource_id = "session-fill-cas"
    scope = core.scope_key(owner, resource_id)
    core.insert_resource(owner, resource_id)
    core.set_cache_current(owner, resource_id, 1, 1)
    lease = issue_scope_lease(scope, "bff-fill-cas", 1, 100)
    core.cache_cmd("DEL", core.positive_key(owner, resource_id))

    if fill_positive_if_current(owner, resource_id, 1, 1) != "FILLED":
        raise RuntimeError("healthy positive fill CAS did not fill current authority")
    if admit(owner, resource_id, lease, 10) != "ALLOW":
        raise RuntimeError("healthy CAS-filled positive record did not authorize")
    core.cache_cmd("DEL", core.positive_key(owner, resource_id))

    # The fill intent is stale by the time it executes: the revocation fence wins.
    if core.install_fence(owner, resource_id, 1, "transition-fill-cas", 1) != "FENCED":
        raise RuntimeError("fill-CAS revocation fence was not installed")
    if fill_positive_if_current(owner, resource_id, 1, 1) != "DENY":
        raise RuntimeError("stale positive fill executed through an installed fence")
    authority = core.cache_scalar(
        "EVAL",
        r"""
local v=redis.call('HMGET',KEYS[1],'state','generation','transition_id','admission_epoch')
return table.concat(v,'|')
""",
        "1",
        core.authority_key(owner, resource_id),
    )
    if authority != "fence|1|transition-fill-cas|1":
        raise RuntimeError(f"stale fill mutated exact fence state: {authority!r}")
    if core.cache_scalar("EXISTS", core.positive_key(owner, resource_id)) != "0":
        raise RuntimeError("stale fill wrote positive bytes after fence")

    print(
        "d3_b_stale_fill_fence_cas=PASS atomic_authority_check_and_positive_write=true "
        "stale_fill_denied=true fence_not_overwritten=true positive_not_written_after_fence=true"
    )


def prove_owner_read_and_fill_fails_before_positive_write() -> None:
    owner = "identity"
    resource_id = "session-owner-read-fill"
    scope = core.scope_key(owner, resource_id)
    core.insert_resource(owner, resource_id)
    core.set_cache_current(owner, resource_id, 1, 1)
    core.cache_cmd("DEL", core.positive_key(owner, resource_id))
    lease = issue_scope_lease(scope, "bff-owner-read-fill", 1, 100)
    bulkhead = core.OwnerReadBulkhead(2)

    if degraded_owner_read_and_fill(owner, resource_id, lease, bulkhead) != "ALLOW":
        raise RuntimeError("healthy owner read-and-fill path did not authorize")
    if core.cache_scalar("EXISTS", core.positive_key(owner, resource_id)) != "1":
        raise RuntimeError("healthy owner read-and-fill path did not produce positive record")
    core.cache_cmd("DEL", core.positive_key(owner, resource_id))

    core.run(["docker", "pause", core.PG_CONTAINER])
    try:
        if degraded_owner_read_and_fill(owner, resource_id, lease, bulkhead) != "DENY":
            raise RuntimeError("paused owner read-and-fill path did not fail closed")
        if core.cache_scalar("EXISTS", core.positive_key(owner, resource_id)) != "0":
            raise RuntimeError("owner-read failure wrote positive cache state")
    finally:
        core.run(["docker", "unpause", core.PG_CONTAINER])

    print(
        "d3_b_owner_read_fill_fail_closed=PASS healthy_owner_read_then_fill=true actual_owner_outage_denied=true "
        "failed_owner_read_precedes_fill=true error_path_positive_absent=true"
    )


def main() -> int:
    if core.main() != 0:
        raise RuntimeError("core D3-B conformance gate failed")
    prove_same_replica_reissue_cannot_revive_retired_lease()
    prove_composed_multi_owner_admission()
    prove_stale_fill_cannot_overwrite_fence()
    prove_owner_read_and_fill_fails_before_positive_write()
    print(
        "d3_b_session_cache_conformance_final=PASS "
        "monotonic_scope_commit_permit=true redis_fence_not_commit_eligibility=true "
        "lease_latch_identity_rotates=true old_lease_cannot_revive_after_same_replica_reissue=true "
        "composed_multi_owner_single_eval=true stale_fill_cas_preserves_fence=true "
        "owner_read_failure_cannot_fill_positive=true reconciliation_exact_non_authority=true "
        "restore_failover_nonresurrection=true"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
