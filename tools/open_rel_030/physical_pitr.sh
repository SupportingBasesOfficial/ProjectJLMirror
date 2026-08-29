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
clone_container="jlmirror-open-rel-030-pitr-restored-clone"
tmpdir="$(mktemp -d)"
recovery_nonce="$(openssl rand -hex 16)"
recovery_race_nonce="$(openssl rand -hex 16)"
required_receipt='effect|after-r'

primary_role="pitr_restore_primary"
rival_role="pitr_restore_rival"
race_a_role="pitr_restore_race_a"
race_b_role="pitr_restore_race_b"

cleanup() {
  docker rm -f "$source_container" "$restored_container" "$clone_container" >/dev/null 2>&1 || true
  sudo rm -rf "$tmpdir" >/dev/null 2>&1 || true
}
trap cleanup EXIT
cleanup

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
# Grant facts and HMAC are resolved internally. Recovery callers provide only a
# grant id plus a post-R instance capability proof. The winner identity is the
# conjunction of authenticated session_user + instance_id + fingerprint(secret).
# A copied database credential alone therefore cannot impersonate a retry from
# the already-admitted restored instance.
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

  CREATE OR REPLACE FUNCTION pitr_external_evidence.instance_fingerprint(p_secret text)
  RETURNS text LANGUAGE sql IMMUTABLE STRICT SET search_path=pg_catalog,public
  AS \$\$
    SELECT encode(public.digest(
      convert_to('open-rel-030-recovery-instance-v1:' || p_secret,'UTF8'),
      'sha256'
    ),'hex')
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
    claimed_instance_id uuid,
    claimed_instance_fingerprint text,
    claimed_at timestamptz,
    CHECK (
      (claimed_principal IS NULL AND claimed_instance_id IS NULL
       AND claimed_instance_fingerprint IS NULL AND claimed_at IS NULL)
      OR
      (claimed_principal IS NOT NULL AND claimed_instance_id IS NOT NULL
       AND claimed_instance_fingerprint IS NOT NULL AND claimed_at IS NOT NULL)
    )
  );
  REVOKE ALL ON pitr_external_evidence.recovery_grant FROM PUBLIC;

  CREATE OR REPLACE FUNCTION pitr_external_evidence.stored_grant_is_valid(p_grant_id text)
  RETURNS boolean LANGUAGE plpgsql STRICT SECURITY DEFINER
  SET search_path=pg_catalog,pitr_external_evidence,public
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

  CREATE OR REPLACE FUNCTION pitr_external_evidence.claim_grant(
    p_grant_id text,p_instance_id uuid,p_instance_secret text
  ) RETURNS boolean LANGUAGE plpgsql STRICT SECURITY DEFINER
  SET search_path=pg_catalog,pitr_external_evidence,public
  AS \$\$
  DECLARE
    v_grant pitr_external_evidence.recovery_grant%ROWTYPE;
    v_principal name := session_user;
    v_fingerprint text;
  BEGIN
    SELECT * INTO v_grant FROM pitr_external_evidence.recovery_grant
     WHERE grant_id=p_grant_id FOR UPDATE;
    IF NOT FOUND OR NOT pitr_external_evidence.stored_grant_is_valid(p_grant_id) THEN
      RETURN false;
    END IF;

    v_fingerprint := pitr_external_evidence.instance_fingerprint(p_instance_secret);
    IF v_grant.claimed_principal IS NULL THEN
      UPDATE pitr_external_evidence.recovery_grant
         SET claimed_principal=v_principal,
             claimed_instance_id=p_instance_id,
             claimed_instance_fingerprint=v_fingerprint,
             claimed_at=clock_timestamp()
       WHERE grant_id=p_grant_id;
      RETURN true;
    END IF;

    RETURN v_grant.claimed_principal = v_principal
       AND v_grant.claimed_instance_id = p_instance_id
       AND v_grant.claimed_instance_fingerprint = v_fingerprint;
  END;
  \$\$;

  CREATE OR REPLACE FUNCTION pitr_external_evidence.verify_claimed_grant(
    p_grant_id text,p_instance_id uuid,p_instance_secret text
  ) RETURNS boolean LANGUAGE plpgsql STRICT SECURITY DEFINER
  SET search_path=pg_catalog,pitr_external_evidence,public
  AS \$\$
  DECLARE
    v_grant pitr_external_evidence.recovery_grant%ROWTYPE;
    v_principal name := session_user;
    v_fingerprint text;
  BEGIN
    SELECT * INTO v_grant FROM pitr_external_evidence.recovery_grant
     WHERE grant_id=p_grant_id;
    IF NOT FOUND THEN RETURN false; END IF;
    v_fingerprint := pitr_external_evidence.instance_fingerprint(p_instance_secret);
    IF v_grant.claimed_principal IS DISTINCT FROM v_principal
       OR v_grant.claimed_instance_id IS DISTINCT FROM p_instance_id
       OR v_grant.claimed_instance_fingerprint IS DISTINCT FROM v_fingerprint THEN
      RETURN false;
    END IF;
    RETURN pitr_external_evidence.stored_grant_is_valid(p_grant_id);
  END;
  \$\$;

  REVOKE ALL ON FUNCTION pitr_external_evidence.stored_grant_is_valid(text) FROM PUBLIC;
  REVOKE ALL ON FUNCTION pitr_external_evidence.instance_fingerprint(text) FROM PUBLIC;
  REVOKE ALL ON FUNCTION pitr_external_evidence.claim_grant(text,uuid,text) FROM PUBLIC;
  REVOKE ALL ON FUNCTION pitr_external_evidence.verify_claimed_grant(text,uuid,text) FROM PUBLIC;
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
    external_grant_principal text,
    external_grant_instance_id uuid,
    external_grant_instance_fingerprint text
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

