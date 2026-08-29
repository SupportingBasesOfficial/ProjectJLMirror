#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 2 ]]; then
  echo "usage: physical_pitr.sh <external-control-container> <postgres-image>" >&2
  exit 2
fi

control_container="$1"
pg_image="$2"
password="evidence"
source_container="jlmirror-open-rel-030-pitr-source"
restored_container="jlmirror-open-rel-030-pitr-restored"
tmpdir="$(mktemp -d)"
recovery_nonce="$(openssl rand -hex 16)"
recovery_race_nonce="$(openssl rand -hex 16)"
required_receipt='effect|after-r'

primary_role="pitr_restore_primary"
rival_role="pitr_restore_rival"
race_a_role="pitr_restore_race_a"
race_b_role="pitr_restore_race_b"

cleanup() {
  docker rm -f "$source_container" "$restored_container" >/dev/null 2>&1 || true
  sudo rm -rf "$tmpdir" >/dev/null 2>&1 || true
}
trap cleanup EXIT

cleanup_containers() {
  docker rm -f "$source_container" "$restored_container" >/dev/null 2>&1 || true
}
cleanup_containers

wait_tcp() {
  local container="$1"
  local consecutive=0
  for _ in $(seq 1 160); do
    if docker exec -e PGPASSWORD="$password" "$container" \
      pg_isready -h 127.0.0.1 -U postgres -d jlmirror >/dev/null 2>&1; then
      consecutive=$((consecutive + 1))
      if [[ "$consecutive" -ge 3 ]]; then return 0; fi
    else
      consecutive=0
    fi
    sleep 0.25
  done
  echo "PITR database TCP path did not become ready: $container" >&2
  docker logs "$container" >&2 || true
  return 1
}

psql_in() {
  local container="$1"
  local sql="$2"
  docker exec -e PGPASSWORD="$password" "$container" \
    psql -X -v ON_ERROR_STOP=1 -U postgres -d jlmirror -Atq -c "$sql"
}

assert_exact() {
  local label="$1" expected="$2" actual="$3"
  if [[ "$actual" != "$expected" ]]; then
    printf '%s expected=%q actual=%q\n' "$label" "$expected" "$actual" >&2
    return 1
  fi
  printf '%s=PASS value=%q\n' "$label" "$actual"
}

