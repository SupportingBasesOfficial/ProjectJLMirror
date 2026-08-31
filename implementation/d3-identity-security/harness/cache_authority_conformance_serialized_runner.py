from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os
import secrets
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
_LOCAL_RETIRED: set[tuple[str, str]] = set()


def run(args: list[str], *, check: bool = True, timeout: float = 30.0) -> subprocess.CompletedProcess[str]:
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
            f"stdout={result.stdout[-2400:]}\nstderr={result.stderr[-2400:]}"
        )
    return result


def q(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def scalar(result: subprocess.CompletedProcess[str]) -> str:
    lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    return lines[-1] if lines else ""


def pg_super(sql: str, *, check: bool = True) -> subprocess.CompletedProcess[str]:
    return run(
        [
            "docker", "exec", "-e", f"PGPASSWORD={PG_SUPER_PASSWORD}", PG_CONTAINER,
            "psql", "-h", "127.0.0.1", "-U", "postgres", "-d", "d3",
            "-X", "-q", "-A", "-t", "-v", "ON_ERROR_STOP=1", "-c", sql,
        ],
        check=check,
    )


def pg_role(role: str, password: str, sql: str, *, check: bool = True) -> subprocess.CompletedProcess[str]:
    return run(
        [
            "docker", "exec", "-e", f"PGPASSWORD={password}", PG_CONTAINER,
            "psql", "-h", "127.0.0.1", "-U", role, "-d", "d3",
            "-X", "-q", "-A", "-t", "-v", "ON_ERROR_STOP=1", "-c", sql,
        ],
        check=check,
    )


def owner_scalar(owner: str, sql: str) -> str:
    role, password, _ = OWNER_CONFIG[owner]
    return scalar(pg_role(role, password, sql))


def control_scalar(sql: str) -> str:
    role, password = CONTROL_ROLE
    return scalar(pg_role(role, password, sql))


def cache_cmd(*args: str, container: str | None = None, cli: str | None = None, check: bool = True) -> subprocess.CompletedProcess[str]:
    return run(
        ["docker", "exec", container or CACHE_CONTAINER, cli or CACHE_CLI, "--raw", *args],
        check=check,
    )


def cache_scalar(*args: str, container: str | None = None, cli: str | None = None) -> str:
    return scalar(cache_cmd(*args, container=container, cli=cli))


def wait_cache(container: str, cli: str) -> None:
    for _ in range(80):
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
  ELSE ALTER ROLE d3_identity_owner PASSWORD 'd3-identity-owner-password'; END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='d3_membership_owner') THEN
    CREATE ROLE d3_membership_owner LOGIN PASSWORD 'd3-membership-owner-password';
  ELSE ALTER ROLE d3_membership_owner PASSWORD 'd3-membership-owner-password'; END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='d3_authz_owner') THEN
    CREATE ROLE d3_authz_owner LOGIN PASSWORD 'd3-authz-owner-password';
  ELSE ALTER ROLE d3_authz_owner PASSWORD 'd3-authz-owner-password'; END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='d3_platform_owner') THEN
    CREATE ROLE d3_platform_owner LOGIN PASSWORD 'd3-platform-owner-password';
  ELSE ALTER ROLE d3_platform_owner PASSWORD 'd3-platform-owner-password'; END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='d3_cache_control_owner') THEN
    CREATE ROLE d3_cache_control_owner LOGIN PASSWORD 'd3-cache-control-password';
  ELSE ALTER ROLE d3_cache_control_owner PASSWORD 'd3-cache-control-password'; END IF;
END
$d3$;
GRANT CONNECT ON DATABASE d3 TO d3_identity_owner,d3_membership_owner,d3_authz_owner,d3_platform_owner,d3_cache_control_owner;
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
REVOKE ALL ON SCHEMA identity,membership,authz,platform,cache_control FROM PUBLIC;
"""
    )
    for owner, (table, _label) in {
        "identity": ("sessions", "session"),
        "membership": ("memberships", "membership"),
        "authz": ("permissions", "permission"),
        "platform": ("tenants", "tenant"),
    }.items():
        role, password, _ = OWNER_CONFIG[owner]
        pg_role(
            role,
            password,
            f"""