mkdir -p "$tmpdir/base" "$tmpdir/clone_base" "$tmpdir/archive"
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
sudo cp -a "$tmpdir/base/." "$tmpdir/clone_base/"
sudo chown -R "$pg_uid:$pg_gid" "$tmpdir/base" "$tmpdir/clone_base" "$tmpdir/archive"

docker run -d --name "$restored_container" -v "$tmpdir/base:/var/lib/postgresql/data" -v "$tmpdir/archive:/archive:ro" "$pg_image" >/dev/null
docker run -d --name "$clone_container" -v "$tmpdir/clone_base:/var/lib/postgresql/data" -v "$tmpdir/archive:/archive:ro" "$pg_image" >/dev/null
wait_tcp "$restored_container"
wait_tcp "$clone_container"

assert_exact "physical_pitr_promoted_at_R" "false" "$(psql_in "$restored_container" "SELECT pg_is_in_recovery()::text;")"
assert_exact "physical_pitr_clone_promoted_at_R" "false" "$(psql_in "$clone_container" "SELECT pg_is_in_recovery()::text;")"
restored_state="$(psql_in "$restored_container" "SELECT business_state||'|'||poll_epoch||'|'||poll_generation||'|'||placement_version||'|'||reconciled_through_f::text||'|'||(SELECT count(*) FROM pitr_continuity_receipt)||'|'||coalesce(external_grant_id,'') FROM pitr_local_state WHERE singleton;")"
clone_state="$(psql_in "$clone_container" "SELECT business_state||'|'||poll_epoch||'|'||poll_generation||'|'||placement_version||'|'||reconciled_through_f::text||'|'||(SELECT count(*) FROM pitr_continuity_receipt)||'|'||coalesce(external_grant_id,'') FROM pitr_local_state WHERE singleton;")"
assert_exact "physical_pitr_exact_R_state" "state_at_R|5|10|7|false|0|" "$restored_state"
assert_exact "physical_pitr_clone_exact_R_state" "state_at_R|5|10|7|false|0|" "$clone_state"