# ---------------------------------------------------------------------------
# Surviving recovery authority.
#
# Grant integrity and claim identity are both resolved inside the surviving
# authority. Target callers can present only grant_id. They cannot read grant
# facts, supply a target identity, or supply a purported attestation. The claim
# winner is the authenticated session_user. Same-principal retries converge;
# another authenticated principal fails.
# ---------------------------------------------------------------------------
psql_in "$control_container" "
  CREATE EXTENSION IF NOT EXISTS pgcrypto;
  DROP SCHEMA IF EXISTS pitr_external_evidence CASCADE;
  DROP ROLE IF EXISTS $primary_role;
  DROP ROLE IF EXISTS $rival_role;
  DROP ROLE IF EXISTS $race_a_role;
  DROP ROLE IF EXISTS $race_b_role;
  CREATE SCHEMA pitr_external_evidence;

  CREATE OR REPLACE FUNCTION pitr_external_evidence.canonical_field(p_value text)
  RETURNS text LANGUAGE sql IMMUTABLE STRICT SET search_path=pg_catalog
  AS \$\$
    SELECT octet_length(convert_to(p_value,'UTF8'))::text || ':' ||
           encode(convert_to(p_value,'UTF8'),'hex')
  \$\$;

  CREATE OR REPLACE FUNCTION pitr_external_evidence.canonical_grant(
    p_domain text,p_boundary_r text,p_boundary_f text,p_successor_epoch bigint,
    p_placement_version bigint,p_required_receipt text,p_nonce text
  ) RETURNS text LANGUAGE sql IMMUTABLE STRICT
  SET search_path=pg_catalog,pitr_external_evidence
  AS \$\$
    SELECT pitr_external_evidence.canonical_field(p_domain) ||
           pitr_external_evidence.canonical_field(p_boundary_r) ||
           pitr_external_evidence.canonical_field(p_boundary_f) ||
           pitr_external_evidence.canonical_field(p_successor_epoch::text) ||
           pitr_external_evidence.canonical_field(p_placement_version::text) ||
           pitr_external_evidence.canonical_field(p_required_receipt) ||
           pitr_external_evidence.canonical_field(p_nonce)
  \$\$;

  CREATE TABLE pitr_external_evidence.authority (
    singleton boolean PRIMARY KEY DEFAULT true CHECK(singleton),
    boundary_r text NOT NULL,
    boundary_f text NOT NULL,
    expected_successor_epoch bigint NOT NULL,
    expected_placement_version bigint NOT NULL,
    required_receipt text NOT NULL
  );
  INSERT INTO pitr_external_evidence.authority
    (singleton,boundary_r,boundary_f,expected_successor_epoch,expected_placement_version,required_receipt)
  VALUES (true,'R','F',6,8,'$required_receipt');

  CREATE TABLE pitr_external_evidence.signing_key (
    singleton boolean PRIMARY KEY DEFAULT true CHECK(singleton),
    key_material text NOT NULL
  );
  INSERT INTO pitr_external_evidence.signing_key(singleton,key_material)
  SELECT true,encode(gen_random_bytes(32),'hex');
  REVOKE ALL ON pitr_external_evidence.signing_key FROM PUBLIC;

  CREATE TABLE pitr_external_evidence.recovery_grant (
    grant_id text PRIMARY KEY,
    domain text NOT NULL,
    boundary_r text NOT NULL,
    boundary_f text NOT NULL,
    successor_epoch bigint NOT NULL,
    placement_version bigint NOT NULL,
    required_receipt text NOT NULL,
    nonce text NOT NULL,
    canonical_payload text NOT NULL,
    attestation text NOT NULL,
    issued_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    claimed_principal name,
    claimed_at timestamptz,
    CHECK ((claimed_principal IS NULL) = (claimed_at IS NULL))
  );
  REVOKE ALL ON pitr_external_evidence.recovery_grant FROM PUBLIC;

  CREATE OR REPLACE FUNCTION pitr_external_evidence.stored_grant_is_valid(p_grant_id text)
  RETURNS boolean LANGUAGE plpgsql STRICT SECURITY DEFINER
  SET search_path=pg_catalog,pitr_external_evidence
  AS \$\$
  DECLARE
    v_key text;
    v_grant pitr_external_evidence.recovery_grant%ROWTYPE;
    v_canonical text;
    v_expected text;
  BEGIN
    SELECT * INTO v_grant FROM pitr_external_evidence.recovery_grant
     WHERE grant_id=p_grant_id;
    IF NOT FOUND THEN RETURN false; END IF;
    v_canonical := pitr_external_evidence.canonical_grant(
      v_grant.domain,v_grant.boundary_r,v_grant.boundary_f,
      v_grant.successor_epoch,v_grant.placement_version,
      v_grant.required_receipt,v_grant.nonce
    );
    IF v_grant.canonical_payload IS DISTINCT FROM v_canonical THEN RETURN false; END IF;
    SELECT key_material INTO STRICT v_key
      FROM pitr_external_evidence.signing_key WHERE singleton;
    v_expected := encode(public.hmac(
      convert_to(v_canonical,'UTF8'),decode(v_key,'hex'),'sha256'),'hex');
    RETURN v_expected = v_grant.attestation;
  END;
  \$\$;

  CREATE OR REPLACE FUNCTION pitr_external_evidence.claim_grant(p_grant_id text)
  RETURNS boolean LANGUAGE plpgsql STRICT SECURITY DEFINER
  SET search_path=pg_catalog,pitr_external_evidence
  AS \$\$
  DECLARE
    v_key text;
    v_grant pitr_external_evidence.recovery_grant%ROWTYPE;
    v_canonical text;
    v_expected text;
    v_principal name := session_user;
  BEGIN
    SELECT * INTO v_grant FROM pitr_external_evidence.recovery_grant
     WHERE grant_id=p_grant_id FOR UPDATE;
    IF NOT FOUND THEN RETURN false; END IF;

    v_canonical := pitr_external_evidence.canonical_grant(
      v_grant.domain,v_grant.boundary_r,v_grant.boundary_f,
      v_grant.successor_epoch,v_grant.placement_version,
      v_grant.required_receipt,v_grant.nonce
    );
    IF v_grant.canonical_payload IS DISTINCT FROM v_canonical THEN RETURN false; END IF;
    SELECT key_material INTO STRICT v_key
      FROM pitr_external_evidence.signing_key WHERE singleton;
    v_expected := encode(public.hmac(
      convert_to(v_canonical,'UTF8'),decode(v_key,'hex'),'sha256'),'hex');
    IF v_expected <> v_grant.attestation THEN RETURN false; END IF;

    IF v_grant.claimed_principal IS NULL THEN
      UPDATE pitr_external_evidence.recovery_grant
         SET claimed_principal=v_principal,claimed_at=clock_timestamp()
       WHERE grant_id=p_grant_id;
      RETURN true;
    END IF;
    RETURN v_grant.claimed_principal = v_principal;
  END;
  \$\$;

  CREATE OR REPLACE FUNCTION pitr_external_evidence.verify_claimed_grant(p_grant_id text)
  RETURNS boolean LANGUAGE plpgsql STRICT SECURITY DEFINER
  SET search_path=pg_catalog,pitr_external_evidence
  AS \$\$
  DECLARE v_claimed name; v_principal name := session_user;
  BEGIN
    SELECT claimed_principal INTO v_claimed
      FROM pitr_external_evidence.recovery_grant WHERE grant_id=p_grant_id;
    IF NOT FOUND OR v_claimed IS DISTINCT FROM v_principal THEN RETURN false; END IF;
    RETURN pitr_external_evidence.stored_grant_is_valid(p_grant_id);
  END;
  \$\$;

  REVOKE ALL ON FUNCTION pitr_external_evidence.stored_grant_is_valid(text) FROM PUBLIC;
  REVOKE ALL ON FUNCTION pitr_external_evidence.claim_grant(text) FROM PUBLIC;
  REVOKE ALL ON FUNCTION pitr_external_evidence.verify_claimed_grant(text) FROM PUBLIC;
