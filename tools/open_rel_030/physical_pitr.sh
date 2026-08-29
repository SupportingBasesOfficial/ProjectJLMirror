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
      if [[ "$consecutive" -ge 3 ]]; then
        return 0
      fi
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
  local label="$1"
  local expected="$2"
  local actual="$3"
  if [[ "$actual" != "$expected" ]]; then
    printf '%s expected=%q actual=%q\n' "$label" "$expected" "$actual" >&2
    return 1
  fi
  printf '%s=PASS value=%q\n' "$label" "$actual"
}

# ---------------------------------------------------------------------------
# Surviving recovery authority.
#
# Structured grants are authenticated over deterministic self-delimiting facts.
# Signature verification alone is deliberately NOT recovery admission.
# Admission is bound to the authenticated PostgreSQL session principal in the
# surviving authority. The claim function accepts no caller-supplied target ID.
# Same-principal retries are idempotent; another authenticated principal fails.
# The concrete LOGIN/password exchange is C2 laboratory machinery, not a
# production identity/authentication selection.
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
  RETURNS text
  LANGUAGE sql IMMUTABLE STRICT
  SET search_path=pg_catalog
  AS \$\$
    SELECT octet_length(convert_to(p_value,'UTF8'))::text || ':' ||
           encode(convert_to(p_value,'UTF8'),'hex')
  \$\$;

  CREATE OR REPLACE FUNCTION pitr_external_evidence.canonical_grant(
    p_domain text,
    p_boundary_r text,
    p_boundary_f text,
    p_successor_epoch bigint,
    p_placement_version bigint,
    p_required_receipt text,
    p_nonce text
  ) RETURNS text
  LANGUAGE sql IMMUTABLE STRICT
  SET search_path=pg_catalog,pitr_external_evidence
  AS \$\$
    SELECT
      pitr_external_evidence.canonical_field(p_domain) ||
      pitr_external_evidence.canonical_field(p_boundary_r) ||
      pitr_external_evidence.canonical_field(p_boundary_f) ||
      pitr_external_evidence.canonical_field(p_successor_epoch::text) ||
      pitr_external_evidence.canonical_field(p_placement_version::text) ||
      pitr_external_evidence.canonical_field(p_required_receipt) ||
      pitr_external_evidence.canonical_field(p_nonce)
  \$\$;

  CREATE TABLE pitr_external_evidence.authority (
    singleton boolean PRIMARY KEY DEFAULT true CHECK (singleton),
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
    singleton boolean PRIMARY KEY DEFAULT true CHECK (singleton),
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

  CREATE OR REPLACE FUNCTION pitr_external_evidence.verify_grant(
    p_grant_id text,
    p_domain text,
    p_boundary_r text,
    p_boundary_f text,
    p_successor_epoch bigint,
    p_placement_version bigint,
    p_required_receipt text,
    p_nonce text,
    p_attestation text
  ) RETURNS boolean
  LANGUAGE plpgsql STRICT
  SECURITY DEFINER
  SET search_path=pg_catalog,pitr_external_evidence
  AS \$\$
  DECLARE
    v_key text;
    v_grant pitr_external_evidence.recovery_grant%ROWTYPE;
    v_canonical text;
    v_expected text;
  BEGIN
    SELECT * INTO v_grant
      FROM pitr_external_evidence.recovery_grant
     WHERE grant_id=p_grant_id;
    IF NOT FOUND
       OR v_grant.domain IS DISTINCT FROM p_domain
       OR v_grant.boundary_r IS DISTINCT FROM p_boundary_r
       OR v_grant.boundary_f IS DISTINCT FROM p_boundary_f
       OR v_grant.successor_epoch IS DISTINCT FROM p_successor_epoch
       OR v_grant.placement_version IS DISTINCT FROM p_placement_version
       OR v_grant.required_receipt IS DISTINCT FROM p_required_receipt
       OR v_grant.nonce IS DISTINCT FROM p_nonce
       OR v_grant.attestation IS DISTINCT FROM p_attestation THEN
      RETURN false;
    END IF;

    v_canonical := pitr_external_evidence.canonical_grant(
      p_domain,p_boundary_r,p_boundary_f,p_successor_epoch,
      p_placement_version,p_required_receipt,p_nonce
    );
    IF v_grant.canonical_payload IS DISTINCT FROM v_canonical THEN
      RETURN false;
    END IF;

    SELECT key_material INTO STRICT v_key
      FROM pitr_external_evidence.signing_key WHERE singleton;
    v_expected := encode(public.hmac(
      convert_to(v_canonical,'UTF8'),decode(v_key,'hex'),'sha256'),'hex');
    RETURN v_expected = p_attestation;
  END;
  \$\$;

  CREATE OR REPLACE FUNCTION pitr_external_evidence.claim_grant(
    p_grant_id text,
    p_domain text,
    p_boundary_r text,
    p_boundary_f text,
    p_successor_epoch bigint,
    p_placement_version bigint,
    p_required_receipt text,
    p_nonce text,
    p_attestation text
  ) RETURNS boolean
  LANGUAGE plpgsql STRICT
  SECURITY DEFINER
  SET search_path=pg_catalog,pitr_external_evidence
  AS \$\$
  DECLARE
    v_key text;
    v_grant pitr_external_evidence.recovery_grant%ROWTYPE;
    v_canonical text;
    v_expected text;
    v_principal name := session_user;
  BEGIN
    SELECT * INTO v_grant
      FROM pitr_external_evidence.recovery_grant
     WHERE grant_id=p_grant_id
     FOR UPDATE;
    IF NOT FOUND
       OR v_grant.domain IS DISTINCT FROM p_domain
       OR v_grant.boundary_r IS DISTINCT FROM p_boundary_r
       OR v_grant.boundary_f IS DISTINCT FROM p_boundary_f
       OR v_grant.successor_epoch IS DISTINCT FROM p_successor_epoch
       OR v_grant.placement_version IS DISTINCT FROM p_placement_version
       OR v_grant.required_receipt IS DISTINCT FROM p_required_receipt
       OR v_grant.nonce IS DISTINCT FROM p_nonce
       OR v_grant.attestation IS DISTINCT FROM p_attestation THEN
      RETURN false;
    END IF;

    v_canonical := pitr_external_evidence.canonical_grant(
      p_domain,p_boundary_r,p_boundary_f,p_successor_epoch,
      p_placement_version,p_required_receipt,p_nonce
    );
    IF v_grant.canonical_payload IS DISTINCT FROM v_canonical THEN
      RETURN false;
    END IF;

    SELECT key_material INTO STRICT v_key
      FROM pitr_external_evidence.signing_key WHERE singleton;
    v_expected := encode(public.hmac(
      convert_to(v_canonical,'UTF8'),decode(v_key,'hex'),'sha256'),'hex');
    IF v_expected <> p_attestation THEN
      RETURN false;
    END IF;

    IF v_grant.claimed_principal IS NULL THEN
      UPDATE pitr_external_evidence.recovery_grant
         SET claimed_principal=v_principal,
             claimed_at=clock_timestamp()
       WHERE grant_id=p_grant_id;
      RETURN true;
    END IF;

    RETURN v_grant.claimed_principal = v_principal;
  END;
  \$\$;

  CREATE OR REPLACE FUNCTION pitr_external_evidence.verify_claimed_grant(
    p_grant_id text,
    p_domain text,
    p_boundary_r text,
    p_boundary_f text,
    p_successor_epoch bigint,
    p_placement_version bigint,
    p_required_receipt text,
    p_nonce text,
    p_attestation text
  ) RETURNS boolean
  LANGUAGE plpgsql STRICT
  SECURITY DEFINER
  SET search_path=pg_catalog,pitr_external_evidence
  AS \$\$
  DECLARE v_claimed name; v_principal name := session_user;
  BEGIN
    SELECT claimed_principal INTO v_claimed
      FROM pitr_external_evidence.recovery_grant
     WHERE grant_id=p_grant_id;
    IF NOT FOUND OR v_claimed IS DISTINCT FROM v_principal THEN
      RETURN false;
    END IF;
    RETURN pitr_external_evidence.verify_grant(
      p_grant_id,p_domain,p_boundary_r,p_boundary_f,p_successor_epoch,
      p_placement_version,p_required_receipt,p_nonce,p_attestation
    );
  END;
  \$\$;

  REVOKE ALL ON FUNCTION pitr_external_evidence.verify_grant(text,text,text,text,bigint,bigint,text,text,text) FROM PUBLIC;
  REVOKE ALL ON FUNCTION pitr_external_evidence.claim_grant(text,text,text,text,bigint,bigint,text,text,text) FROM PUBLIC;
  REVOKE ALL ON FUNCTION pitr_external_evidence.verify_claimed_grant(text,text,text,text,bigint,bigint,text,text,text) FROM PUBLIC;
  REVOKE ALL ON pitr_external_evidence.recovery_grant FROM PUBLIC;
" >/dev/null

if [[ ${recovery_key+x} == x ]]; then
  echo "controller retained a recovery_key variable" >&2
  exit 1
fi
printf '%s\n' 'physical_pitr_controller_does_not_retain_recovery_signing_key=PASS'

# Prove why the old pipe framing is not a structured authority boundary.
legacy_probe="$(psql_in "$control_container" "
  SELECT (
    ('domain' || '|' || 'R|F' || '|' || 'tail') =
    ('domain|R' || '|' || 'F' || '|' || 'tail')
  )::text || '|' || (
    pitr_external_evidence.canonical_field('domain') ||
    pitr_external_evidence.canonical_field('R|F') ||
    pitr_external_evidence.canonical_field('tail') <>
    pitr_external_evidence.canonical_field('domain|R') ||
    pitr_external_evidence.canonical_field('F') ||
    pitr_external_evidence.canonical_field('tail')
  )::text;
")"
assert_exact "physical_pitr_grant_delimiter_collision_closed" "true|true" "$legacy_probe"

docker run -d --name "$source_container" \
  -e POSTGRES_PASSWORD="$password" \
  -e POSTGRES_DB=jlmirror \
  "$pg_image" \
  postgres \
    -c wal_level=replica \
    -c archive_mode=on \
    -c "archive_command=mkdir -p /tmp/wal_archive && test ! -f /tmp/wal_archive/%f && cp %p /tmp/wal_archive/%f" \
  >/dev/null
wait_tcp "$source_container"

psql_in "$source_container" "
  CREATE TABLE pitr_local_state (
    singleton boolean PRIMARY KEY DEFAULT true CHECK (singleton),
    business_state text NOT NULL,
    poll_epoch bigint NOT NULL,
    poll_generation bigint NOT NULL,
    placement_version bigint NOT NULL,
    reconciled_through_f boolean NOT NULL DEFAULT false,
    external_grant_id text,
    external_grant_fingerprint text,
    external_grant_principal text
  );
  CREATE TABLE pitr_continuity_receipt (receipt_id text PRIMARY KEY);
  INSERT INTO pitr_local_state
    (singleton,business_state,poll_epoch,poll_generation,placement_version,reconciled_through_f)
  VALUES (true,'pre_R',4,9,7,false);
" >/dev/null

docker exec -u postgres -e PGPASSWORD="$password" "$source_container" \
  sh -c 'rm -rf /tmp/basebackup && pg_basebackup -h 127.0.0.1 -U postgres -D /tmp/basebackup -Fp -Xs -P' \
  >/dev/null

psql_in "$source_container" "
  UPDATE pitr_local_state
     SET business_state='state_at_R',poll_epoch=5,poll_generation=10
   WHERE singleton;
" >/dev/null
r_committed="$(psql_in "$source_container" "SELECT business_state||'|'||poll_epoch||'|'||poll_generation FROM pitr_local_state WHERE singleton;")"
assert_exact "physical_pitr_R_transaction_committed" "state_at_R|5|10" "$r_committed"
r_lsn="$(psql_in "$source_container" "SELECT pg_create_restore_point('jlmirror_R');")"

psql_in "$source_container" "
  UPDATE pitr_local_state
     SET business_state='post_R_business_change',poll_generation=11
   WHERE singleton;
  INSERT INTO pitr_continuity_receipt(receipt_id) VALUES ('$required_receipt');
" >/dev/null
f_committed="$(psql_in "$source_container" "SELECT business_state||'|'||poll_generation||'|'||(SELECT count(*) FROM pitr_continuity_receipt) FROM pitr_local_state WHERE singleton;")"
assert_exact "physical_pitr_F_transaction_committed" "post_R_business_change|11|1" "$f_committed"
f_lsn="$(psql_in "$source_container" "SELECT pg_create_restore_point('jlmirror_F');")"
if [[ "$r_lsn" == "$f_lsn" ]]; then
  echo "PITR R and F unexpectedly share the same WAL LSN" >&2
  exit 1
fi
printf 'physical_pitr_restore_points=PASS R=%s F=%s\n' "$r_lsn" "$f_lsn"

# Only after F exists does the surviving authority issue grants.
psql_in "$control_container" "
  WITH facts AS (
    SELECT
      'grant-F-1'::text AS grant_id,
      'open-rel-030-recovery-v1'::text AS domain,
      boundary_r,
      boundary_f,
      expected_successor_epoch AS successor_epoch,
      expected_placement_version AS placement_version,
      required_receipt,
      '$recovery_nonce'::text AS nonce
    FROM pitr_external_evidence.authority WHERE singleton
    UNION ALL
    SELECT
      'grant-F-race'::text,
      'open-rel-030-recovery-v1'::text,
      boundary_r,
      boundary_f,
      expected_successor_epoch,
      expected_placement_version,
      required_receipt,
      '$recovery_race_nonce'::text
    FROM pitr_external_evidence.authority WHERE singleton
  ), canonical AS (
    SELECT f.*,
      pitr_external_evidence.canonical_grant(
        domain,boundary_r,boundary_f,successor_epoch,
        placement_version,required_receipt,nonce
      ) AS payload
    FROM facts f
  )
  INSERT INTO pitr_external_evidence.recovery_grant(
    grant_id,domain,boundary_r,boundary_f,successor_epoch,placement_version,
    required_receipt,nonce,canonical_payload,attestation
  )
  SELECT c.grant_id,c.domain,c.boundary_r,c.boundary_f,c.successor_epoch,
         c.placement_version,c.required_receipt,c.nonce,c.payload,
         encode(public.hmac(convert_to(c.payload,'UTF8'),decode(k.key_material,'hex'),'sha256'),'hex')
    FROM canonical c CROSS JOIN pitr_external_evidence.signing_key k
   WHERE k.singleton;
" >/dev/null

grant_id="$(psql_in "$control_container" "SELECT grant_id FROM pitr_external_evidence.recovery_grant WHERE grant_id='grant-F-1';")"
grant_domain="$(psql_in "$control_container" "SELECT domain FROM pitr_external_evidence.recovery_grant WHERE grant_id='grant-F-1';")"
grant_r="$(psql_in "$control_container" "SELECT boundary_r FROM pitr_external_evidence.recovery_grant WHERE grant_id='grant-F-1';")"
grant_f="$(psql_in "$control_container" "SELECT boundary_f FROM pitr_external_evidence.recovery_grant WHERE grant_id='grant-F-1';")"
grant_epoch="$(psql_in "$control_container" "SELECT successor_epoch FROM pitr_external_evidence.recovery_grant WHERE grant_id='grant-F-1';")"
grant_placement="$(psql_in "$control_container" "SELECT placement_version FROM pitr_external_evidence.recovery_grant WHERE grant_id='grant-F-1';")"
grant_receipt="$(psql_in "$control_container" "SELECT required_receipt FROM pitr_external_evidence.recovery_grant WHERE grant_id='grant-F-1';")"
grant_nonce="$(psql_in "$control_container" "SELECT nonce FROM pitr_external_evidence.recovery_grant WHERE grant_id='grant-F-1';")"
grant_payload="$(psql_in "$control_container" "SELECT canonical_payload FROM pitr_external_evidence.recovery_grant WHERE grant_id='grant-F-1';")"
grant_attestation="$(psql_in "$control_container" "SELECT attestation FROM pitr_external_evidence.recovery_grant WHERE grant_id='grant-F-1';")"
if [[ -z "$grant_attestation" || -z "$grant_payload" ]]; then
  echo "surviving authority failed to issue authenticated structured recovery grant" >&2
  exit 1
fi
assert_exact "physical_pitr_grant_receipt_contains_pipe" "$required_receipt" "$grant_receipt"

docker exec -e PGPASSWORD="$password" "$source_container" \
  psql -X -v ON_ERROR_STOP=1 -U postgres -d jlmirror -Atq -c \
  "SELECT pg_switch_wal(); CHECKPOINT; SELECT pg_switch_wal();" >/dev/null

for _ in $(seq 1 80); do
  archived_count="$(psql_in "$source_container" "SELECT archived_count FROM pg_stat_archiver;")"
  failed_count="$(psql_in "$source_container" "SELECT failed_count FROM pg_stat_archiver;")"
  if [[ "$failed_count" != "0" ]]; then
    echo "PITR WAL archive reported failures: $failed_count" >&2
    exit 1
  fi
  if [[ "$archived_count" -ge 2 ]]; then break; fi
  sleep 0.25
done
if [[ "${archived_count:-0}" -lt 2 ]]; then
  echo "PITR WAL archive did not reach the required boundary" >&2
  exit 1
fi
printf 'physical_pitr_archive=PASS archived_count=%s\n' "$archived_count"

mkdir -p "$tmpdir/base" "$tmpdir/archive"
docker cp "$source_container:/tmp/basebackup/." "$tmpdir/base/"
docker cp "$source_container:/tmp/wal_archive/." "$tmpdir/archive/"
if [[ -z "$(find "$tmpdir/archive" -type f -print -quit)" ]]; then
  echo "PITR archive copy is empty" >&2
  exit 1
fi

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

docker run -d --name "$restored_container" \
  -v "$tmpdir/base:/var/lib/postgresql/data" \
  -v "$tmpdir/archive:/archive:ro" \
  "$pg_image" >/dev/null
wait_tcp "$restored_container"

recovery_flag="$(psql_in "$restored_container" "SELECT pg_is_in_recovery()::text;")"
assert_exact "physical_pitr_promoted_at_R" "false" "$recovery_flag"

restored_state="$(psql_in "$restored_container" "
  SELECT business_state||'|'||poll_epoch||'|'||poll_generation||'|'||
         placement_version||'|'||reconciled_through_f::text||'|'||
         (SELECT count(*) FROM pitr_continuity_receipt)||'|'||coalesce(external_grant_id,'')
  FROM pitr_local_state WHERE singleton;
")"
assert_exact "physical_pitr_exact_R_state" "state_at_R|5|10|7|false|0|" "$restored_state"

# ---------------------------------------------------------------------------
# Post-R authenticated recovery principals.
#
# The credentials are created only after the restore has reached R, so they are
# not present in the restored database image. The concrete PostgreSQL LOGIN
# mechanism is evidence-only; the invariant is that external authority derives
# claim identity from authenticated session state rather than caller data.
# ---------------------------------------------------------------------------
primary_password="$(openssl rand -hex 24)"
rival_password="$(openssl rand -hex 24)"
race_a_password="$(openssl rand -hex 24)"
race_b_password="$(openssl rand -hex 24)"
control_ip="$(docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' "$control_container")"
if [[ -z "$control_ip" ]]; then
  echo "cannot resolve surviving authority container IP" >&2
  exit 1
fi

psql_in "$control_container" "
  CREATE ROLE $primary_role LOGIN PASSWORD '$primary_password';
  CREATE ROLE $rival_role LOGIN PASSWORD '$rival_password';
  CREATE ROLE $race_a_role LOGIN PASSWORD '$race_a_password';
  CREATE ROLE $race_b_role LOGIN PASSWORD '$race_b_password';
  GRANT USAGE ON SCHEMA pitr_external_evidence TO $primary_role,$rival_role,$race_a_role,$race_b_role;
  GRANT EXECUTE ON FUNCTION pitr_external_evidence.claim_grant(text,text,text,text,bigint,bigint,text,text,text)
    TO $primary_role,$rival_role,$race_a_role,$race_b_role;
  GRANT EXECUTE ON FUNCTION pitr_external_evidence.verify_claimed_grant(text,text,text,text,bigint,bigint,text,text,text)
    TO $primary_role,$rival_role,$race_a_role,$race_b_role;
" >/dev/null

psql_control_as() {
  local user="$1"
  local pass="$2"
  local sql="$3"
  docker exec -e PGPASSWORD="$pass" "$restored_container" \
    psql -X -v ON_ERROR_STOP=1 -h "$control_ip" -U "$user" -d jlmirror -Atq -c "$sql"
}

# Prove the claim API cannot accept caller-supplied target identity.
claim_args="$(psql_in "$control_container" "SELECT pg_get_function_identity_arguments('pitr_external_evidence.claim_grant(text,text,text,text,bigint,bigint,text,text,text)'::regprocedure);")"
if [[ "$claim_args" == *"target"* || "$claim_args" == *"principal"* ]]; then
  echo "recovery claim API still accepts caller-supplied target/principal identity: $claim_args" >&2
  exit 1
fi
printf '%s\n' 'physical_pitr_recovery_claim_identity_from_authenticated_session=PASS'

# Password authentication is part of the bounded evidence path. Knowing the
# winner role name while presenting the rival credential must not authenticate.
set +e
docker exec -e PGPASSWORD="$rival_password" "$restored_container" \
  psql -X -v ON_ERROR_STOP=1 -h "$control_ip" -U "$primary_role" -d jlmirror -Atq -c 'SELECT 1;' \
  >"$tmpdir/spoof.out" 2>"$tmpdir/spoof.err"
spoof_rc=$?
set -e
if [[ "$spoof_rc" -eq 0 ]]; then
  echo "rival credential authenticated as winning recovery principal" >&2
  exit 1
fi
printf '%s\n' 'physical_pitr_recovery_principal_spoof_rejected=PASS'

# Two independently authenticated principals race the same dedicated grant.
race_sql="SELECT pitr_external_evidence.claim_grant(g.grant_id,g.domain,g.boundary_r,g.boundary_f,g.successor_epoch,g.placement_version,g.required_receipt,g.nonce,g.attestation)::text FROM pitr_external_evidence.recovery_grant g WHERE g.grant_id='grant-F-race';"
( psql_control_as "$race_a_role" "$race_a_password" "$race_sql" >"$tmpdir/race-a.out" ) &
race_pid_a=$!
( psql_control_as "$race_b_role" "$race_b_password" "$race_sql" >"$tmpdir/race-b.out" ) &
race_pid_b=$!
wait "$race_pid_a"
wait "$race_pid_b"
race_a="$(cat "$tmpdir/race-a.out")"
race_b="$(cat "$tmpdir/race-b.out")"
if [[ "$race_a|$race_b" != "true|false" && "$race_a|$race_b" != "false|true" ]]; then
  echo "authenticated recovery claim race did not produce exactly one winner: $race_a|$race_b" >&2
  exit 1
fi
if [[ "$race_a" == "true" ]]; then
  race_winner_role="$race_a_role"
  race_winner_password="$race_a_password"
  race_loser_role="$race_b_role"
  race_loser_password="$race_b_password"
else
  race_winner_role="$race_b_role"
  race_winner_password="$race_b_password"
  race_loser_role="$race_a_role"
  race_loser_password="$race_a_password"
fi
race_winner_retry="$(psql_control_as "$race_winner_role" "$race_winner_password" "$race_sql")"
race_loser_retry="$(psql_control_as "$race_loser_role" "$race_loser_password" "$race_sql")"
assert_exact "physical_pitr_recovery_claim_winner_retry" "true" "$race_winner_retry"
assert_exact "physical_pitr_recovery_claim_loser_rejected" "false" "$race_loser_retry"
race_claimed_principal="$(psql_in "$control_container" "SELECT claimed_principal::text FROM pitr_external_evidence.recovery_grant WHERE grant_id='grant-F-race';")"
assert_exact "physical_pitr_recovery_claim_single_winner_race" "$race_winner_role" "$race_claimed_principal"

external_epoch="$(psql_in "$control_container" "SELECT expected_successor_epoch FROM pitr_external_evidence.authority WHERE singleton;")"
external_placement="$(psql_in "$control_container" "SELECT expected_placement_version FROM pitr_external_evidence.authority WHERE singleton;")"
external_receipt="$(psql_in "$control_container" "SELECT required_receipt FROM pitr_external_evidence.authority WHERE singleton;")"
assert_exact "physical_pitr_external_F_epoch_survives" "6" "$external_epoch"
assert_exact "physical_pitr_external_F_placement_survives" "8" "$external_placement"
assert_exact "physical_pitr_external_F_receipt_survives" "$required_receipt" "$external_receipt"

# A restore can reproduce a local receipt string, but that is not admission.
psql_in "$restored_container" "
  INSERT INTO pitr_continuity_receipt(receipt_id)
  VALUES ('$required_receipt') ON CONFLICT DO NOTHING;
" >/dev/null
local_self_mint="$(psql_in "$restored_container" "
  SELECT (reconciled_through_f AND external_grant_id IS NOT NULL
          AND external_grant_fingerprint IS NOT NULL
          AND external_grant_principal IS NOT NULL)::text
  FROM pitr_local_state WHERE singleton;
")"
assert_exact "physical_pitr_local_self_mint_cannot_admit" "false" "$local_self_mint"

# Tampering structured grant facts must fail and must not claim the grant.
tampered_claim_sql="SELECT pitr_external_evidence.claim_grant('$grant_id','$grant_domain','$grant_r','$grant_f',$grant_epoch,$grant_placement,'effect|after-r-tampered','$grant_nonce','$grant_attestation')::text;"
tampered_claim="$(psql_control_as "$primary_role" "$primary_password" "$tampered_claim_sql")"
assert_exact "physical_pitr_tampered_grant_cannot_claim" "false" "$tampered_claim"
unclaimed_after_tamper="$(psql_in "$control_container" "SELECT (claimed_principal IS NULL)::text FROM pitr_external_evidence.recovery_grant WHERE grant_id='$grant_id';")"
assert_exact "physical_pitr_tamper_leaves_grant_unclaimed" "true" "$unclaimed_after_tamper"

# Integrity verification by surviving authority is necessary but not admission.
verified="$(psql_in "$control_container" "
  SELECT pitr_external_evidence.verify_grant(
    '$grant_id','$grant_domain','$grant_r','$grant_f',$grant_epoch,$grant_placement,
    '$grant_receipt','$grant_nonce','$grant_attestation'
  )::text;
")"
assert_exact "physical_pitr_external_grant_verified" "true" "$verified"
assert_exact "physical_pitr_grant_domain" "open-rel-030-recovery-v1" "$grant_domain"
assert_exact "physical_pitr_grant_R" "R" "$grant_r"
assert_exact "physical_pitr_grant_F" "F" "$grant_f"
assert_exact "physical_pitr_grant_epoch" "6" "$grant_epoch"
assert_exact "physical_pitr_grant_placement" "8" "$grant_placement"
assert_exact "physical_pitr_grant_receipt" "$required_receipt" "$grant_receipt"

# The actual restored authority claims through its authenticated session. Retry
# by the same authenticated principal converges; a different principal fails.
claim_sql="SELECT pitr_external_evidence.claim_grant('$grant_id','$grant_domain','$grant_r','$grant_f',$grant_epoch,$grant_placement,'$grant_receipt','$grant_nonce','$grant_attestation')::text;"
claimed="$(psql_control_as "$primary_role" "$primary_password" "$claim_sql")"
assert_exact "physical_pitr_recovery_grant_claimed" "true" "$claimed"
claim_retry="$(psql_control_as "$primary_role" "$primary_password" "$claim_sql")"
assert_exact "physical_pitr_recovery_grant_same_principal_retry" "true" "$claim_retry"
rival_claim="$(psql_control_as "$rival_role" "$rival_password" "$claim_sql")"
assert_exact "physical_pitr_recovery_grant_other_principal_rejected" "false" "$rival_claim"
claimed_principal="$(psql_in "$control_container" "SELECT claimed_principal::text FROM pitr_external_evidence.recovery_grant WHERE grant_id='$grant_id';")"
assert_exact "physical_pitr_recovery_grant_authenticated_principal_binding" "$primary_role" "$claimed_principal"

grant_fingerprint="$(printf '%s' "$grant_payload" | sha256sum | awk '{print $1}')"

# Apply only facts from the authenticated, single-winner surviving grant after
# the restored authority's external session has won the claim.
psql_in "$restored_container" "
  UPDATE pitr_local_state
     SET poll_epoch=$grant_epoch,
         poll_generation=1,
         placement_version=$grant_placement,
         reconciled_through_f=true,
         external_grant_id='$grant_id',
         external_grant_fingerprint='$grant_fingerprint',
         external_grant_principal='$primary_role'
   WHERE singleton;
" >/dev/null

after_state="$(psql_in "$restored_container" "
  SELECT business_state||'|'||poll_epoch||'|'||poll_generation||'|'||
         placement_version||'|'||reconciled_through_f::text||'|'||
         (SELECT count(*) FROM pitr_continuity_receipt)||'|'||external_grant_id
  FROM pitr_local_state WHERE singleton;
")"
assert_exact "physical_pitr_reconciled_without_business_replay" \
  "state_at_R|6|1|8|true|1|grant-F-1" "$after_state"

local_ready="$(psql_in "$restored_container" "
  SELECT (
    reconciled_through_f
    AND poll_epoch=$grant_epoch
    AND placement_version=$grant_placement
    AND external_grant_id='$grant_id'
    AND external_grant_fingerprint='$grant_fingerprint'
    AND external_grant_principal='$primary_role'
    AND EXISTS (SELECT 1 FROM pitr_continuity_receipt WHERE receipt_id='$grant_receipt')
  )::text FROM pitr_local_state WHERE singleton;
")"
verify_claimed_sql="SELECT pitr_external_evidence.verify_claimed_grant('$grant_id','$grant_domain','$grant_r','$grant_f',$grant_epoch,$grant_placement,'$grant_receipt','$grant_nonce','$grant_attestation')::text;"
external_ready="$(psql_control_as "$primary_role" "$primary_password" "$verify_claimed_sql")"
rival_ready="$(psql_control_as "$rival_role" "$rival_password" "$verify_claimed_sql")"
assert_exact "physical_pitr_local_reconciled_state" "true" "$local_ready"
assert_exact "physical_pitr_external_authority_still_verifies" "true" "$external_ready"
assert_exact "physical_pitr_duplicate_restored_authority_not_admitted" "false" "$rival_ready"
if [[ "$local_ready" != "true" || "$external_ready" != "true" || "$rival_ready" != "false" ]]; then
  echo "physical PITR admission lacks unique authenticated surviving external authority" >&2
  exit 1
fi

# Clear transient evidence credentials from the controller process. Production
# identity/credential provisioning is deliberately outside this C2 selection.
unset primary_password rival_password race_a_password race_b_password
printf '%s\n' 'physical_pitr_recovery_single_winner_authenticated_principal=PASS'
printf '%s\n' 'physical_pitr_post_reconcile_admission=PASS authority=surviving_external_authenticated_single_winner_principal'
printf '%s\n' 'physical_pitr_rf_reconciliation=PASS'