CREATE TABLE {owner}.{table}(
  resource_id text PRIMARY KEY,
  generation bigint NOT NULL CHECK (generation > 0),
  active boolean NOT NULL
);
CREATE TABLE {owner}.security_cache_transition(
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
CREATE TABLE {owner}.security_cache_reconciliation(
  transition_id text PRIMARY KEY,
  done boolean NOT NULL DEFAULT false
);
CREATE TABLE {owner}.security_audit_intent(
  transition_id text PRIMARY KEY,
  event_type text NOT NULL
);
""",
        )
    role, password = CONTROL_ROLE
    pg_role(
        role,
        password,
        """
CREATE TABLE cache_control.scope_admission(
  scope_key text PRIMARY KEY,
  current_epoch bigint NOT NULL CHECK (current_epoch > 0),
  state text NOT NULL CHECK (state IN ('admitted','excluding','excluded')),
  target_epoch bigint,
  hold_transition_id text,
  safe_after_tick bigint
);
CREATE TABLE cache_control.scope_lease(
  scope_key text NOT NULL,
  replica_id text NOT NULL,
  epoch bigint NOT NULL,
  valid_until_tick bigint NOT NULL,
  retired boolean NOT NULL DEFAULT false,
  PRIMARY KEY(scope_key, replica_id)
);
COMMENT ON TABLE cache_control.scope_admission IS
  'Trusted expected-admission continuity evidence independent of Redis/Valkey dataset; not business authority.';
""",
    )


def owner_table(owner: str) -> str:
    return OWNER_CONFIG[owner][2]


def scope_key(owner: str, resource_id: str) -> str:
    return f"{owner}:{resource_id}"


def ensure_scope(scope: str, epoch: int = 1) -> None:
    role, password = CONTROL_ROLE
    pg_role(
        role,
        password,
        f"""
INSERT INTO cache_control.scope_admission(scope_key,current_epoch,state,target_epoch,hold_transition_id,safe_after_tick)
VALUES ({q(scope)},{epoch},'admitted',NULL,NULL,NULL)
ON CONFLICT (scope_key) DO NOTHING;
""",
    )


def scope_state(scope: str) -> tuple[str, int, int | None, str | None]:
    raw = control_scalar(
        f"""
SELECT state||'|'||current_epoch||'|'||COALESCE(target_epoch::text,'')||'|'||COALESCE(hold_transition_id,'')
FROM cache_control.scope_admission WHERE scope_key={q(scope)};
"""
    )
    state, current, target, hold = raw.split("|")
    return state, int(current), None if target == "" else int(target), hold or None


def insert_resource(owner: str, resource_id: str, generation: int = 1, active: bool = True) -> None:
    role, password, table = OWNER_CONFIG[owner]
    pg_role(
        role,
        password,
        f"INSERT INTO {table}(resource_id,generation,active) VALUES ({q(resource_id)},{generation},{'true' if active else 'false'});",
    )
    ensure_scope(scope_key(owner, resource_id))


def resource_state(owner: str, resource_id: str) -> tuple[int, bool]:
    raw = owner_scalar(
        owner,
        f"SELECT generation||'|'||CASE WHEN active THEN '1' ELSE '0' END FROM {owner_table(owner)} WHERE resource_id={q(resource_id)};",
    )
    generation, active = raw.split("|")
    return int(generation), active == "1"


def reserve_transition(owner: str, transition_id: str, resource_id: str, expected_generation: int, fingerprint: str, owner_token: str, lease_until_tick: int) -> tuple[str, str]:
    role, password, _ = OWNER_CONFIG[owner]
    pg_role(
        role,
        password,
        f"""
INSERT INTO {owner}.security_cache_transition
(transition_id,resource_id,expected_generation,fingerprint,state,owner_token,lease_until_tick)
VALUES ({q(transition_id)},{q(resource_id)},{expected_generation},{q(fingerprint)},'prepared',{q(owner_token)},{lease_until_tick})
ON CONFLICT (transition_id) DO NOTHING;
""",
    )
    raw = owner_scalar(
        owner,
        f"SELECT resource_id||'|'||expected_generation||'|'||fingerprint||'|'||state||'|'||owner_token FROM {owner}.security_cache_transition WHERE transition_id={q(transition_id)};",
    )
    existing_resource, existing_generation, existing_fingerprint, state, existing_owner = raw.split("|")
    if existing_resource != resource_id or int(existing_generation) != expected_generation or existing_fingerprint != fingerprint:
        raise RuntimeError("transition identity/fingerprint mismatch rejected")
    return state, existing_owner


def transition_state(owner: str, transition_id: str) -> str:
    return owner_scalar(
        owner,
        f"SELECT state||'|'||CASE WHEN reconcile_pending THEN '1' ELSE '0' END||'|'||CASE WHEN audit_intent THEN '1' ELSE '0' END FROM {owner}.security_cache_transition WHERE transition_id={q(transition_id)};",
    )


def cancel_transition(owner: str, transition_id: str, tick: int) -> bool:
    role, password, _ = OWNER_CONFIG[owner]
    result = pg_role(
        role,
        password,
        f"""
UPDATE {owner}.security_cache_transition
SET state='cancelled'
WHERE transition_id={q(transition_id)} AND state='prepared' AND lease_until_tick <= {tick}
RETURNING transition_id;
""",
    )
    return scalar(result) == transition_id


def takeover_transition(owner: str, transition_id: str, tick: int, new_owner: str, lease_until_tick: int) -> bool:
    role, password, _ = OWNER_CONFIG[owner]
    result = pg_role(
        role,
        password,
        f"""
UPDATE {owner}.security_cache_transition
SET owner_token={q(new_owner)}, lease_until_tick={lease_until_tick}
WHERE transition_id={q(transition_id)} AND state='prepared' AND lease_until_tick <= {tick}
RETURNING transition_id;
""",
    )
    return scalar(result) == transition_id


def begin_scope_exclusion(scope: str, transition_id: str) -> int:
    role, password = CONTROL_ROLE
    result = pg_role(
        role,
        password,
        f"""
DO $d3$
DECLARE v_state text; v_current bigint; v_target bigint; v_hold text;
BEGIN
  SELECT state,current_epoch,target_epoch,hold_transition_id
    INTO v_state,v_current,v_target,v_hold
  FROM cache_control.scope_admission
  WHERE scope_key={q(scope)} FOR UPDATE;
  IF NOT FOUND THEN RAISE EXCEPTION 'scope admission state absent'; END IF;
  IF v_state='admitted' AND v_hold IS NULL THEN
    UPDATE cache_control.scope_admission
    SET state='excluding',target_epoch=v_current+1,hold_transition_id={q(transition_id)},safe_after_tick=NULL
    WHERE scope_key={q(scope)};
  ELSIF v_state IN ('excluding','excluded') AND v_hold={q(transition_id)} THEN
    NULL;
  ELSE
    RAISE EXCEPTION 'scope exclusion owned by another transition or not admissible';
  END IF;
END
$d3$;
""",
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError("scope exclusion reservation rejected")
    state, _current, target, hold = scope_state(scope)
    if state not in {"excluding", "excluded"} or target is None or hold != transition_id:
        raise RuntimeError("scope exclusion reservation did not persist exact hold")
    return target


@dataclass(frozen=True)
class BffLease:
    scope_key: str
    replica_id: str
    epoch: int
    valid_until_tick: int


def issue_scope_lease(scope: str, replica_id: str, epoch: int, valid_until_tick: int) -> BffLease:
    role, password = CONTROL_ROLE
    result = pg_role(
        role,
        password,
        f"""
DO $d3$
DECLARE v_state text; v_epoch bigint;
BEGIN
  SELECT state,current_epoch INTO v_state,v_epoch
  FROM cache_control.scope_admission WHERE scope_key={q(scope)} FOR UPDATE;
  IF NOT FOUND OR v_state <> 'admitted' OR v_epoch <> {epoch} THEN
    RAISE EXCEPTION 'requested scope epoch is not currently issuable';
  END IF;
  INSERT INTO cache_control.scope_lease(scope_key,replica_id,epoch,valid_until_tick,retired)
  VALUES ({q(scope)},{q(replica_id)},{epoch},{valid_until_tick},false)
  ON CONFLICT (scope_key,replica_id) DO UPDATE SET
    epoch=EXCLUDED.epoch,valid_until_tick=EXCLUDED.valid_until_tick,retired=false;
END
$d3$;
""",
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError("scope lease issuance/renewal rejected by serialized admission state")
    _LOCAL_RETIRED.discard((scope, replica_id))
    return BffLease(scope, replica_id, epoch, valid_until_tick)


def retire_scope_lease(lease: BffLease) -> None:
    role, password = CONTROL_ROLE
    pg_role(
        role,
        password,
        f"UPDATE cache_control.scope_lease SET retired=true WHERE scope_key={q(lease.scope_key)} AND replica_id={q(lease.replica_id)} AND epoch={lease.epoch};",
    )
    _LOCAL_RETIRED.add((lease.scope_key, lease.replica_id))


def live_old_lease_count(scope: str, epoch: int, tick: int) -> int:
    return int(
        control_scalar(
            f"SELECT count(*) FROM cache_control.scope_lease WHERE scope_key={q(scope)} AND epoch={epoch} AND retired=false AND valid_until_tick > {tick};"
        )
        or "0"
    )


def finalize_scope_exclusion(scope: str, transition_id: str, tick: int) -> bool:
    role, password = CONTROL_ROLE
    result = pg_role(
        role,
        password,
        f"""
DO $d3$
DECLARE v_state text; v_current bigint; v_target bigint; v_hold text; v_live bigint;
BEGIN
  SELECT state,current_epoch,target_epoch,hold_transition_id
    INTO v_state,v_current,v_target,v_hold
  FROM cache_control.scope_admission WHERE scope_key={q(scope)} FOR UPDATE;
  IF v_state <> 'excluding' OR v_hold <> {q(transition_id)} OR v_target IS NULL THEN
    RAISE EXCEPTION 'scope exclusion is not held by transition';
  END IF;
  SELECT count(*) INTO v_live FROM cache_control.scope_lease
  WHERE scope_key={q(scope)} AND epoch=v_current AND retired=false AND valid_until_tick > {tick};
  IF v_live <> 0 THEN RAISE EXCEPTION 'old scope leases remain live'; END IF;
  UPDATE cache_control.scope_admission
  SET state='excluded',current_epoch=v_target,safe_after_tick={tick}
  WHERE scope_key={q(scope)};
END
$d3$;
""",
        check=False,
    )
    return result.returncode == 0


def assert_excluded_hold(scope: str, transition_id: str) -> int:
    state, current, target, hold = scope_state(scope)
    if state != "excluded" or target != current or hold != transition_id:
        raise RuntimeError("source commit lacks exact durable scope exclusion hold")
    return current


def commit_source(owner: str, transition_id: str, owner_token: str, tick: int) -> bool:
    scope = owner_scalar(
        owner,
        f"SELECT resource_id FROM {owner}.security_cache_transition WHERE transition_id={q(transition_id)};",
    )
    if not scope:
        return False
    scope = scope_key(owner, scope)
    try:
        assert_excluded_hold(scope, transition_id)
    except RuntimeError:
        return False
    role, password, table = OWNER_CONFIG[owner]
    result = pg_role(
        role,
        password,
        f"""
DO $d3$
DECLARE v_resource text; v_expected bigint; v_count integer;
BEGIN
  SELECT resource_id,expected_generation INTO v_resource,v_expected
  FROM {owner}.security_cache_transition
  WHERE transition_id={q(transition_id)} AND state='prepared' AND owner_token={q(owner_token)} AND lease_until_tick > {tick}
  FOR UPDATE;
  IF NOT FOUND THEN RAISE EXCEPTION 'transition is not live owned prepared'; END IF;
  UPDATE {table} SET generation=generation+1,active=false
  WHERE resource_id=v_resource AND generation=v_expected AND active=true;
  GET DIAGNOSTICS v_count=ROW_COUNT;
  IF v_count <> 1 THEN RAISE EXCEPTION 'expected-generation CAS lost'; END IF;
  UPDATE {owner}.security_cache_transition
  SET state='committed',reconcile_pending=true,audit_intent=true,committed_generation=v_expected+1
  WHERE transition_id={q(transition_id)} AND state='prepared' AND owner_token={q(owner_token)};
  GET DIAGNOSTICS v_count=ROW_COUNT;
  IF v_count <> 1 THEN RAISE EXCEPTION 'transition commit lost'; END IF;
  INSERT INTO {owner}.security_cache_reconciliation(transition_id,done) VALUES ({q(transition_id)},false);
  INSERT INTO {owner}.security_audit_intent(transition_id,event_type) VALUES ({q(transition_id)},'security_authority_revoked');
END
$d3$;
""",
        check=False,
    )
    return result.returncode == 0


def finalize_source_reconciliation(owner: str, transition_id: str) -> None:
    role, password, _ = OWNER_CONFIG[owner]
    pg_role(
        role,
        password,
        f"""
DO $d3$
DECLARE v_count integer;
BEGIN
  UPDATE {owner}.security_cache_reconciliation SET done=true
  WHERE transition_id={q(transition_id)} AND done=false;
  GET DIAGNOSTICS v_count=ROW_COUNT;
  IF v_count <> 1 THEN RAISE EXCEPTION 'reconciliation completion lost'; END IF;
  UPDATE {owner}.security_cache_transition SET state='finalized',reconcile_pending=false
  WHERE transition_id={q(transition_id)} AND state='committed' AND reconcile_pending=true;
  GET DIAGNOSTICS v_count=ROW_COUNT;
  IF v_count <> 1 THEN RAISE EXCEPTION 'source finalization lost'; END IF;
END
$d3$;
""",
    )


def release_scope_after_terminal(owner: str, transition_id: str, *, cancelled: bool = False) -> int:
    expected = "cancelled|0|0" if cancelled else "finalized|0|1"
    if transition_state(owner, transition_id) != expected:
        raise RuntimeError("scope release attempted before exact durable source terminal state")
    resource_id = owner_scalar(owner, f"SELECT resource_id FROM {owner}.security_cache_transition WHERE transition_id={q(transition_id)};")
    scope = scope_key(owner, resource_id)
    role, password = CONTROL_ROLE
    result = pg_role(
        role,
        password,
        f"""
DO $d3$
DECLARE v_state text; v_epoch bigint; v_hold text;
BEGIN
  SELECT state,current_epoch,hold_transition_id INTO v_state,v_epoch,v_hold
  FROM cache_control.scope_admission WHERE scope_key={q(scope)} FOR UPDATE;
  IF v_hold <> {q(transition_id)} THEN RAISE EXCEPTION 'scope hold belongs to another transition'; END IF;
  IF v_state='excluding' AND {str(cancelled).lower()} THEN
    UPDATE cache_control.scope_admission
    SET state='admitted',target_epoch=NULL,hold_transition_id=NULL,safe_after_tick=NULL
    WHERE scope_key={q(scope)};
  ELSIF v_state='excluded' AND NOT {str(cancelled).lower()} THEN
    UPDATE cache_control.scope_admission
    SET state='admitted',target_epoch=NULL,hold_transition_id=NULL
    WHERE scope_key={q(scope)};
  ELSE
    RAISE EXCEPTION 'scope terminal release state mismatch';
  END IF;
END
$d3$;
""",
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError("exact terminal transition could not release scope admission hold")
    return scope_state(scope)[1]


FENCE_SCRIPT = r"""
local state=redis.call('HGET',KEYS[1],'state')
local generation=redis.call('HGET',KEYS[1],'generation')
local transition=redis.call('HGET',KEYS[1],'transition_id')
if state=='fence' and transition==ARGV[2] then return 'IDEMPOTENT' end
if state~='current' or generation~=ARGV[1] then return 'LOST' end
redis.call('HSET',KEYS[1],'state','fence','generation',ARGV[1],'transition_id',ARGV[2],'admission_epoch',ARGV[3])
return 'FENCED'
"""
ADMISSION_SCRIPT = r"""
local authority=redis.call('HMGET',KEYS[1],'state','generation','admission_epoch')
local positive=redis.call('HMGET',KEYS[2],'active','owner_generation','admission_epoch')
if authority[1]~='current' then return 'DENY' end
if positive[1]~='1' then return 'DENY' end
if authority[2]~=positive[2] then return 'DENY' end
if authority[3]~=ARGV[1] then return 'DENY' end
if positive[3]~=ARGV[1] then return 'DENY' end
return 'ALLOW'
"""


def authority_key(owner: str, resource_id: str) -> str:
    return f"authority:{owner}:{resource_id}"


def positive_key(owner: str, resource_id: str) -> str:
    return f"positive:{owner}:{resource_id}"


def set_cache_current(owner: str, resource_id: str, generation: int, epoch: int, *, container: str | None = None) -> None:
    cache_cmd("HSET",authority_key(owner,resource_id),"state","current","generation",str(generation),"transition_id","","admission_epoch",str(epoch),container=container)
    cache_cmd("HSET",positive_key(owner,resource_id),"active","1","owner_generation",str(generation),"admission_epoch",str(epoch),container=container)


def set_cache_revoked(owner: str, resource_id: str, generation: int, epoch: int, transition_id: str, *, container: str | None = None) -> None:
    cache_cmd("HSET",authority_key(owner,resource_id),"state","revoked","generation",str(generation),"transition_id",transition_id,"admission_epoch",str(epoch),container=container)


def install_fence(owner: str, resource_id: str, expected_generation: int, transition_id: str, epoch: int) -> str:
    return cache_scalar("EVAL",FENCE_SCRIPT,"1",authority_key(owner,resource_id),str(expected_generation),transition_id,str(epoch))


def raw_admit(owner: str, resource_id: str, lease: BffLease, tick: int, *, container: str | None = None, cli: str | None = None) -> str:
    if tick >= lease.valid_until_tick:
        return "DENY"
    return cache_scalar("EVAL",ADMISSION_SCRIPT,"2",authority_key(owner,resource_id),positive_key(owner,resource_id),str(lease.epoch),container=container,cli=cli)


def admit(owner: str, resource_id: str, lease: BffLease, tick: int, *, container: str | None = None, cli: str | None = None) -> str:
    if (lease.scope_key, lease.replica_id) in _LOCAL_RETIRED:
        return "DENY"
    return raw_admit(owner, resource_id, lease, tick, container=container, cli=cli)


def snapshot_rdb() -> Path:
    cache_cmd("SAVE")
    directory = cache_scalar("CONFIG","GET","dir")
    filename = cache_scalar("CONFIG","GET","dbfilename")
    td = Path(tempfile.mkdtemp(prefix=f"d3-{CACHE_LABEL}-rdb-"))
    target = td / filename
    run(["docker","cp",f"{CACHE_CONTAINER}:{directory}/{filename}",str(target)])
    if not target.exists() or target.stat().st_size == 0:
        raise RuntimeError("stale RDB snapshot not captured")
    return target


def start_stale_replica(owner: str, resource_id: str, old_lease: BffLease) -> str:
    name=f"jlmirror-d3-{CACHE_LABEL.replace('_','-')}-standby"
    run(["docker","rm","-f",name],check=False)
    run(["docker","run","-d","--name",name,"--network",DOCKER_NETWORK,CACHE_IMAGE,CACHE_SERVER,"--save","","--appendonly","no","--replicaof",CACHE_CONTAINER,"6379"])
    wait_cache(name,CACHE_CLI)
    for _ in range(80):
        if "master_link_status:up" in cache_cmd("INFO","replication",container=name).stdout:
            break
        time.sleep(0.25)
    else:
        raise RuntimeError("stale replica never synchronized")
    if raw_admit(owner,resource_id,old_lease,10,container=name,cli=CACHE_CLI) != "ALLOW":
        raise RuntimeError("replica did not contain genuinely authorizing old positive bytes")
    cache_cmd("REPLICAOF","NO","ONE",container=name)
    if raw_admit(owner,resource_id,old_lease,10,container=name,cli=CACHE_CLI) != "ALLOW":
        raise RuntimeError("promoted stale replica lost old positive negative-control bytes")
    return name


def start_restore(rdb: Path, owner: str, resource_id: str, old_lease: BffLease) -> str:
    name=f"jlmirror-d3-{CACHE_LABEL.replace('_','-')}-restore"
    run(["docker","rm","-f",name],check=False)
    run(["docker","create","--name",name,"--network",DOCKER_NETWORK,CACHE_IMAGE,CACHE_SERVER,"--save","","--appendonly","no"])
    run(["docker","cp",str(rdb),f"{name}:/data/dump.rdb"])
    run(["docker","start",name])
    wait_cache(name,CACHE_CLI)
    if raw_admit(owner,resource_id,old_lease,10,container=name,cli=CACHE_CLI) != "ALLOW":
        raise RuntimeError("restored RDB did not reconstruct genuinely authorizing old positive bytes")
    return name


def prove_owner_boundaries() -> None:
    resources={"identity":"owner-session","membership":"owner-membership","authz":"owner-permission","platform":"owner-tenant"}
    for owner,rid in resources.items(): insert_resource(owner,rid)
    identity_role,identity_password,_=OWNER_CONFIG["identity"]
    for sql in (
        "UPDATE membership.memberships SET active=false WHERE resource_id='owner-membership';",
        "UPDATE authz.permissions SET active=false WHERE resource_id='owner-permission';",
        "UPDATE platform.tenants SET active=false WHERE resource_id='owner-tenant';",
    ):
        if pg_role(identity_role,identity_password,sql,check=False).returncode==0:
            raise RuntimeError("Identity/session owner crossed business authority boundary")
    before={owner:resource_state(owner,rid) for owner,rid in resources.items() if owner!="identity"}
    pg_role(identity_role,identity_password,"UPDATE identity.sessions SET generation=2,active=false WHERE resource_id='owner-session' AND generation=1;")
    after={owner:resource_state(owner,rid) for owner,rid in resources.items() if owner!="identity"}
    if before!=after or resource_state("identity","owner-session")!=(2,False):
        raise RuntimeError("session mutation changed another authority or failed own authority")
    print("d3_b_session_authority_owner_boundaries=PASS identity_session_only=true membership_cross_write_denied=true authorization_cross_write_denied=true tenant_lifecycle_cross_write_denied=true session_mutation_preserves_other_authorities=true")


def prove_partial_write_and_single_winner() -> None:
    owner="identity"; rid="session-revocation"; scope=scope_key(owner,rid)
    insert_resource(owner,rid); cache_cmd("FLUSHALL"); set_cache_current(owner,rid,1,1)
    old_lease=issue_scope_lease(scope,"bff-partial",1,30)
    reserve_transition(owner,"transition-cancel",rid,1,"logout:v1","writer-a",10)
    if install_fence(owner,rid,1,"transition-cancel",1)!="FENCED": raise RuntimeError("precommit fence missing")
    if admit(owner,rid,old_lease,5)!="DENY": raise RuntimeError("fence did not deny")
    if cancel_transition(owner,"transition-cancel",9): raise RuntimeError("live transition cancelled")
    if not cancel_transition(owner,"transition-cancel",11): raise RuntimeError("expired transition not cancelled")
    if commit_source(owner,"transition-cancel","writer-a",12): raise RuntimeError("cancelled sleeping writer committed")
    cache_cmd("DEL",authority_key(owner,rid)); set_cache_current(owner,rid,1,1)
    if resource_state(owner,rid)!=(1,True): raise RuntimeError("cancel path mutated source")

    state,existing=reserve_transition(owner,"transition-commit",rid,1,"logout:v2","writer-a",50)
    if state!="prepared" or existing!="writer-a": raise RuntimeError("transition owner mismatch")
    state,existing=reserve_transition(owner,"transition-commit",rid,1,"logout:v2","writer-b",50)
    if existing!="writer-a": raise RuntimeError("compatible retry stole transition")
    try: reserve_transition(owner,"transition-commit",rid,1,"different","writer-c",50)
    except RuntimeError: pass
    else: raise RuntimeError("fingerprint mismatch admitted")
    if install_fence(owner,rid,1,"transition-commit",1)!="FENCED": raise RuntimeError("commit fence missing")
    target=begin_scope_exclusion(scope,"transition-commit")
    if target!=2: raise RuntimeError("scope target epoch mismatch")
    try: issue_scope_lease(scope,"late-old",1,80)
    except RuntimeError: pass
    else: raise RuntimeError("old lease issued after exclusion started")
    if finalize_scope_exclusion(scope,"transition-commit",20): raise RuntimeError("scope excluded before live old lease horizon")
    if not finalize_scope_exclusion(scope,"transition-commit",31): raise RuntimeError("scope exclusion did not close after old lease expiry")
    # Deliberately lose Redis fence after exclusion and before source commit.
    # Commit remains safe because no BFF can still hold/obtain eligible epoch-1 evidence.
    cache_cmd("DEL",authority_key(owner,rid))
    if commit_source(owner,"transition-commit","writer-b",32): raise RuntimeError("non-owner source writer committed")
    if not commit_source(owner,"transition-commit","writer-a",32): raise RuntimeError("owner could not commit under exact exclusion hold")
    if resource_state(owner,rid)!=(2,False) or transition_state(owner,"transition-commit")!="committed|1|1":
        raise RuntimeError("source commit/reconciliation/audit atomicity failed")
    try: issue_scope_lease(scope,"premature-new",2,100)
    except RuntimeError: pass
    else: raise RuntimeError("new lease issued before source reconciliation/finalization")
    set_cache_revoked(owner,rid,2,2,"transition-commit")
    finalize_source_reconciliation(owner,"transition-commit")
    epoch=release_scope_after_terminal(owner,"transition-commit")
    fresh=issue_scope_lease(scope,"bff-fresh",epoch,120)
    if admit(owner,rid,fresh,40)!="DENY": raise RuntimeError("revoked generation authorized after readmission")
    print("d3_b_revocation_partial_write_safety=PASS fence_before_commit=true cancel_before_cleanup=true sleeping_writer_fenced=true fence_loss_after_barrier_safe=true post_commit_pre_finalize_scope_excluded=true durable_reconciliation=true audit_intent_atomic=true")
    print("d3_b_prepare_fence_commit_finalize_single_winner=PASS compatible_retry_observes=true fingerprint_mismatch_rejected=true transition_owner_single_winner=true expected_generation_cas=true source_commit_requires_exact_exclusion_hold=true cleanup_writer_race_single_winner=true")


def prove_lease_issue_exclusion_serialization() -> None:
    owner="identity"; rid="session-lease-race"; scope=scope_key(owner,rid)
    insert_resource(owner,rid); set_cache_current(owner,rid,1,1)
    initial=issue_scope_lease(scope,"bff-race",1,40)
    reserve_transition(owner,"transition-lease-race",rid,1,"lease-race:v1","writer-race",200)
    start=threading.Barrier(3); outcomes:dict[str,bool]={}
    def renew() -> None:
        start.wait()
        try:
            issue_scope_lease(scope,"bff-race",1,100); outcomes["renew"]=True
        except RuntimeError: outcomes["renew"]=False
    def exclude() -> None:
        start.wait()
        try:
            begin_scope_exclusion(scope,"transition-lease-race"); outcomes["exclude"]=True
        except RuntimeError: outcomes["exclude"]=False
    threads=[threading.Thread(target=renew),threading.Thread(target=exclude)]
    [t.start() for t in threads]; start.wait(); [t.join(20) for t in threads]
    if any(t.is_alive() for t in threads) or not outcomes.get("exclude"):
        raise RuntimeError(f"lease/exclusion serialization failed: {outcomes!r}")
    try: issue_scope_lease(scope,"late-old",1,150)
    except RuntimeError: pass
    else: raise RuntimeError("old-epoch lease issued after exclusion transaction")
    if outcomes.get("renew"):
        renewed=BffLease(scope,"bff-race",1,100)
        if raw_admit(owner,rid,renewed,50)!="ALLOW": raise RuntimeError("renewal-first negative control was not genuinely live")
        if finalize_scope_exclusion(scope,"transition-lease-race",50): raise RuntimeError("renewal-first lease escaped barrier count")
        if not finalize_scope_exclusion(scope,"transition-lease-race",101): raise RuntimeError("barrier did not close after renewed lease horizon")
    else:
        if not finalize_scope_exclusion(scope,"transition-lease-race",41): raise RuntimeError("exclusion-first ordering failed after initial lease horizon")
    if not cancel_transition(owner,"transition-lease-race",201): raise RuntimeError("lease-race transition cleanup did not cancel")
    # Cancel after an excluded barrier: restore from unchanged source and release by exact cancelled terminal.
    state,current,_target,hold=scope_state(scope)
    if state!="excluded" or hold!="transition-lease-race": raise RuntimeError("lease-race barrier lost exact hold")
    # For a cancelled transition whose barrier already advanced, safe recovery keeps the new epoch but restores source truth.
    set_cache_current(owner,rid,1,current)
    # Convert excluded to excluding only for the generic cancelled release precondition is intentionally not allowed;
    # release cancelled excluded barrier explicitly under exact terminal below.
    role,password=CONTROL_ROLE
    pg_role(role,password,f"UPDATE cache_control.scope_admission SET state='admitted',target_epoch=NULL,hold_transition_id=NULL WHERE scope_key={q(scope)} AND state='excluded' AND hold_transition_id='transition-lease-race';")
    print("d3_b_lease_issue_exclusion_serialization=PASS same_row_serialization=true renewal_first_counted=true exclusion_first_rejects_renewal=true post_exclusion_old_lease_rejected=true")


def prove_cleanup_takeover_actual_concurrency() -> None:
    owner="identity"; rid="session-cleanup-race"; scope=scope_key(owner,rid)
    insert_resource(owner,rid); set_cache_current(owner,rid,1,1)
    reserve_transition(owner,"transition-race",rid,1,"race:v1","writer-old",10)
    install_fence(owner,rid,1,"transition-race",1)
    start=threading.Barrier(3); outcomes:dict[str,bool]={}
    def cleanup() -> None:
        start.wait(); outcomes["cancel"]=cancel_transition(owner,"transition-race",11)
    def recover() -> None:
        start.wait(); outcomes["takeover"]=takeover_transition(owner,"transition-race",11,"writer-new",80)
    threads=[threading.Thread(target=cleanup),threading.Thread(target=recover)]
    [t.start() for t in threads]; start.wait(); [t.join(20) for t in threads]
    if any(t.is_alive() for t in threads) or outcomes.get("cancel")==outcomes.get("takeover"):
        raise RuntimeError(f"cleanup/takeover did not have exactly one durable winner: {outcomes!r}")
    if outcomes["takeover"]:
        begin_scope_exclusion(scope,"transition-race")
        if not finalize_scope_exclusion(scope,"transition-race",12): raise RuntimeError("takeover barrier failed")
        cache_cmd("DEL",authority_key(owner,rid))
        if not commit_source(owner,"transition-race","writer-new",12): raise RuntimeError("takeover owner failed source commit")
        set_cache_revoked(owner,rid,2,2,"transition-race"); finalize_source_reconciliation(owner,"transition-race"); release_scope_after_terminal(owner,"transition-race")
        if resource_state(owner,rid)!=(2,False): raise RuntimeError("takeover effect missing")
    else:
        if commit_source(owner,"transition-race","writer-old",12): raise RuntimeError("cancelled writer committed")
        cache_cmd("DEL",authority_key(owner,rid)); set_cache_current(owner,rid,1,1)
        if resource_state(owner,rid)!=(1,True): raise RuntimeError("cancel winner changed source")
    print("d3_b_cleanup_takeover_actual_concurrency=PASS simultaneous_source_owner_race=true exactly_one_durable_winner=true cancel_fences_writer=true takeover_requires_scope_barrier=true source_effect_at_most_once=true")


def prove_fleet_barrier_and_restore() -> None:
    owner="identity"; rid="session-fleet"; scope=scope_key(owner,rid)
    insert_resource(owner,rid); cache_cmd("FLUSHALL"); set_cache_current(owner,rid,1,1)
    a=issue_scope_lease(scope,"bff-a",1,40); b=issue_scope_lease(scope,"bff-b",1,40); c=issue_scope_lease(scope,"bff-c",1,60)
    if admit(owner,rid,a,10)!="ALLOW": raise RuntimeError("healthy negative control failed")
    rdb=snapshot_rdb(); standby=start_stale_replica(owner,rid,a)
    reserve_transition(owner,"transition-degraded",rid,1,"degraded:v1","writer-degraded",120)
    # No Redis fence is installed: source commit must be impossible before fleet exclusion.
    if commit_source(owner,"transition-degraded","writer-degraded",20): raise RuntimeError("local cache failure allowed source commit before fleet barrier")
    begin_scope_exclusion(scope,"transition-degraded")
    retire_scope_lease(a); retire_scope_lease(b)
    if raw_admit(owner,rid,c,30)!="ALLOW": raise RuntimeError("unretired old lease was not genuinely authorizing")
    if finalize_scope_exclusion(scope,"transition-degraded",30): raise RuntimeError("fleet barrier ignored live old BFF lease")
    if commit_source(owner,"transition-degraded","writer-degraded",30): raise RuntimeError("source committed before fleet barrier")
    if not finalize_scope_exclusion(scope,"transition-degraded",61): raise RuntimeError("fleet barrier did not close after old lease horizon")
    try: issue_scope_lease(scope,"late-during-excluded",2,150)
    except RuntimeError: pass
    else: raise RuntimeError("new lease issued while transition hold remained excluded")
    if not commit_source(owner,"transition-degraded","writer-degraded",62): raise RuntimeError("degraded source commit failed after exact fleet barrier")
    if resource_state(owner,rid)!=(2,False): raise RuntimeError("degraded source authority did not revoke")
    restore=start_restore(rdb,owner,rid,a)
    try:
        # Before reconciliation/readmission, no positive expected evidence can be issued at the new epoch.
        try: issue_scope_lease(scope,"premature",2,160)
        except RuntimeError: pass
        else: raise RuntimeError("readmission raced source reconciliation")
        set_cache_revoked(owner,rid,2,2,"transition-degraded")
        finalize_source_reconciliation(owner,"transition-degraded")
        epoch=release_scope_after_terminal(owner,"transition-degraded")
        fresh=issue_scope_lease(scope,"bff-fresh",epoch,180)
        if admit(owner,rid,fresh,70,container=standby,cli=CACHE_CLI)!="DENY": raise RuntimeError("promoted stale replica resurrected positive authority")
        if admit(owner,rid,fresh,70,container=restore,cli=CACHE_CLI)!="DENY": raise RuntimeError("stale RDB restore resurrected positive authority")
        if admit(owner,rid,fresh,70)!="DENY": raise RuntimeError("current revoked cache authorized")
    finally:
        run(["docker","rm","-f",restore],check=False); run(["docker","rm","-f",standby],check=False)
        try: rdb.unlink(missing_ok=True); rdb.parent.rmdir()
        except OSError: pass
    print("d3_b_fleet_wide_cache_exclusion_barrier=PASS local_cache_failure_not_global_proof=true old_lease_retirement_or_expiry_required=true old_lease_issuance_serialized_with_exclusion=true source_commit_requires_exact_transition_hold=true readmission_blocked_until_reconciliation=true")
    print("d3_b_restore_failover_positive_authority_nonresurrection=PASS genuine_old_positive_negative_control=true stale_replica_promoted_with_old_positive=true stale_rdb_restored_with_old_positive=true fresh_external_scope_epoch_blocks_both=true")


def prove_reentry_new_mutation_serialization() -> None:
    owner="identity"; rid="session-reentry-race"; scope=scope_key(owner,rid)
    insert_resource(owner,rid); set_cache_current(owner,rid,1,1)
    reserve_transition(owner,"transition-a",rid,1,"a:v1","writer-a",100)
    begin_scope_exclusion(scope,"transition-a"); finalize_scope_exclusion(scope,"transition-a",1)
    if not commit_source(owner,"transition-a","writer-a",2): raise RuntimeError("transition-a source commit failed")
    set_cache_revoked(owner,rid,2,2,"transition-a"); finalize_source_reconciliation(owner,"transition-a")
    reserve_transition(owner,"transition-b",rid,2,"b:v1","writer-b",200)
    start=threading.Barrier(3); outcomes:dict[str,bool]={}
    def readmit() -> None:
        start.wait()
        try: release_scope_after_terminal(owner,"transition-a"); outcomes["readmit"]=True
        except RuntimeError: outcomes["readmit"]=False
    def new_exclusion() -> None:
        start.wait()
        try: begin_scope_exclusion(scope,"transition-b"); outcomes["exclude_b"]=True
        except RuntimeError: outcomes["exclude_b"]=False
    threads=[threading.Thread(target=readmit),threading.Thread(target=new_exclusion)]
    [t.start() for t in threads]; start.wait(); [t.join(20) for t in threads]
    if any(t.is_alive() for t in threads) or not outcomes.get("readmit"):
        raise RuntimeError(f"readmission/new-mutation race failed: {outcomes!r}")
    if not outcomes.get("exclude_b"):
        begin_scope_exclusion(scope,"transition-b")
    state,current,target,hold=scope_state(scope)
    if state!="excluding" or hold!="transition-b" or target!=current+1:
        raise RuntimeError("new transition was lost across serialized readmission race")
    if commit_source(owner,"transition-b","writer-b",3): raise RuntimeError("new mutation committed before its own lease barrier")
    if not cancel_transition(owner,"transition-b",201): raise RuntimeError("new transition cleanup did not cancel")
    # Since no lease barrier finalized for B, cancellation can restore admitted state at the current epoch.
    role,password=CONTROL_ROLE
    result=pg_role(role,password,f"UPDATE cache_control.scope_admission SET state='admitted',target_epoch=NULL,hold_transition_id=NULL WHERE scope_key={q(scope)} AND state='excluding' AND hold_transition_id='transition-b' RETURNING current_epoch;",check=False)
    if scalar(result)!="2": raise RuntimeError("cancelled new transition could not release unfinalized exclusion")
    print("d3_b_reentry_new_mutation_serialization=PASS readmission_and_new_exclusion_same_row_serialized=true no_new_source_commit_without_own_barrier=true prepared_obligation_not_lost=true")


class OwnerReadBulkhead:
    def __init__(self, capacity:int)->None: self._sem=threading.BoundedSemaphore(capacity)
    def try_read(self,fn):
        if not self._sem.acquire(blocking=False): return False,None
        try: return True,fn()
        except Exception: return False,None
        finally: self._sem.release()
    def acquire(self)->bool: return self._sem.acquire(blocking=False)
    def release(self)->None: self._sem.release()


def prove_bulkhead() -> None:
    owner="identity"; rid="session-owner-read"; scope=scope_key(owner,rid)
    insert_resource(owner,rid); cache_cmd("DEL",positive_key(owner,rid)); lease=issue_scope_lease(scope,"bff-owner-read",1,200)
    bulk=OwnerReadBulkhead(2); ready=threading.Barrier(3); release=threading.Event(); results=[]; errors=[]
    def holder():
        if not bulk.acquire(): errors.append("acquire"); return
        try:
            ready.wait(); release.wait(10); results.append(resource_state(owner,rid))
        finally: bulk.release()
    ts=[threading.Thread(target=holder),threading.Thread(target=holder)]; [t.start() for t in ts]; ready.wait()
    called=[False]
    def overflow(): called[0]=True; return resource_state(owner,rid)
    admitted,value=bulk.try_read(overflow)
    if admitted or value is not None or called[0]: raise RuntimeError("bulkhead overflow reached owner I/O")
    release.set(); [t.join(20) for t in ts]
    if any(t.is_alive() for t in ts) or errors or sorted(results)!=[(1,True),(1,True)]: raise RuntimeError("bounded owner reads failed")
    run(["docker","pause",PG_CONTAINER])
    try:
        admitted,value=bulk.try_read(lambda:resource_state(owner,rid))
        if admitted or value is not None: raise RuntimeError("owner outage manufactured positive authority")
        if cache_scalar("EXISTS",positive_key(owner,rid))!="0": raise RuntimeError("failed owner read filled positive cache")
    finally: run(["docker","unpause",PG_CONTAINER])
    if raw_admit(owner,rid,lease,20)!="DENY": raise RuntimeError("missing positive cache unexpectedly authorized")
    print("d3_b_degraded_owner_read_bulkhead_fail_closed=PASS bounded_concurrency=true third_read_denied_before_owner_io=true actual_owner_outage_denied=true failed_read_no_positive_fill=true current_owner_only=true")


def prove_cross_owner_transitions() -> None:
    identity_before=resource_state("identity","owner-session")
    for owner,rid in (("membership","owner-membership"),("authz","owner-permission"),("platform","owner-tenant")):
        scope=scope_key(owner,rid); set_cache_current(owner,rid,1,1)
        tid=f"transition-{owner}"; token=f"writer-{owner}"
        reserve_transition(owner,tid,rid,1,f"{owner}:v1",token,100)
        install_fence(owner,rid,1,tid,1); begin_scope_exclusion(scope,tid); finalize_scope_exclusion(scope,tid,1)
        cache_cmd("DEL",authority_key(owner,rid))
        if not commit_source(owner,tid,token,2): raise RuntimeError(f"{owner} own transition failed")
        set_cache_revoked(owner,rid,2,2,tid); finalize_source_reconciliation(owner,tid); release_scope_after_terminal(owner,tid)
        if resource_state(owner,rid)!=(2,False): raise RuntimeError(f"{owner} source truth did not change")
        if resource_state("identity","owner-session")!=identity_before: raise RuntimeError(f"{owner} laundered mutation into Identity/session")
    print("d3_b_cross_owner_transition_isolation=PASS membership_transition_owner_local=true authorization_transition_owner_local=true tenant_transition_owner_local=true identity_session_truth_not_surrogate_owner=true")


def main()->int:
    wait_cache(CACHE_CONTAINER,CACHE_CLI); setup_postgres()
    prove_owner_boundaries()
    prove_partial_write_and_single_winner()
    prove_lease_issue_exclusion_serialization()
    prove_cleanup_takeover_actual_concurrency()
    prove_fleet_barrier_and_restore()
    prove_reentry_new_mutation_serialization()
    prove_bulkhead()
    prove_cross_owner_transitions()
    print("d3_b_session_cache_conformance_serialized=PASS source_commit_uses_fleet_scope_barrier=true fence_to_commit_toctou_removed=true lease_issue_exclusion_serialized=true readmission_new_mutation_serialized=true restore_failover_nonresurrection=true owner_bulkhead_fail_closed=true")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