" >/dev/null

if [[ ${recovery_key+x} == x ]]; then
  echo "controller retained a recovery_key variable" >&2
  exit 1
fi
printf '%s\n' 'physical_pitr_controller_does_not_retain_recovery_signing_key=PASS'

legacy_probe="$(psql_in "$control_container" "
  SELECT (('domain'||'|'||'R|F'||'|'||'tail')=('domain|R'||'|'||'F'||'|'||'tail'))::text || '|' ||
         (pitr_external_evidence.canonical_field('domain')||
          pitr_external_evidence.canonical_field('R|F')||
          pitr_external_evidence.canonical_field('tail') <>
          pitr_external_evidence.canonical_field('domain|R')||
          pitr_external_evidence.canonical_field('F')||
          pitr_external_evidence.canonical_field('tail'))::text;
")"
assert_exact "physical_pitr_grant_delimiter_collision_closed" "true|true" "$legacy_probe"

# ---------------------------------------------------------------------------
# Build a physical R backup and create a later F boundary.
# ---------------------------------------------------------------------------
docker run -d --name "$source_container" \
  -e POSTGRES_PASSWORD="$password" -e POSTGRES_DB=jlmirror "$pg_image" \
  postgres -c wal_level=replica -c archive_mode=on \
  -c "archive_command=mkdir -p /tmp/wal_archive && test ! -f /tmp/wal_archive/%f && cp %p /tmp/wal_archive/%f" >/dev/null
wait_tcp "$source_container"

psql_in "$source_container" "
  CREATE TABLE pitr_local_state (
    singleton boolean PRIMARY KEY DEFAULT true CHECK(singleton),
    business_state text NOT NULL,
    poll_epoch bigint NOT NULL,
    poll_generation bigint NOT NULL,
    placement_version bigint NOT NULL,
    reconciled_through_f boolean NOT NULL DEFAULT false,
    external_grant_id text,
    external_grant_fingerprint text,
    external_grant_principal text
  );
  CREATE TABLE pitr_continuity_receipt(receipt_id text PRIMARY KEY);
  INSERT INTO pitr_local_state(singleton,business_state,poll_epoch,poll_generation,placement_version,reconciled_through_f)
  VALUES(true,'pre_R',4,9,7,false);
" >/dev/null

docker exec -u postgres -e PGPASSWORD="$password" "$source_container" \
  sh -c 'rm -rf /tmp/basebackup && pg_basebackup -h 127.0.0.1 -U postgres -D /tmp/basebackup -Fp -Xs -P' >/dev/null

