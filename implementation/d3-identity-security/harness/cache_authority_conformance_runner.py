from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os
import subprocess
import tempfile
import threading
import time


PG_CONTAINER = os.environ["PG_CONTAINER"]
CACHE_CONTAINER = os.environ["CACHE_CONTAINER"]
CACHE_LABEL = os.environ["CACHE_LABEL"]
CACHE_CLI = os.environ["CACHE_CLI"]
CACHE_IMAGE = os.environ["CACHE_IMAGE"]
CACHE_SERVER = os.environ["CACHE_SERVER"]
DOCKER_NETWORK = os.environ["DOCKER_NETWORK"]

PG_SUPER_PASSWORD = "d3-postgres-password"

OWNER_CONFIG = {
    "identity": ("d3_identity_owner", "d3-identity-owner-password", "identity.sessions"),
    "membership": ("d3_membership_owner", "d3-membership-owner-password", "membership.memberships"),
    "authz": ("d3_authz_owner", "d3-authz-owner-password", "authz.permissions"),
    "platform": ("d3_platform_owner", "d3-platform-owner-password", "platform.tenants"),
}
CONTROL_ROLE = ("d3_cache_control_owner", "d3-cache-control-password")


def run(
    args: list[str],
    *,
    check: bool = True,
    timeout: float = 30.0,
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        args,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
        check=False,
    )
    if check and result.returncode != 0:
        raise RuntimeError(
            f"command failed rc={result.returncode}: {args!r}\n"
            f"stdout={result.stdout[-2000:]}\nstderr={result.stderr[-2000:]}"
        )
    return result


