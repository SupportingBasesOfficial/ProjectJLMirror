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
recovery_key="$(openssl rand -hex 32)"
recovery_nonce="$(openssl rand -hex 16)"

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
# Surviving authority. The HMAC key exists only in the external control plane;
# it is never copied to source/basebackup/restored PostgreSQL. A restore can
# therefore not self-mint the grant that fences re-admission after PITR.
# ---------------------------------------------------------------------------
psql_in "$control_container" "
  CREATE EXTENSION IF NOT EXISTS pgcrypto;
  DROP SCHEMA IF EXISTS pitr_external_evidence CASCADE;
  CREATE SCHEMA pitr_external_evidence;

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
  VALUES (true,'R','F',6,8,'effect-after-r');

  CREATE TABLE pitr_external_evidence.signing_key (
    singleton boolean PRIMARY KEY DEFAULT true CHECK (singleton),
    key_material text NOT NULL
  );
  INSERT INTO pitr_external_evidence.signing_key(singleton,key_material)
  VALUES (true,'$recovery_key');
  REVOKE ALL ON pitr_external_evidence.signing_key FROM PUBLIC;

  CREATE TABLE pitr_external_evidence.recovery_grant (
    grant_id text PRIMARY KEY,
    payload text NOT NULL,
    attestation text NOT NULL,
    issued_at timestamptz NOT NULL DEFAULT clock_timestamp()
  );

  CREATE OR REPLACE FUNCTION pitr_external_evidence.verify_grant(
    p_grant_id text,
    p_payload text,
    p_attestation text
  ) RETURNS boolean
  LANGUAGE plpgsql
  SECURITY DEFINER
  SET search_path = pg_catalog, pitr_external_evidence
  AS \$\$
  DECLARE
    v_key text;
    v_grant pitr_external_evidence.recovery_grant%ROWTYPE;
    v_expected text;
  BEGIN
    SELECT * INTO v_grant
      FROM pitr_external_evidence.recovery_grant
     WHERE grant_id=p_grant_id;
    IF NOT FOUND OR v_grant.payload IS DISTINCT FROM p_payload
       OR v_grant.attestation IS DISTINCT FROM p_attestation THEN
      RETURN false;
    END IF;
    SELECT key_material INTO STRICT v_key
      FROM pitr_external_evidence.signing_key WHERE singleton;
    v_expected := encode(public.hmac(
      convert_to(p_payload,'UTF8'),decode(v_key,'hex'),'sha256'),'hex');
    RETURN v_expected = p_attestation;
  END;
  \$\$;
  REVOKE ALL ON FUNCTION pitr_external_evidence.verify_grant(text,text,text) FROM PUBLIC;
" >/dev/null

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
    external_grant_fingerprint text
  );
  CREATE TABLE pitr_continuity_receipt (
    receipt_id text PRIMARY KEY
  );
  INSERT INTO pitr_local_state
    (singleton,business_state,poll_epoch,poll_generation,placement_version,reconciled_through_f)
  VALUES (true,'pre_R',4,9,7,false);
" >/dev/null

docker exec -u postgres -e PGPASSWORD="$password" "$source_container" \
  sh -c 'rm -rf /tmp/basebackup && pg_basebackup -h 127.0.0.1 -U postgres -D /tmp/basebackup -Fp -Xs -P' \
  >/dev/null

psql_in "$source_container" "
  UPDATE pitr_local_state
     SET business_state='state_at_R', poll_epoch=5, poll_generation=10
   WHERE singleton;
" >/dev/null
r_committed="$(psql_in "$source_container" "SELECT business_state||'|'||poll_epoch||'|'||poll_generation FROM pitr_local_state WHERE singleton;")"
assert_exact "physical_pitr_R_transaction_committed" "state_at_R|5|10" "$r_committed"
r_lsn="$(psql_in "$source_container" "SELECT pg_create_restore_point('jlmirror_R');")"

psql_in "$source_container" "
  UPDATE pitr_local_state
     SET business_state='post_R_business_change', poll_generation=11
   WHERE singleton;
  INSERT INTO pitr_continuity_receipt(receipt_id) VALUES ('effect-after-r');
" >/dev/null
f_committed="$(psql_in "$source_container" "SELECT business_state||'|'||poll_generation||'|'||(SELECT count(*) FROM pitr_continuity_receipt) FROM pitr_local_state WHERE singleton;")"
assert_exact "physical_pitr_F_transaction_committed" "post_R_business_change|11|1" "$f_committed"
f_lsn="$(psql_in "$source_container" "SELECT pg_create_restore_point('jlmirror_F');")"
if [[ "$r_lsn" == "$f_lsn" ]]; then
  echo "PITR R and F unexpectedly share the same WAL LSN" >&2
  exit 1
fi
printf 'physical_pitr_restore_points=PASS R=%s F=%s\n' "$r_lsn" "$f_lsn"

# Only after F exists does the surviving authority issue the recovery grant.
# The nonce and HMAC were never present in the source database or base backup.
grant_payload="open-rel-030-recovery-v1|R|F|6|8|effect-after-r|$recovery_nonce"
psql_in "$control_container" "
  INSERT INTO pitr_external_evidence.recovery_grant(grant_id,payload,attestation)
  SELECT 'grant-F-1',
         '$grant_payload',
         encode(public.hmac(convert_to('$grant_payload','UTF8'),decode(key_material,'hex'),'sha256'),'hex')
    FROM pitr_external_evidence.signing_key
   WHERE singleton;