# ---------------------------------------------------------------------------
# Post-R instance capabilities.
# Each physical restore generates its own id+secret inside local protected state.
# The secret never leaves through the shell; local SECURITY DEFINER helpers read
# it and present proof to the surviving authority. Both clones deliberately use
# the exact same external PostgreSQL role/password to falsify credential reuse.
# ---------------------------------------------------------------------------
for c in "$restored_container" "$clone_container"; do
  psql_in "$c" "
    CREATE EXTENSION IF NOT EXISTS pgcrypto;
    CREATE EXTENSION IF NOT EXISTS dblink;
    CREATE TABLE pitr_recovery_instance(
      singleton boolean PRIMARY KEY DEFAULT true CHECK(singleton),
      instance_id uuid NOT NULL,
      instance_secret text NOT NULL,
      created_at timestamptz NOT NULL DEFAULT clock_timestamp()
    );
    INSERT INTO pitr_recovery_instance(singleton,instance_id,instance_secret)
    SELECT true,gen_random_uuid(),encode(gen_random_bytes(32),'hex');
    REVOKE ALL ON pitr_recovery_instance FROM PUBLIC;

    CREATE OR REPLACE FUNCTION pitr_local_claim_external(
      p_conn text,p_grant_id text
    ) RETURNS boolean LANGUAGE plpgsql STRICT SECURITY DEFINER
    SET search_path=pg_catalog,public
    AS \$\$
    DECLARE v_id uuid; v_secret text; v_result boolean;
    BEGIN
      SELECT instance_id,instance_secret INTO STRICT v_id,v_secret
        FROM public.pitr_recovery_instance WHERE singleton;
      SELECT ok INTO v_result
        FROM public.dblink(
          p_conn,
          format('SELECT pitr_external_evidence.claim_grant(%L,%L::uuid,%L)::text',
                 p_grant_id,v_id::text,v_secret)
        ) AS r(ok boolean);
      RETURN coalesce(v_result,false);
    EXCEPTION WHEN OTHERS THEN
      RETURN false;
    END;
    \$\$;

    CREATE OR REPLACE FUNCTION pitr_local_verify_external(
      p_conn text,p_grant_id text
    ) RETURNS boolean LANGUAGE plpgsql STRICT SECURITY DEFINER
    SET search_path=pg_catalog,public
    AS \$\$
    DECLARE v_id uuid; v_secret text; v_result boolean;
    BEGIN
      SELECT instance_id,instance_secret INTO STRICT v_id,v_secret
        FROM public.pitr_recovery_instance WHERE singleton;
      SELECT ok INTO v_result
        FROM public.dblink(
          p_conn,
          format('SELECT pitr_external_evidence.verify_claimed_grant(%L,%L::uuid,%L)::text',
                 p_grant_id,v_id::text,v_secret)
        ) AS r(ok boolean);
      RETURN coalesce(v_result,false);
    EXCEPTION WHEN OTHERS THEN
      RETURN false;
    END;
    \$\$;
    REVOKE ALL ON FUNCTION pitr_local_claim_external(text,text) FROM PUBLIC;
    REVOKE ALL ON FUNCTION pitr_local_verify_external(text,text) FROM PUBLIC;
  " >/dev/null
done

primary_instance_id="$(psql_in "$restored_container" "SELECT instance_id::text FROM pitr_recovery_instance WHERE singleton;")"
clone_instance_id="$(psql_in "$clone_container" "SELECT instance_id::text FROM pitr_recovery_instance WHERE singleton;")"
primary_instance_fp="$(psql_in "$restored_container" "SELECT encode(public.digest(convert_to(instance_secret,'UTF8'),'sha256'),'hex') FROM pitr_recovery_instance WHERE singleton;")"
clone_instance_fp="$(psql_in "$clone_container" "SELECT encode(public.digest(convert_to(instance_secret,'UTF8'),'sha256'),'hex') FROM pitr_recovery_instance WHERE singleton;")"
[[ "$primary_instance_id" != "$clone_instance_id" && "$primary_instance_fp" != "$clone_instance_fp" ]] || {
  echo "physical restore clones did not generate distinct post-R instance capabilities" >&2; exit 1;
}
printf '%s\n' 'physical_pitr_recovery_instance_capability_generated_post_R=PASS'
printf '%s\n' 'physical_pitr_recovery_clone_capability_distinct=PASS'