psql_in "$source_container" "UPDATE pitr_local_state SET business_state='state_at_R',poll_epoch=5,poll_generation=10 WHERE singleton;" >/dev/null
r_committed="$(psql_in "$source_container" "SELECT business_state||'|'||poll_epoch||'|'||poll_generation FROM pitr_local_state WHERE singleton;")"
assert_exact "physical_pitr_R_transaction_committed" "state_at_R|5|10" "$r_committed"
r_lsn="$(psql_in "$source_container" "SELECT pg_create_restore_point('jlmirror_R');")"

psql_in "$source_container" "
  UPDATE pitr_local_state SET business_state='post_R_business_change',poll_generation=11 WHERE singleton;
  INSERT INTO pitr_continuity_receipt(receipt_id) VALUES('$required_receipt');
" >/dev/null
f_committed="$(psql_in "$source_container" "SELECT business_state||'|'||poll_generation||'|'||(SELECT count(*) FROM pitr_continuity_receipt) FROM pitr_local_state WHERE singleton;")"
assert_exact "physical_pitr_F_transaction_committed" "post_R_business_change|11|1" "$f_committed"
f_lsn="$(psql_in "$source_container" "SELECT pg_create_restore_point('jlmirror_F');")"
if [[ "$r_lsn" == "$f_lsn" ]]; then echo "PITR R and F share LSN" >&2; exit 1; fi
printf 'physical_pitr_restore_points=PASS R=%s F=%s\n' "$r_lsn" "$f_lsn"

# Issue real, race and deliberately invalid grants only after F.
psql_in "$control_container" "
  WITH facts(grant_id,domain,boundary_r,boundary_f,successor_epoch,placement_version,required_receipt,nonce) AS (
    SELECT 'grant-F-1','open-rel-030-recovery-v1',boundary_r,boundary_f,expected_successor_epoch,expected_placement_version,required_receipt,'$recovery_nonce'
      FROM pitr_external_evidence.authority WHERE singleton
    UNION ALL
    SELECT 'grant-F-race','open-rel-030-recovery-v1',boundary_r,boundary_f,expected_successor_epoch,expected_placement_version,required_receipt,'$recovery_race_nonce'
      FROM pitr_external_evidence.authority WHERE singleton
  ), c AS (
    SELECT f.*,pitr_external_evidence.canonical_grant(domain,boundary_r,boundary_f,successor_epoch,placement_version,required_receipt,nonce) payload
      FROM facts f
  )
  INSERT INTO pitr_external_evidence.recovery_grant(grant_id,domain,boundary_r,boundary_f,successor_epoch,placement_version,required_receipt,nonce,canonical_payload,attestation)
  SELECT c.grant_id,c.domain,c.boundary_r,c.boundary_f,c.successor_epoch,c.placement_version,c.required_receipt,c.nonce,c.payload,
         encode(public.hmac(convert_to(c.payload,'UTF8'),decode(k.key_material,'hex'),'sha256'),'hex')
    FROM c CROSS JOIN pitr_external_evidence.signing_key k WHERE k.singleton;

  INSERT INTO pitr_external_evidence.recovery_grant(grant_id,domain,boundary_r,boundary_f,successor_epoch,placement_version,required_receipt,nonce,canonical_payload,attestation)
  SELECT 'grant-F-tampered',domain,boundary_r,boundary_f,successor_epoch,placement_version,required_receipt,
         nonce||'-tampered',
         pitr_external_evidence.canonical_grant(domain,boundary_r,boundary_f,successor_epoch,placement_version,required_receipt,nonce||'-tampered'),
         repeat('0',64)
    FROM pitr_external_evidence.recovery_grant WHERE grant_id='grant-F-1';
" >/dev/null

# Admin-only facts used after successful claim to apply the successor state.
grant_payload="$(psql_in "$control_container" "SELECT canonical_payload FROM pitr_external_evidence.recovery_grant WHERE grant_id='grant-F-1';")"
grant_epoch="$(psql_in "$control_container" "SELECT successor_epoch FROM pitr_external_evidence.recovery_grant WHERE grant_id='grant-F-1';")"
grant_placement="$(psql_in "$control_container" "SELECT placement_version FROM pitr_external_evidence.recovery_grant WHERE grant_id='grant-F-1';")"
grant_receipt="$(psql_in "$control_container" "SELECT required_receipt FROM pitr_external_evidence.recovery_grant WHERE grant_id='grant-F-1';")"
assert_exact "physical_pitr_grant_receipt_contains_pipe" "$required_receipt" "$grant_receipt"