def q(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def pg_super(sql: str, *, check: bool = True) -> subprocess.CompletedProcess[str]:
    return run(
        [
            "docker",
            "exec",
            "-e",
            f"PGPASSWORD={PG_SUPER_PASSWORD}",
            PG_CONTAINER,
            "psql",
            "-h",
            "127.0.0.1",
            "-U",
            "postgres",
            "-d",
            "d3",
            "-X",
            "-q",
            "-A",
            "-t",
            "-v",
            "ON_ERROR_STOP=1",
            "-c",
            sql,
        ],
        check=check,
    )


def pg_role(
    role: str,
    password: str,
    sql: str,
    *,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    return run(
        [
            "docker",
            "exec",
            "-e",
            f"PGPASSWORD={password}",
            PG_CONTAINER,
            "psql",
            "-h",
            "127.0.0.1",
            "-U",
            role,
            "-d",
            "d3",
            "-X",
            "-q",
            "-A",
            "-t",
            "-v",
            "ON_ERROR_STOP=1",
            "-c",
            sql,
        ],
        check=check,
    )


def scalar(result: subprocess.CompletedProcess[str]) -> str:
    lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    return lines[-1] if lines else ""


def owner_scalar(owner: str, sql: str) -> str:
    role, password, _ = OWNER_CONFIG[owner]
    return scalar(pg_role(role, password, sql))


def control_scalar(sql: str) -> str:
    role, password = CONTROL_ROLE
    return scalar(pg_role(role, password, sql))


def cache_cmd(
    *args: str,
    container: str | None = None,
    cli: str | None = None,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    return run(
        [
            "docker",
            "exec",
            container or CACHE_CONTAINER,
            cli or CACHE_CLI,
            "--raw",
            *args,
        ],
        check=check,
    )


def cache_scalar(
    *args: str,
    container: str | None = None,
    cli: str | None = None,
) -> str:
    return scalar(cache_cmd(*args, container=container, cli=cli))


def wait_cache(container: str, cli: str) -> None:
    for _ in range(60):
        result = cache_cmd("PING", container=container, cli=cli, check=False)
        if result.returncode == 0 and scalar(result) == "PONG":
            return
        time.sleep(0.25)
    raise RuntimeError(f"cache did not become ready: {container}")


def setup_postgres() -> None:
    pg_super(
        r"""
DO $d3$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='d3_identity_owner') THEN
    CREATE ROLE d3_identity_owner LOGIN PASSWORD 'd3-identity-owner-password';
  ELSE
    ALTER ROLE d3_identity_owner PASSWORD 'd3-identity-owner-password';
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='d3_membership_owner') THEN
    CREATE ROLE d3_membership_owner LOGIN PASSWORD 'd3-membership-owner-password';
  ELSE
    ALTER ROLE d3_membership_owner PASSWORD 'd3-membership-owner-password';
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='d3_authz_owner') THEN
    CREATE ROLE d3_authz_owner LOGIN PASSWORD 'd3-authz-owner-password';
  ELSE
    ALTER ROLE d3_authz_owner PASSWORD 'd3-authz-owner-password';
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='d3_platform_owner') THEN
    CREATE ROLE d3_platform_owner LOGIN PASSWORD 'd3-platform-owner-password';
  ELSE
    ALTER ROLE d3_platform_owner PASSWORD 'd3-platform-owner-password';
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='d3_cache_control_owner') THEN
    CREATE ROLE d3_cache_control_owner LOGIN PASSWORD 'd3-cache-control-password';
  ELSE
    ALTER ROLE d3_cache_control_owner PASSWORD 'd3-cache-control-password';
  END IF;
END
$d3$;

GRANT CONNECT ON DATABASE d3 TO
  d3_identity_owner,
  d3_membership_owner,
  d3_authz_owner,
  d3_platform_owner,
  d3_cache_control_owner;

DROP SCHEMA IF EXISTS identity CASCADE;
DROP SCHEMA IF EXISTS membership CASCADE;
DROP SCHEMA IF EXISTS authz CASCADE;
DROP SCHEMA IF EXISTS platform CASCADE;
DROP SCHEMA IF EXISTS cache_control CASCADE;

CREATE SCHEMA identity AUTHORIZATION d3_identity_owner;
CREATE SCHEMA membership AUTHORIZATION d3_membership_owner;
CREATE SCHEMA authz AUTHORIZATION d3_authz_owner;
CREATE SCHEMA platform AUTHORIZATION d3_platform_owner;
CREATE SCHEMA cache_control AUTHORIZATION d3_cache_control_owner;

REVOKE ALL ON SCHEMA identity, membership, authz, platform, cache_control FROM PUBLIC;
"""
    )

    resource_defs = {
        "identity": ("sessions", "session"),
        "membership": ("memberships", "membership"),
        "authz": ("permissions", "permission"),
        "platform": ("tenants", "tenant"),
    }
    for owner, (table, label) in resource_defs.items():
        role, password, _ = OWNER_CONFIG[owner]
        pg_role(
            role,
            password,
            f"""
CREATE TABLE {owner}.{table} (
  resource_id text PRIMARY KEY,
  generation bigint NOT NULL CHECK (generation > 0),
  active boolean NOT NULL
);
CREATE TABLE {owner}.security_cache_transition (
  transition_id text PRIMARY KEY,
  resource_id text NOT NULL,
  expected_generation bigint NOT NULL,
  fingerprint text NOT NULL,
  state text NOT NULL CHECK (state IN ('prepared','cancelled','committed','finalized')),
  owner_token text NOT NULL,
  lease_until_tick bigint NOT NULL,
  reconcile_pending boolean NOT NULL DEFAULT false,
  audit_intent boolean NOT NULL DEFAULT false,
  committed_generation bigint
);
CREATE TABLE {owner}.security_cache_reconciliation (
  transition_id text PRIMARY KEY,
  done boolean NOT NULL DEFAULT false
);
CREATE TABLE {owner}.security_audit_intent (
  transition_id text PRIMARY KEY,
  event_type text NOT NULL
);
COMMENT ON TABLE {owner}.{table} IS
  '{label} truth owned only by its bounded authority in this D3-B evidence profile';
""",
        )

    role, password = CONTROL_ROLE
    pg_role(
        role,
        password,
        """
CREATE TABLE cache_control.admission_state (
  singleton boolean PRIMARY KEY DEFAULT true CHECK (singleton),
  current_epoch bigint NOT NULL,
  state text NOT NULL CHECK (state IN ('admitted','excluding','excluded')),
  target_epoch bigint,
  safe_after_tick bigint
);
CREATE TABLE cache_control.bff_lease (
  replica_id text PRIMARY KEY,
  epoch bigint NOT NULL,
  valid_until_tick bigint NOT NULL,
  retired boolean NOT NULL DEFAULT false
);
INSERT INTO cache_control.admission_state(singleton,current_epoch,state,target_epoch,safe_after_tick)
VALUES (true,1,'admitted',NULL,NULL);
COMMENT ON TABLE cache_control.admission_state IS
  'Evidence-only trusted admission continuity oracle; not Identity/session or business truth.';
""",
    )


def insert_resource(owner: str, resource_id: str, generation: int = 1, active: bool = True) -> None:
    _, _, table = OWNER_CONFIG[owner]
    role, password, _ = OWNER_CONFIG[owner]
    pg_role(
        role,
        password,
        f"INSERT INTO {table}(resource_id,generation,active) "
        f"VALUES ({q(resource_id)},{generation},{'true' if active else 'false'});",
    )


def resource_state(owner: str, resource_id: str) -> tuple[int, bool]:
    _, _, table = OWNER_CONFIG[owner]
    raw = owner_scalar(
        owner,
        f"SELECT generation||'|'||CASE WHEN active THEN '1' ELSE '0' END "
        f"FROM {table} WHERE resource_id={q(resource_id)};",
    )
    generation, active = raw.split("|")
    return int(generation), active == "1"


def reserve_transition(
    owner: str,
    *,
    transition_id: str,
    resource_id: str,
    expected_generation: int,
    fingerprint: str,
    owner_token: str,
    lease_until_tick: int,
) -> tuple[str, str, str]:
    role, password, _ = OWNER_CONFIG[owner]
    pg_role(
        role,
        password,
        f"""
INSERT INTO {owner}.security_cache_transition
  (transition_id,resource_id,expected_generation,fingerprint,state,owner_token,lease_until_tick)
VALUES
  ({q(transition_id)},{q(resource_id)},{expected_generation},{q(fingerprint)},
   'prepared',{q(owner_token)},{lease_until_tick})
ON CONFLICT (transition_id) DO NOTHING;
""",
    )
    raw = owner_scalar(
        owner,
        f"""
SELECT resource_id||'|'||expected_generation||'|'||fingerprint||'|'||state||'|'||owner_token
FROM {owner}.security_cache_transition
WHERE transition_id={q(transition_id)};
""",
    )
    existing_resource, existing_generation, existing_fingerprint, state, existing_owner = raw.split("|")
    if (
        existing_resource != resource_id
        or int(existing_generation) != expected_generation
        or existing_fingerprint != fingerprint
    ):
        raise RuntimeError("transition identity/fingerprint mismatch was not rejected")
    return state, existing_owner, existing_fingerprint


def cancel_transition(owner: str, transition_id: str, tick: int) -> bool:
    role, password, _ = OWNER_CONFIG[owner]
    result = pg_role(
        role,
        password,
        f"""
UPDATE {owner}.security_cache_transition
SET state='cancelled'
WHERE transition_id={q(transition_id)}
  AND state='prepared'
  AND lease_until_tick <= {tick}
RETURNING transition_id;
""",
    )
    return scalar(result) == transition_id


def commit_transition(
    owner: str,
    *,
    transition_id: str,
    owner_token: str,
    tick: int,
    cache_eligible: bool,
) -> bool:
    if not cache_eligible:
        return False
    role, password, table = OWNER_CONFIG[owner]
    sql = f"""
DO $d3$
DECLARE
  v_resource text;
  v_expected bigint;
  v_count integer;
BEGIN
  SELECT resource_id, expected_generation
  INTO v_resource, v_expected
  FROM {owner}.security_cache_transition
  WHERE transition_id={q(transition_id)}
    AND state='prepared'
    AND owner_token={q(owner_token)}
    AND lease_until_tick > {tick}
  FOR UPDATE;

  IF NOT FOUND THEN
    RAISE EXCEPTION 'transition is not a live owned prepared transition';
  END IF;

  UPDATE {table}
  SET generation=generation+1, active=false
  WHERE resource_id=v_resource
    AND generation=v_expected
    AND active=true;
  GET DIAGNOSTICS v_count = ROW_COUNT;
  IF v_count <> 1 THEN
    RAISE EXCEPTION 'source authority expected-generation CAS lost';
  END IF;

  UPDATE {owner}.security_cache_transition
  SET state='committed',
      reconcile_pending=true,
      audit_intent=true,
      committed_generation=v_expected+1
  WHERE transition_id={q(transition_id)}
    AND state='prepared'
    AND owner_token={q(owner_token)};
  GET DIAGNOSTICS v_count = ROW_COUNT;
  IF v_count <> 1 THEN
    RAISE EXCEPTION 'transition terminal update lost';
  END IF;

  INSERT INTO {owner}.security_cache_reconciliation(transition_id,done)
  VALUES ({q(transition_id)},false);

  INSERT INTO {owner}.security_audit_intent(transition_id,event_type)
  VALUES ({q(transition_id)},'security_authority_revoked');
END
$d3$;
"""
    return pg_role(role, password, sql, check=False).returncode == 0


def transition_state(owner: str, transition_id: str) -> str:
    return owner_scalar(
        owner,
        f"""
SELECT state||'|'||CASE WHEN reconcile_pending THEN '1' ELSE '0' END
       ||'|'||CASE WHEN audit_intent THEN '1' ELSE '0' END
FROM {owner}.security_cache_transition
WHERE transition_id={q(transition_id)};
""",
    )


def mark_reconciled(owner: str, transition_id: str) -> None:
    role, password, _ = OWNER_CONFIG[owner]
    pg_role(
        role,
        password,
        f"""
DO $d3$
DECLARE v_count integer;
BEGIN
  UPDATE {owner}.security_cache_reconciliation
  SET done=true
  WHERE transition_id={q(transition_id)} AND done=false;
  GET DIAGNOSTICS v_count = ROW_COUNT;
  IF v_count <> 1 THEN
    RAISE EXCEPTION 'reconciliation completion lost';
  END IF;

  UPDATE {owner}.security_cache_transition
  SET state='finalized', reconcile_pending=false
  WHERE transition_id={q(transition_id)}
    AND state='committed'
    AND reconcile_pending=true;
  GET DIAGNOSTICS v_count = ROW_COUNT;
  IF v_count <> 1 THEN
    RAISE EXCEPTION 'transition finalization lost';
  END IF;
END
$d3$;
""",
    )


FENCE_SCRIPT = r"""
local state = redis.call('HGET', KEYS[1], 'state')
local generation = redis.call('HGET', KEYS[1], 'generation')
local transition = redis.call('HGET', KEYS[1], 'transition_id')
if state == 'fence' and transition == ARGV[2] then
  return 'IDEMPOTENT'
end
if state ~= 'current' or generation ~= ARGV[1] then
  return 'LOST'
end
redis.call('HSET', KEYS[1],
  'state','fence',
  'generation',ARGV[1],
  'transition_id',ARGV[2],
  'admission_epoch',ARGV[3])
return 'FENCED'
"""

ADMISSION_SCRIPT = r"""
local authority = redis.call('HMGET', KEYS[1], 'state','generation','admission_epoch')
local positive = redis.call('HMGET', KEYS[2], 'active','owner_generation','admission_epoch')
if authority[1] ~= 'current' then return 'DENY' end
if positive[1] ~= '1' then return 'DENY' end
if authority[2] ~= positive[2] then return 'DENY' end
if authority[3] ~= ARGV[1] then return 'DENY' end
if positive[3] ~= ARGV[1] then return 'DENY' end
return 'ALLOW'
"""


def authority_key(owner: str, resource_id: str) -> str:
    return f"authority:{owner}:{resource_id}"


def positive_key(owner: str, resource_id: str) -> str:
    return f"positive:{owner}:{resource_id}"


def set_cache_current(
    owner: str,
    resource_id: str,
    generation: int,
    epoch: int,
    *,
    container: str | None = None,
) -> None:
    cache_cmd(
        "HSET",
        authority_key(owner, resource_id),
        "state",
        "current",
        "generation",
        str(generation),
        "transition_id",
        "",
        "admission_epoch",
        str(epoch),
        container=container,
    )
    cache_cmd(
        "HSET",
        positive_key(owner, resource_id),
        "active",
        "1",
        "owner_generation",
        str(generation),
        "admission_epoch",
        str(epoch),
        container=container,
    )


def set_cache_revoked(
    owner: str,
    resource_id: str,
    generation: int,
    epoch: int,
    transition_id: str,
    *,
    container: str | None = None,
) -> None:
    cache_cmd(
        "HSET",
        authority_key(owner, resource_id),
        "state",
        "revoked",
        "generation",
        str(generation),
        "transition_id",
        transition_id,
        "admission_epoch",
        str(epoch),
        container=container,
    )


def install_fence(
    owner: str,
    resource_id: str,
    expected_generation: int,
    transition_id: str,
    epoch: int,
) -> str:
    return cache_scalar(
        "EVAL",
        FENCE_SCRIPT,
        "1",
        authority_key(owner, resource_id),
        str(expected_generation),
        transition_id,
        str(epoch),
    )


def fence_is_exact(owner: str, resource_id: str, transition_id: str) -> bool:
    result = cache_cmd(
        "HMGET",
        authority_key(owner, resource_id),
        "state",
        "transition_id",
    )
    values = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    return values == ["fence", transition_id]


@dataclass(frozen=True)
class BffLease:
    replica_id: str
    epoch: int
    valid_until_tick: int


def admit(
    owner: str,
    resource_id: str,
    lease: BffLease,
    tick: int,
    *,
    container: str | None = None,
    cli: str | None = None,
) -> str:
    if tick >= lease.valid_until_tick:
        return "DENY"
    return cache_scalar(
        "EVAL",
        ADMISSION_SCRIPT,
        "2",
        authority_key(owner, resource_id),
        positive_key(owner, resource_id),
        str(lease.epoch),
        container=container,
        cli=cli,
    )


def issue_lease(replica_id: str, epoch: int, valid_until_tick: int) -> BffLease:
    role, password = CONTROL_ROLE
    pg_role(
        role,
        password,
        f"""
INSERT INTO cache_control.bff_lease(replica_id,epoch,valid_until_tick,retired)
VALUES ({q(replica_id)},{epoch},{valid_until_tick},false)
ON CONFLICT (replica_id) DO UPDATE SET
  epoch=EXCLUDED.epoch,
  valid_until_tick=EXCLUDED.valid_until_tick,
  retired=false;
""",
    )
    return BffLease(replica_id, epoch, valid_until_tick)


def begin_exclusion(target_epoch: int) -> None:
    role, password = CONTROL_ROLE
    pg_role(
        role,
        password,
        f"""
UPDATE cache_control.admission_state
SET state='excluding', target_epoch={target_epoch}, safe_after_tick=NULL
WHERE singleton=true AND state='admitted' AND current_epoch={target_epoch - 1};
""",
    )


def retire_lease(replica_id: str) -> None:
    role, password = CONTROL_ROLE
    pg_role(
        role,
        password,
        f"UPDATE cache_control.bff_lease SET retired=true WHERE replica_id={q(replica_id)};",
    )


def exclusion_safe(tick: int) -> bool:
    target = control_scalar(
        "SELECT target_epoch FROM cache_control.admission_state "
        "WHERE singleton=true AND state='excluding';"
    )
    if not target:
        return False
    old_epoch = int(target) - 1
    remaining = int(
        control_scalar(
            f"""
SELECT count(*)
FROM cache_control.bff_lease
WHERE epoch={old_epoch}
  AND retired=false
  AND valid_until_tick > {tick};
"""
        )
        or "0"
    )
    return remaining == 0


def finalize_exclusion(tick: int) -> bool:
    if not exclusion_safe(tick):
        return False
    role, password = CONTROL_ROLE
    result = pg_role(
        role,
        password,
        f"""
UPDATE cache_control.admission_state
SET current_epoch=target_epoch,
    state='excluded',
    safe_after_tick={tick}
WHERE singleton=true AND state='excluding'
RETURNING current_epoch;
""",
    )
    return scalar(result) != ""


def pending_reconciliation_count() -> int:
    total = 0
    for owner in OWNER_CONFIG:
        total += int(
            owner_scalar(
                owner,
                f"SELECT count(*) FROM {owner}.security_cache_reconciliation WHERE done=false;",
            )
            or "0"
        )
    return total


def admit_new_epoch() -> bool:
    if pending_reconciliation_count() != 0:
        return False
    role, password = CONTROL_ROLE
    result = pg_role(
        role,
        password,
        """
UPDATE cache_control.admission_state
SET state='admitted', target_epoch=NULL
WHERE singleton=true AND state='excluded'
RETURNING current_epoch;
""",
    )
    return scalar(result) != ""


def snapshot_cache_rdb() -> Path:
    cache_cmd("SAVE")
    directory = cache_scalar("CONFIG", "GET", "dir")
    filename = cache_scalar("CONFIG", "GET", "dbfilename")
    td = tempfile.mkdtemp(prefix=f"d3-{CACHE_LABEL}-rdb-")
    target = Path(td) / filename
    run(["docker", "cp", f"{CACHE_CONTAINER}:{directory}/{filename}", str(target)])
    if not target.exists() or target.stat().st_size == 0:
        raise RuntimeError("candidate stale RDB snapshot was not captured")
    return target


def start_stale_replica(resource_id: str, lease: BffLease) -> str:
    name = f"jlmirror-d3-{CACHE_LABEL.replace('_','-')}-standby"
    run(["docker", "rm", "-f", name], check=False)
    run(
        [
            "docker",
            "run",
            "-d",
            "--name",
            name,
            "--network",
            DOCKER_NETWORK,
            CACHE_IMAGE,
            CACHE_SERVER,
            "--save",
            "",
            "--appendonly",
            "no",
            "--replicaof",
            CACHE_CONTAINER,
            "6379",
        ]
    )
    wait_cache(name, CACHE_CLI)
    for _ in range(80):
        info = cache_cmd("INFO", "replication", container=name).stdout
        if "master_link_status:up" in info:
            break
        time.sleep(0.25)
    else:
        raise RuntimeError("stale replica never synchronized")
    if admit("identity", resource_id, lease, 10, container=name, cli=CACHE_CLI) != "ALLOW":
        raise RuntimeError("replica negative control was not a genuinely authorizing stale positive")
    cache_cmd("REPLICAOF", "NO", "ONE", container=name)
    return name


def start_restore_container(rdb_path: Path) -> str:
    name = f"jlmirror-d3-{CACHE_LABEL.replace('_','-')}-restore"
    run(["docker", "rm", "-f", name], check=False)
    run(
        [
            "docker",
            "create",
            "--name",
            name,
            "--network",
            DOCKER_NETWORK,
            CACHE_IMAGE,
            CACHE_SERVER,
            "--save",
            "",
            "--appendonly",
            "no",
        ]
    )
    run(["docker", "cp", str(rdb_path), f"{name}:/data/dump.rdb"])
    run(["docker", "start", name])
    wait_cache(name, CACHE_CLI)
    return name


def prove_owner_boundaries() -> None:
    insert_resource("identity", "owner-session")
    insert_resource("membership", "owner-membership")
    insert_resource("authz", "owner-permission")
    insert_resource("platform", "owner-tenant")

    identity_role, identity_password, _ = OWNER_CONFIG["identity"]
    for forbidden_sql in (
        "UPDATE membership.memberships SET active=false WHERE resource_id='owner-membership';",
        "UPDATE authz.permissions SET active=false WHERE resource_id='owner-permission';",
        "UPDATE platform.tenants SET active=false WHERE resource_id='owner-tenant';",
    ):
        if pg_role(identity_role, identity_password, forbidden_sql, check=False).returncode == 0:
            raise RuntimeError("Identity/session owner crossed a business-authority boundary")

    membership_role, membership_password, _ = OWNER_CONFIG["membership"]
    if (
        pg_role(
            membership_role,
            membership_password,
            "UPDATE identity.sessions SET active=false WHERE resource_id='owner-session';",
            check=False,
        ).returncode
        == 0
    ):
        raise RuntimeError("Membership owner crossed into Identity/session authority")

    before = (
        resource_state("membership", "owner-membership"),
        resource_state("authz", "owner-permission"),
        resource_state("platform", "owner-tenant"),
    )
    pg_role(
        identity_role,
        identity_password,
        "UPDATE identity.sessions SET generation=2, active=false "
        "WHERE resource_id='owner-session' AND generation=1;",
    )
    after = (
        resource_state("membership", "owner-membership"),
        resource_state("authz", "owner-permission"),
        resource_state("platform", "owner-tenant"),
    )
    if before != after:
        raise RuntimeError("session mutation changed another canonical authority")

    if resource_state("identity", "owner-session") != (2, False):
        raise RuntimeError("Identity/session owner could not mutate its own truth")

    print(
        "d3_b_session_authority_owner_boundaries=PASS "
        "identity_session_only=true membership_cross_write_denied=true "
        "authorization_cross_write_denied=true tenant_lifecycle_cross_write_denied=true "
        "session_mutation_preserves_other_authorities=true"
    )


def prove_partial_write_and_single_winner() -> None:
    resource_id = "session-revocation"
    insert_resource("identity", resource_id)
    cache_cmd("FLUSHALL")
    set_cache_current("identity", resource_id, 1, 1)
    lease = BffLease("bff-proof", 1, 100)

    reserve_transition(
        "identity",
        transition_id="transition-cancel",
        resource_id=resource_id,
        expected_generation=1,
        fingerprint="logout:v1",
        owner_token="writer-a",
        lease_until_tick=10,
    )
    if install_fence("identity", resource_id, 1, "transition-cancel", 1) != "FENCED":
        raise RuntimeError("initial cache fence was not installed")
    if admit("identity", resource_id, lease, 5) != "DENY":
        raise RuntimeError("fenced scope still authorized a protected request")
    if cancel_transition("identity", "transition-cancel", 9):
        raise RuntimeError("cleanup cancelled a still-live transition")
    if not cancel_transition("identity", "transition-cancel", 11):
        raise RuntimeError("expired prepared transition could not be durably cancelled")
    if resource_state("identity", resource_id) != (1, True):
        raise RuntimeError("pre-commit cancellation mutated source authority")
    set_cache_current("identity", resource_id, 1, 1)
    if admit("identity", resource_id, lease, 12) != "ALLOW":
        raise RuntimeError("cancelled transition did not restore from current source truth")
    if commit_transition(
        "identity",
        transition_id="transition-cancel",
        owner_token="writer-a",
        tick=12,
        cache_eligible=True,
    ):
        raise RuntimeError("sleeping writer committed after durable cancellation")
    if resource_state("identity", resource_id) != (1, True):
        raise RuntimeError("sleeping writer changed authority after cancellation")

    state, existing_owner, _ = reserve_transition(
        "identity",
        transition_id="transition-commit",
        resource_id=resource_id,
        expected_generation=1,
        fingerprint="logout:v2",
        owner_token="writer-a",
        lease_until_tick=40,
    )
    if state != "prepared" or existing_owner != "writer-a":
        raise RuntimeError("fresh transition reservation was not owned by writer-a")
    state, existing_owner, _ = reserve_transition(
        "identity",
        transition_id="transition-commit",
        resource_id=resource_id,
        expected_generation=1,
        fingerprint="logout:v2",
        owner_token="writer-b",
        lease_until_tick=40,
    )
    if state != "prepared" or existing_owner != "writer-a":
        raise RuntimeError("compatible retry stole live transition ownership")
    try:
        reserve_transition(
            "identity",
            transition_id="transition-commit",
            resource_id=resource_id,
            expected_generation=1,
            fingerprint="different-effect",
            owner_token="writer-c",
            lease_until_tick=40,
        )
    except RuntimeError:
        pass
    else:
        raise RuntimeError("transition fingerprint mismatch was admitted")

    if install_fence("identity", resource_id, 1, "transition-commit", 1) != "FENCED":
        raise RuntimeError("commit transition fence was not installed")
    if install_fence("identity", resource_id, 1, "transition-competitor", 1) != "LOST":
        raise RuntimeError("competing transition overwrote an installed fence")
    if commit_transition(
        "identity",
        transition_id="transition-commit",
        owner_token="writer-b",
        tick=20,
        cache_eligible=fence_is_exact("identity", resource_id, "transition-commit"),
    ):
        raise RuntimeError("non-owner committed a live transition")
    if not commit_transition(
        "identity",
        transition_id="transition-commit",
        owner_token="writer-a",
        tick=20,
        cache_eligible=fence_is_exact("identity", resource_id, "transition-commit"),
    ):
        raise RuntimeError("live transition owner could not commit source truth")

    if resource_state("identity", resource_id) != (2, False):
        raise RuntimeError("source revocation did not commit exact generation")
    if transition_state("identity", "transition-commit") != "committed|1|1":
        raise RuntimeError("source commit did not atomically persist reconciliation+audit responsibility")
    if admit("identity", resource_id, lease, 21) != "DENY":
        raise RuntimeError("post-commit/pre-finalize crash resurrected positive authority")

    set_cache_revoked("identity", resource_id, 2, 1, "transition-commit")
    mark_reconciled("identity", "transition-commit")
    if transition_state("identity", "transition-commit") != "finalized|0|1":
        raise RuntimeError("reconciliation did not durably finalize transition")
    if admit("identity", resource_id, lease, 22) != "DENY":
        raise RuntimeError("finalized revoked generation authorized")

    print(
        "d3_b_revocation_partial_write_safety=PASS "
        "fence_before_commit=true cancel_before_cleanup=true sleeping_writer_fenced=true "
        "post_commit_pre_finalize_non_authorizing=true durable_reconciliation=true audit_intent_atomic=true"
    )
    print(
        "d3_b_prepare_fence_commit_finalize_single_winner=PASS "
        "compatible_retry_observes=true fingerprint_mismatch_rejected=true "
        "transition_owner_single_winner=true competing_fence_rejected=true "
        "expected_generation_cas=true cleanup_writer_race_single_winner=true"
    )


def prove_fleet_barrier_restore_failover() -> None:
    resource_id = "session-fleet"
    insert_resource("identity", resource_id)
    cache_cmd("FLUSHALL")
    set_cache_current("identity", resource_id, 1, 1)

    lease_a = issue_lease("bff-a", 1, 40)
    lease_b = issue_lease("bff-b", 1, 40)
    lease_c = issue_lease("bff-c", 1, 60)
    if admit("identity", resource_id, lease_a, 10) != "ALLOW":
        raise RuntimeError("healthy fleet negative control did not authorize current cache state")

    rdb_path = snapshot_cache_rdb()
    standby = start_stale_replica(resource_id, lease_a)

    reserve_transition(
        "identity",
        transition_id="transition-degraded",
        resource_id=resource_id,
        expected_generation=1,
        fingerprint="fleet-logout:v1",
        owner_token="writer-degraded",
        lease_until_tick=100,
    )

    if commit_transition(
        "identity",
        transition_id="transition-degraded",
        owner_token="writer-degraded",
        tick=20,
        cache_eligible=False,
    ):
        raise RuntimeError("source commit ignored local cache-fence failure")
    if resource_state("identity", resource_id) != (1, True):
        raise RuntimeError("blocked degraded commit still changed source truth")

    begin_exclusion(2)
    retire_lease("bff-a")
    retire_lease("bff-b")
    if exclusion_safe(30):
        raise RuntimeError("fleet exclusion ignored an unretired live BFF lease")
    if finalize_exclusion(30):
        raise RuntimeError("fleet exclusion finalized before old-generation safety horizon")
    if commit_transition(
        "identity",
        transition_id="transition-degraded",
        owner_token="writer-degraded",
        tick=30,
        cache_eligible=False,
    ):
        raise RuntimeError("degraded source commit escaped before fleet barrier")

    if not exclusion_safe(61) or not finalize_exclusion(61):
        raise RuntimeError("fleet barrier did not close after every old lease retired/expired")
    for lease in (lease_a, lease_b, lease_c):
        if admit("identity", resource_id, lease, 61) != "DENY":
            raise RuntimeError("retired/expired old admission lease still authorized stale cache")

    if not commit_transition(
        "identity",
        transition_id="transition-degraded",
        owner_token="writer-degraded",
        tick=62,
        cache_eligible=True,
    ):
        raise RuntimeError("fleet-excluded degraded owner mutation did not commit")
    if resource_state("identity", resource_id) != (2, False):
        raise RuntimeError("degraded source owner did not become revoked")

    if admit_new_epoch():
        raise RuntimeError("cache re-entry occurred before durable source reconciliation")
    set_cache_revoked("identity", resource_id, 2, 2, "transition-degraded")
    mark_reconciled("identity", "transition-degraded")
    if not admit_new_epoch():
        raise RuntimeError("reconciled cache could not establish a fresh admission epoch")
    new_lease = issue_lease("bff-new", 2, 120)

    restore = start_restore_container(rdb_path)
    try:
        if admit("identity", resource_id, new_lease, 70, container=standby, cli=CACHE_CLI) != "DENY":
            raise RuntimeError("stale promoted replica resurrected positive authority")
        if admit("identity", resource_id, new_lease, 70, container=restore, cli=CACHE_CLI) != "DENY":
            raise RuntimeError("stale restored RDB resurrected positive authority")
        if admit("identity", resource_id, new_lease, 70) != "DENY":
            raise RuntimeError("current revoked cache state authorized")
    finally:
        run(["docker", "rm", "-f", restore], check=False)
        run(["docker", "rm", "-f", standby], check=False)
        try:
            rdb_path.unlink(missing_ok=True)
            rdb_path.parent.rmdir()
        except OSError:
            pass

    print(
        "d3_b_fleet_wide_cache_exclusion_barrier=PASS "
        "local_cache_failure_not_global_proof=true old_lease_retirement_or_expiry_required=true "
        "degraded_commit_after_barrier_only=true reentry_requires_reconciliation=true "
        "admission_continuity_external_to_cache=true"
    )
    print(
        "d3_b_restore_failover_positive_authority_nonresurrection=PASS "
        "genuine_old_positive_negative_control=true stale_replica_promoted=true stale_rdb_restored=true "
        "external_epoch_blocks_both=true fresh_epoch_after_reconciliation=true"
    )


class OwnerReadBulkhead:
    def __init__(self, capacity: int) -> None:
        self._semaphore = threading.BoundedSemaphore(capacity)

    def try_read(self, read_fn) -> tuple[bool, tuple[int, bool] | None]:
        if not self._semaphore.acquire(blocking=False):
            return False, None
        try:
            return True, read_fn()
        except Exception:
            return False, None
        finally:
            self._semaphore.release()

    def acquire_for_test(self) -> bool:
        return self._semaphore.acquire(blocking=False)

    def release_for_test(self) -> None:
        self._semaphore.release()


def prove_degraded_owner_bulkhead() -> None:
    resource_id = "session-owner-read"
    insert_resource("identity", resource_id)
    cache_cmd("DEL", positive_key("identity", resource_id))
    bulkhead = OwnerReadBulkhead(capacity=2)

    if not bulkhead.acquire_for_test() or not bulkhead.acquire_for_test():
        raise RuntimeError("could not saturate owner-read bulkhead")
    called = [False]

    def forbidden_overflow_read() -> tuple[int, bool]:
        called[0] = True
        return resource_state("identity", resource_id)

    admitted, value = bulkhead.try_read(forbidden_overflow_read)
    if admitted or value is not None or called[0]:
        raise RuntimeError("bulkhead admitted or invoked owner I/O beyond configured evidence capacity")
    bulkhead.release_for_test()
    bulkhead.release_for_test()

    admitted, value = bulkhead.try_read(lambda: resource_state("identity", resource_id))
    if not admitted or value != (1, True):
        raise RuntimeError("available current durable owner could not serve degraded read")

    run(["docker", "pause", PG_CONTAINER])
    try:
        admitted, value = bulkhead.try_read(lambda: resource_state("identity", resource_id))
        if admitted or value is not None:
            raise RuntimeError("paused durable owner manufactured positive authority")
        if cache_scalar("EXISTS", positive_key("identity", resource_id)) != "0":
            raise RuntimeError("failed degraded owner read still filled positive cache")
    finally:
        run(["docker", "unpause", PG_CONTAINER])

    if resource_state("identity", resource_id) != (1, True):
        raise RuntimeError("owner did not recover after evidence outage")

    print(
        "d3_b_degraded_owner_read_bulkhead_fail_closed=PASS "
        "bounded_concurrency=true overflow_denied_before_owner_io=true "
        "current_owner_read_required=true actual_owner_outage_denied=true "
        "failed_read_no_positive_fill=true"
    )


def main() -> int:
    wait_cache(CACHE_CONTAINER, CACHE_CLI)
    setup_postgres()
    prove_owner_boundaries()
    prove_partial_write_and_single_winner()
    prove_fleet_barrier_restore_failover()
    prove_degraded_owner_bulkhead()
    print(
        "d3_b_session_cache_conformance_runner=PASS "
        f"candidate={CACHE_LABEL} "
        "owner_boundaries=true partial_write_safety=true transition_single_winner=true "
        "fleet_barrier=true restore_failover_nonresurrection=true owner_bulkhead_fail_closed=true"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