# Concrete external DB credentials are evidence-only. Primary and physical clone
# intentionally share exactly the same winning role/password.
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
  GRANT EXECUTE ON FUNCTION pitr_external_evidence.claim_grant(text,uuid,text)
    TO $primary_role,$rival_role,$race_a_role,$race_b_role;
  GRANT EXECUTE ON FUNCTION pitr_external_evidence.verify_claimed_grant(text,uuid,text)
    TO $primary_role,$rival_role,$race_a_role,$race_b_role;
" >/dev/null

conn_string() {
  local user="$1" pass="$2"
  printf 'hostaddr=%s port=5432 dbname=jlmirror user=%s password=%s connect_timeout=2' \
    "$control_ip" "$user" "$pass"
}
primary_conn="$(conn_string "$primary_role" "$primary_password")"
rival_conn="$(conn_string "$rival_role" "$rival_password")"
race_a_conn="$(conn_string "$race_a_role" "$race_a_password")"
race_b_conn="$(conn_string "$race_b_role" "$race_b_password")"

# The external API accepts grant id plus capability proof, but never caller-
# supplied principal or signed grant facts. Principal authority is session_user.
claim_args="$(psql_in "$control_container" "SELECT pg_get_function_identity_arguments('pitr_external_evidence.claim_grant(text,uuid,text)'::regprocedure);")"
assert_exact "physical_pitr_recovery_claim_api_grant_plus_instance_proof" "p_grant_id text, p_instance_id uuid, p_instance_secret text" "$claim_args"
printf '%s\n' 'physical_pitr_recovery_claim_identity_from_authenticated_session=PASS'

# Restricted external principal cannot read grant state directly.
set +e
docker exec -e PGPASSWORD="$primary_password" "$restored_container" \
  psql -X -v ON_ERROR_STOP=1 -h "$control_ip" -U "$primary_role" -d jlmirror -Atq \
  -c "SELECT grant_id FROM pitr_external_evidence.recovery_grant;" >"$tmpdir/direct.out" 2>"$tmpdir/direct.err"
direct_rc=$?
set -e
[[ "$direct_rc" -ne 0 ]] || { echo "restore principal can read recovery_grant directly" >&2; exit 1; }
printf '%s\n' 'physical_pitr_recovery_principal_no_direct_grant_read=PASS'

# Knowing the role name but not its external credential still cannot authenticate.
set +e
docker exec -e PGPASSWORD="$rival_password" "$restored_container" \
  psql -X -v ON_ERROR_STOP=1 -h "$control_ip" -U "$primary_role" -d jlmirror -Atq -c 'SELECT 1;' \
  >"$tmpdir/spoof.out" 2>"$tmpdir/spoof.err"
spoof_rc=$?
set -e
[[ "$spoof_rc" -ne 0 ]] || { echo "rival credential authenticated as primary" >&2; exit 1; }
printf '%s\n' 'physical_pitr_recovery_principal_spoof_rejected=PASS'

# Invalid stored attestation cannot be claimed by a valid restored instance.
assert_exact "physical_pitr_tampered_grant_cannot_claim" "false" \
  "$(psql_in "$restored_container" "SELECT pitr_local_claim_external('$primary_conn','grant-F-tampered')::text;")"
assert_exact "physical_pitr_tamper_leaves_grant_unclaimed" "true" \
  "$(psql_in "$control_container" "SELECT (claimed_principal IS NULL)::text FROM pitr_external_evidence.recovery_grant WHERE grant_id='grant-F-tampered';")"