# Complete WAL archiving for R/F restore.
docker exec -e PGPASSWORD="$password" "$source_container" psql -X -v ON_ERROR_STOP=1 -U postgres -d jlmirror -Atq -c "SELECT pg_switch_wal(); CHECKPOINT; SELECT pg_switch_wal();" >/dev/null
for _ in $(seq 1 80); do
  archived_count="$(psql_in "$source_container" "SELECT archived_count FROM pg_stat_archiver;")"
  failed_count="$(psql_in "$source_container" "SELECT failed_count FROM pg_stat_archiver;")"
  [[ "$failed_count" == "0" ]] || { echo "PITR archive failures=$failed_count" >&2; exit 1; }
  [[ "$archived_count" -ge 2 ]] && break
  sleep 0.25
done
[[ "${archived_count:-0}" -ge 2 ]] || { echo "PITR archive incomplete" >&2; exit 1; }
printf 'physical_pitr_archive=PASS archived_count=%s\n' "$archived_count"

mkdir -p "$tmpdir/base" "$tmpdir/archive"
docker cp "$source_container:/tmp/basebackup/." "$tmpdir/base/"
docker cp "$source_container:/tmp/wal_archive/." "$tmpdir/archive/"
[[ -n "$(find "$tmpdir/archive" -type f -print -quit)" ]] || { echo "PITR archive copy empty" >&2; exit 1; }
docker stop "$source_container" >/dev/null
pg_uid="$(docker run --rm --entrypoint sh "$pg_image" -c 'id -u postgres')"
pg_gid="$(docker run --rm --entrypoint sh "$pg_image" -c 'id -g postgres')"
sudo tee -a "$tmpdir/base/postgresql.auto.conf" >/dev/null <<'EOF'
restore_command = 'cp /archive/%f %p'
recovery_target_name = 'jlmirror_R'
recovery_target_action = 'promote'
recovery_target_timeline = 'current'
EOF
sudo touch "$tmpdir/base/recovery.signal"
sudo chown -R "$pg_uid:$pg_gid" "$tmpdir/base" "$tmpdir/archive"
docker run -d --name "$restored_container" -v "$tmpdir/base:/var/lib/postgresql/data" -v "$tmpdir/archive:/archive:ro" "$pg_image" >/dev/null
wait_tcp "$restored_container"

assert_exact "physical_pitr_promoted_at_R" "false" "$(psql_in "$restored_container" "SELECT pg_is_in_recovery()::text;")"
restored_state="$(psql_in "$restored_container" "SELECT business_state||'|'||poll_epoch||'|'||poll_generation||'|'||placement_version||'|'||reconciled_through_f::text||'|'||(SELECT count(*) FROM pitr_continuity_receipt)||'|'||coalesce(external_grant_id,'') FROM pitr_local_state WHERE singleton;")"
assert_exact "physical_pitr_exact_R_state" "state_at_R|5|10|7|false|0|" "$restored_state"

# ---------------------------------------------------------------------------
# Post-R authenticated principals. These concrete credentials are evidence-only.
# Claim identity comes from session_user, never from a function argument.
# ---------------------------------------------------------------------------
primary_password="$(openssl rand -hex 24)"
rival_password="$(openssl rand -hex 24)"
race_a_password="$(openssl rand -hex 24)"
race_b_password="$(openssl rand -hex 24)"
control_ip="$(docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' "$control_container")"
[[ -n "$control_ip" ]] || { echo "cannot resolve control IP" >&2; exit 1; }

psql_in "$control_container" "
  CREATE ROLE $primary_role LOGIN PASSWORD '$primary_password';
  CREATE ROLE $rival_role LOGIN PASSWORD '$rival_password';
  CREATE ROLE $race_a_role LOGIN PASSWORD '$race_a_password';
  CREATE ROLE $race_b_role LOGIN PASSWORD '$race_b_password';
  GRANT USAGE ON SCHEMA pitr_external_evidence TO $primary_role,$rival_role,$race_a_role,$race_b_role;
  GRANT EXECUTE ON FUNCTION pitr_external_evidence.claim_grant(text) TO $primary_role,$rival_role,$race_a_role,$race_b_role;
  GRANT EXECUTE ON FUNCTION pitr_external_evidence.verify_claimed_grant(text) TO $primary_role,$rival_role,$race_a_role,$race_b_role;