" >/dev/null

grant_row="$(psql_in "$control_container" "SELECT grant_id||'|'||payload||'|'||attestation FROM pitr_external_evidence.recovery_grant WHERE grant_id='grant-F-1';")"
IFS='|' read -r grant_id grant_domain grant_r grant_f grant_epoch grant_placement grant_receipt grant_nonce grant_attestation <<< "$grant_row"
if [[ -z "${grant_attestation:-}" ]]; then
  echo "surviving authority failed to issue authenticated recovery grant" >&2
  exit 1
fi

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
  SELECT business_state || '|' || poll_epoch || '|' || poll_generation || '|' ||
         placement_version || '|' || reconciled_through_f::text || '|' ||
         (SELECT count(*) FROM pitr_continuity_receipt) || '|' ||
         coalesce(external_grant_id,'')
  FROM pitr_local_state WHERE singleton;
")"
assert_exact "physical_pitr_exact_R_state" "state_at_R|5|10|7|false|0|" "$restored_state"

external_state="$(psql_in "$control_container" "
  SELECT expected_successor_epoch || '|' || expected_placement_version || '|' || required_receipt
  FROM pitr_external_evidence.authority WHERE singleton;
")"
assert_exact "physical_pitr_external_F_survives" "6|8|effect-after-r" "$external_state"

# A restore can reproduce a local receipt string, but that is not admission
# evidence anymore. Without a verified external grant it remains fenced.
psql_in "$restored_container" "
  INSERT INTO pitr_continuity_receipt(receipt_id)
  VALUES ('effect-after-r') ON CONFLICT DO NOTHING;
" >/dev/null
local_self_mint="$(psql_in "$restored_container" "
  SELECT (
    reconciled_through_f
    AND external_grant_id IS NOT NULL
    AND external_grant_fingerprint IS NOT NULL
  )::text FROM pitr_local_state WHERE singleton;
")"
assert_exact "physical_pitr_local_self_mint_cannot_admit" "false" "$local_self_mint"

# Tampering with any surviving grant field fails at the external authority.
tampered_verify="$(psql_in "$control_container" "SELECT pitr_external_evidence.verify_grant('grant-F-1','$grant_payload-tampered','$grant_attestation')::text;")"
assert_exact "physical_pitr_tampered_external_grant_rejected" "false" "$tampered_verify"

verified="$(psql_in "$control_container" "SELECT pitr_external_evidence.verify_grant('$grant_id','$grant_payload','$grant_attestation')::text;")"
assert_exact "physical_pitr_external_grant_verified" "true" "$verified"

assert_exact "physical_pitr_grant_domain" "open-rel-030-recovery-v1" "$grant_domain"
assert_exact "physical_pitr_grant_R" "R" "$grant_r"
assert_exact "physical_pitr_grant_F" "F" "$grant_f"
assert_exact "physical_pitr_grant_epoch" "6" "$grant_epoch"
assert_exact "physical_pitr_grant_placement" "8" "$grant_placement"
assert_exact "physical_pitr_grant_receipt" "effect-after-r" "$grant_receipt"

grant_fingerprint="$(printf '%s' "$grant_payload" | sha256sum | awk '{print $1}')"

# Apply only facts extracted from the authenticated surviving grant. The local
# rollback-subject business mutation after R is deliberately not replayed.
psql_in "$restored_container" "
  UPDATE pitr_local_state
     SET poll_epoch=$grant_epoch,
         poll_generation=1,
         placement_version=$grant_placement,
         reconciled_through_f=true,
         external_grant_id='$grant_id',
         external_grant_fingerprint='$grant_fingerprint'
   WHERE singleton;
" >/dev/null

after_state="$(psql_in "$restored_container" "
  SELECT business_state || '|' || poll_epoch || '|' || poll_generation || '|' ||
         placement_version || '|' || reconciled_through_f::text || '|' ||
         (SELECT count(*) FROM pitr_continuity_receipt) || '|' || external_grant_id
  FROM pitr_local_state WHERE singleton;
")"
assert_exact "physical_pitr_reconciled_without_business_replay" \
  "state_at_R|6|1|8|true|1|grant-F-1" "$after_state"

# Final admission is explicitly a conjunction of restored local state and a
# fresh verification by the surviving authority; the restored database cannot
# make this final decision by minting its own receipt.
local_ready="$(psql_in "$restored_container" "
  SELECT (
    reconciled_through_f
    AND poll_epoch=$grant_epoch
    AND placement_version=$grant_placement
    AND external_grant_id='$grant_id'
    AND external_grant_fingerprint='$grant_fingerprint'
    AND EXISTS (SELECT 1 FROM pitr_continuity_receipt WHERE receipt_id='$grant_receipt')
  )::text FROM pitr_local_state WHERE singleton;
")"
external_ready="$(psql_in "$control_container" "SELECT pitr_external_evidence.verify_grant('$grant_id','$grant_payload','$grant_attestation')::text;")"
assert_exact "physical_pitr_local_reconciled_state" "true" "$local_ready"
assert_exact "physical_pitr_external_authority_still_verifies" "true" "$external_ready"
if [[ "$local_ready" != "true" || "$external_ready" != "true" ]]; then
  echo "physical PITR admission lacks surviving external authority" >&2
  exit 1
fi
printf '%s\n' 'physical_pitr_post_reconcile_admission=PASS authority=surviving_external_authenticated_grant'
printf '%s\n' 'physical_pitr_rf_reconciliation=PASS'