# Existing single-winner race is retained with independent authenticated roles
# and independent instance capabilities.
race_a_id="$(psql_in "$control_container" "SELECT gen_random_uuid()::text;")"
race_b_id="$(psql_in "$control_container" "SELECT gen_random_uuid()::text;")"
race_a_secret="$(openssl rand -hex 32)"
race_b_secret="$(openssl rand -hex 32)"
psql_control_direct() {
  local user="$1" pass="$2" sql="$3"
  docker exec -e PGPASSWORD="$pass" "$restored_container" \
    psql -X -v ON_ERROR_STOP=1 -h "$control_ip" -U "$user" -d jlmirror -Atq -c "$sql"
}
race_sql_a="SELECT pitr_external_evidence.claim_grant('grant-F-race','$race_a_id'::uuid,'$race_a_secret')::text;"
race_sql_b="SELECT pitr_external_evidence.claim_grant('grant-F-race','$race_b_id'::uuid,'$race_b_secret')::text;"
( psql_control_direct "$race_a_role" "$race_a_password" "$race_sql_a" >"$tmpdir/race-a.out" ) & race_pid_a=$!
( psql_control_direct "$race_b_role" "$race_b_password" "$race_sql_b" >"$tmpdir/race-b.out" ) & race_pid_b=$!
wait "$race_pid_a"; wait "$race_pid_b"
race_a="$(cat "$tmpdir/race-a.out")"; race_b="$(cat "$tmpdir/race-b.out")"
if [[ "$race_a|$race_b" != "true|false" && "$race_a|$race_b" != "false|true" ]]; then
  echo "authenticated recovery race not single-winner: $race_a|$race_b" >&2; exit 1
fi
if [[ "$race_a" == true ]]; then
  race_winner_role="$race_a_role"; race_winner_password="$race_a_password"; race_winner_sql="$race_sql_a"
  race_loser_role="$race_b_role"; race_loser_password="$race_b_password"; race_loser_sql="$race_sql_b"
else
  race_winner_role="$race_b_role"; race_winner_password="$race_b_password"; race_winner_sql="$race_sql_b"
  race_loser_role="$race_a_role"; race_loser_password="$race_a_password"; race_loser_sql="$race_sql_a"
fi
assert_exact "physical_pitr_recovery_claim_winner_retry" "true" "$(psql_control_direct "$race_winner_role" "$race_winner_password" "$race_winner_sql")"
assert_exact "physical_pitr_recovery_claim_loser_rejected" "false" "$(psql_control_direct "$race_loser_role" "$race_loser_password" "$race_loser_sql")"
printf '%s\n' 'physical_pitr_recovery_claim_single_winner_race=PASS'

# Local receipt recreation remains insufficient before external claim.
for c in "$restored_container" "$clone_container"; do
  psql_in "$c" "INSERT INTO pitr_continuity_receipt(receipt_id) VALUES('$required_receipt') ON CONFLICT DO NOTHING;" >/dev/null
done
local_self_mint="$(psql_in "$restored_container" "SELECT (reconciled_through_f AND external_grant_id IS NOT NULL AND external_grant_fingerprint IS NOT NULL)::text FROM pitr_local_state WHERE singleton;")"
assert_exact "physical_pitr_local_self_mint_cannot_admit" "false" "$local_self_mint"

# Primary restore claims. A physical clone from the same R backup uses the exact
# same external role/password but a different post-R local capability and must
# therefore be rejected as a distinct restored authority, not accepted as retry.
assert_exact "physical_pitr_recovery_grant_claimed" "true" \
  "$(psql_in "$restored_container" "SELECT pitr_local_claim_external('$primary_conn','grant-F-1')::text;")"
assert_exact "physical_pitr_recovery_grant_same_instance_retry" "true" \
  "$(psql_in "$restored_container" "SELECT pitr_local_claim_external('$primary_conn','grant-F-1')::text;")"
assert_exact "physical_pitr_recovery_same_principal_clone_rejected" "false" \
  "$(psql_in "$clone_container" "SELECT pitr_local_claim_external('$primary_conn','grant-F-1')::text;")"