" >/dev/null

psql_control_as() {
  local user="$1" pass="$2" sql="$3"
  docker exec -e PGPASSWORD="$pass" "$restored_container" \
    psql -X -v ON_ERROR_STOP=1 -h "$control_ip" -U "$user" -d jlmirror -Atq -c "$sql"
}

claim_args="$(psql_in "$control_container" "SELECT pg_get_function_identity_arguments('pitr_external_evidence.claim_grant(text)'::regprocedure);")"
assert_exact "physical_pitr_recovery_claim_api_id_only" "p_grant_id text" "$claim_args"
printf '%s\n' 'physical_pitr_recovery_claim_identity_from_authenticated_session=PASS'

# Restricted callers have no direct grant table read.
set +e
psql_control_as "$primary_role" "$primary_password" "SELECT grant_id FROM pitr_external_evidence.recovery_grant;" >"$tmpdir/direct.out" 2>"$tmpdir/direct.err"
direct_rc=$?
set -e
[[ "$direct_rc" -ne 0 ]] || { echo "restore principal can read recovery_grant directly" >&2; exit 1; }
printf '%s\n' 'physical_pitr_recovery_principal_no_direct_grant_read=PASS'

# Knowing the winner role name with the rival credential cannot authenticate.
set +e
docker exec -e PGPASSWORD="$rival_password" "$restored_container" \
  psql -X -v ON_ERROR_STOP=1 -h "$control_ip" -U "$primary_role" -d jlmirror -Atq -c 'SELECT 1;' >"$tmpdir/spoof.out" 2>"$tmpdir/spoof.err"
spoof_rc=$?
set -e
[[ "$spoof_rc" -ne 0 ]] || { echo "rival credential authenticated as primary" >&2; exit 1; }
printf '%s\n' 'physical_pitr_recovery_principal_spoof_rejected=PASS'

# Invalid stored attestation cannot be claimed even by an authenticated principal.
assert_exact "physical_pitr_tampered_grant_cannot_claim" "false" "$(psql_control_as "$primary_role" "$primary_password" "SELECT pitr_external_evidence.claim_grant('grant-F-tampered')::text;")"
assert_exact "physical_pitr_tamper_leaves_grant_unclaimed" "true" "$(psql_in "$control_container" "SELECT (claimed_principal IS NULL)::text FROM pitr_external_evidence.recovery_grant WHERE grant_id='grant-F-tampered';")"

# Two independent authenticated principals race the same grant: exactly one wins.
race_sql="SELECT pitr_external_evidence.claim_grant('grant-F-race')::text;"
( psql_control_as "$race_a_role" "$race_a_password" "$race_sql" >"$tmpdir/race-a.out" ) & race_pid_a=$!
( psql_control_as "$race_b_role" "$race_b_password" "$race_sql" >"$tmpdir/race-b.out" ) & race_pid_b=$!
wait "$race_pid_a"; wait "$race_pid_b"
race_a="$(cat "$tmpdir/race-a.out")"; race_b="$(cat "$tmpdir/race-b.out")"
if [[ "$race_a|$race_b" != "true|false" && "$race_a|$race_b" != "false|true" ]]; then
  echo "authenticated recovery race not single-winner: $race_a|$race_b" >&2; exit 1
fi
if [[ "$race_a" == "true" ]]; then
  race_winner_role="$race_a_role"; race_winner_password="$race_a_password"
  race_loser_role="$race_b_role"; race_loser_password="$race_b_password"
else
  race_winner_role="$race_b_role"; race_winner_password="$race_b_password"
  race_loser_role="$race_a_role"; race_loser_password="$race_a_password"
fi
assert_exact "physical_pitr_recovery_claim_winner_retry" "true" "$(psql_control_as "$race_winner_role" "$race_winner_password" "$race_sql")"
assert_exact "physical_pitr_recovery_claim_loser_rejected" "false" "$(psql_control_as "$race_loser_role" "$race_loser_password" "$race_sql")"
race_claimed_principal="$(psql_in "$control_container" "SELECT claimed_principal::text FROM pitr_external_evidence.recovery_grant WHERE grant_id='grant-F-race';")"
assert_exact "physical_pitr_recovery_claim_single_winner_race" "$race_winner_role" "$race_claimed_principal"