assert_exact "physical_pitr_recovery_other_principal_rejected" "false" \
  "$(psql_in "$clone_container" "SELECT pitr_local_claim_external('$rival_conn','grant-F-1')::text;")"

claimed_binding="$(psql_in "$control_container" "SELECT claimed_principal::text||'|'||claimed_instance_id::text||'|'||claimed_instance_fingerprint FROM pitr_external_evidence.recovery_grant WHERE grant_id='grant-F-1';")"
claimed_principal="${claimed_binding%%|*}"
remaining="${claimed_binding#*|}"
claimed_instance_id="${remaining%%|*}"
claimed_instance_fingerprint="${remaining#*|}"
assert_exact "physical_pitr_recovery_grant_authenticated_principal_binding" "$primary_role" "$claimed_principal"
assert_exact "physical_pitr_recovery_grant_instance_id_binding" "$primary_instance_id" "$claimed_instance_id"
[[ -n "$claimed_instance_fingerprint" ]] || { echo "missing claimed instance fingerprint" >&2; exit 1; }
printf '%s\n' 'physical_pitr_recovery_instance_fingerprint_binding=PASS'

# Apply externally authorized successor facts only to the winning physical restore.
grant_fingerprint="$(printf '%s' "$grant_payload" | sha256sum | awk '{print $1}')"
psql_in "$restored_container" "
  UPDATE pitr_local_state SET poll_epoch=$grant_epoch,poll_generation=1,
    placement_version=$grant_placement,reconciled_through_f=true,
    external_grant_id='grant-F-1',external_grant_fingerprint='$grant_fingerprint',
    external_grant_principal='$primary_role',
    external_grant_instance_id='$primary_instance_id'::uuid,
    external_grant_instance_fingerprint='$claimed_instance_fingerprint'
  WHERE singleton;
" >/dev/null

after_state="$(psql_in "$restored_container" "SELECT business_state||'|'||poll_epoch||'|'||poll_generation||'|'||placement_version||'|'||reconciled_through_f::text||'|'||(SELECT count(*) FROM pitr_continuity_receipt)||'|'||external_grant_id FROM pitr_local_state WHERE singleton;")"
assert_exact "physical_pitr_reconciled_without_business_replay" "state_at_R|6|1|8|true|1|grant-F-1" "$after_state"

local_ready="$(psql_in "$restored_container" "SELECT (reconciled_through_f AND poll_epoch=$grant_epoch AND placement_version=$grant_placement AND external_grant_id='grant-F-1' AND external_grant_fingerprint='$grant_fingerprint' AND external_grant_principal='$primary_role' AND external_grant_instance_id='$primary_instance_id'::uuid AND external_grant_instance_fingerprint='$claimed_instance_fingerprint' AND EXISTS(SELECT 1 FROM pitr_continuity_receipt WHERE receipt_id='$grant_receipt'))::text FROM pitr_local_state WHERE singleton;")"
external_ready="$(psql_in "$restored_container" "SELECT pitr_local_verify_external('$primary_conn','grant-F-1')::text;")"
clone_ready="$(psql_in "$clone_container" "SELECT pitr_local_verify_external('$primary_conn','grant-F-1')::text;")"
assert_exact "physical_pitr_local_reconciled_state" "true" "$local_ready"
assert_exact "physical_pitr_external_authority_still_verifies" "true" "$external_ready"
assert_exact "physical_pitr_duplicate_restored_authority_not_admitted" "false" "$clone_ready"
if [[ "$local_ready" != true || "$external_ready" != true || "$clone_ready" != false ]]; then
  echo "PITR admission lacks unique post-R instance-capability authority" >&2; exit 1
fi

unset primary_password rival_password race_a_password race_b_password race_a_secret race_b_secret
printf '%s\n' 'physical_pitr_recovery_single_winner_instance_capability=PASS'
printf '%s\n' 'physical_pitr_post_reconcile_admission=PASS authority=surviving_external_authenticated_single_winner_instance_capability'
printf '%s\n' 'physical_pitr_rf_reconciliation=PASS'