# Local receipt recreation remains insufficient.
psql_in "$restored_container" "INSERT INTO pitr_continuity_receipt(receipt_id) VALUES('$required_receipt') ON CONFLICT DO NOTHING;" >/dev/null
local_self_mint="$(psql_in "$restored_container" "SELECT (reconciled_through_f AND external_grant_id IS NOT NULL AND external_grant_fingerprint IS NOT NULL AND external_grant_principal IS NOT NULL)::text FROM pitr_local_state WHERE singleton;")"
assert_exact "physical_pitr_local_self_mint_cannot_admit" "false" "$local_self_mint"

# The actual restore principal claims by ID only; retry converges, rival fails.
claim_sql="SELECT pitr_external_evidence.claim_grant('grant-F-1')::text;"
assert_exact "physical_pitr_recovery_grant_claimed" "true" "$(psql_control_as "$primary_role" "$primary_password" "$claim_sql")"
assert_exact "physical_pitr_recovery_grant_same_principal_retry" "true" "$(psql_control_as "$primary_role" "$primary_password" "$claim_sql")"
assert_exact "physical_pitr_recovery_grant_other_principal_rejected" "false" "$(psql_control_as "$rival_role" "$rival_password" "$claim_sql")"
claimed_principal="$(psql_in "$control_container" "SELECT claimed_principal::text FROM pitr_external_evidence.recovery_grant WHERE grant_id='grant-F-1';")"
assert_exact "physical_pitr_recovery_grant_authenticated_principal_binding" "$primary_role" "$claimed_principal"

# Apply externally authorized successor facts without replaying post-R business state.
grant_fingerprint="$(printf '%s' "$grant_payload" | sha256sum | awk '{print $1}')"
psql_in "$restored_container" "
  UPDATE pitr_local_state SET poll_epoch=$grant_epoch,poll_generation=1,
    placement_version=$grant_placement,reconciled_through_f=true,
    external_grant_id='grant-F-1',external_grant_fingerprint='$grant_fingerprint',
    external_grant_principal='$primary_role' WHERE singleton;
" >/dev/null

after_state="$(psql_in "$restored_container" "SELECT business_state||'|'||poll_epoch||'|'||poll_generation||'|'||placement_version||'|'||reconciled_through_f::text||'|'||(SELECT count(*) FROM pitr_continuity_receipt)||'|'||external_grant_id FROM pitr_local_state WHERE singleton;")"
assert_exact "physical_pitr_reconciled_without_business_replay" "state_at_R|6|1|8|true|1|grant-F-1" "$after_state"

local_ready="$(psql_in "$restored_container" "SELECT (reconciled_through_f AND poll_epoch=$grant_epoch AND placement_version=$grant_placement AND external_grant_id='grant-F-1' AND external_grant_fingerprint='$grant_fingerprint' AND external_grant_principal='$primary_role' AND EXISTS(SELECT 1 FROM pitr_continuity_receipt WHERE receipt_id='$grant_receipt'))::text FROM pitr_local_state WHERE singleton;")"
verify_sql="SELECT pitr_external_evidence.verify_claimed_grant('grant-F-1')::text;"
external_ready="$(psql_control_as "$primary_role" "$primary_password" "$verify_sql")"
rival_ready="$(psql_control_as "$rival_role" "$rival_password" "$verify_sql")"
assert_exact "physical_pitr_local_reconciled_state" "true" "$local_ready"
assert_exact "physical_pitr_external_authority_still_verifies" "true" "$external_ready"
assert_exact "physical_pitr_duplicate_restored_authority_not_admitted" "false" "$rival_ready"
if [[ "$local_ready" != true || "$external_ready" != true || "$rival_ready" != false ]]; then
  echo "PITR admission lacks unique authenticated surviving authority" >&2; exit 1
fi

unset primary_password rival_password race_a_password race_b_password
printf '%s\n' 'physical_pitr_recovery_single_winner_authenticated_principal=PASS'
printf '%s\n' 'physical_pitr_post_reconcile_admission=PASS authority=surviving_external_authenticated_single_winner_principal'
printf '%s\n' 'physical_pitr_rf_reconciliation=PASS'
