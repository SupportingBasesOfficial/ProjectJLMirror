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

# External continuity authority is deliberately outside the database image that
# will be rolled back. It represents the surviving placement/recovery evidence
# ADR-018 requires for (R,F] reconciliation.
psql_in "$control_container" "
  DROP SCHEMA IF EXISTS pitr_external_evidence CASCADE;
  CREATE SCHEMA pitr_external_evidence;
  CREATE TABLE pitr_external_evidence.authority (
    singleton boolean PRIMARY KEY DEFAULT true CHECK (singleton),
    boundary_f text NOT NULL,
    expected_successor_epoch bigint NOT NULL,
    expected_placement_version bigint NOT NULL,
    required_receipt text NOT NULL
  );
  INSERT INTO pitr_external_evidence.authority
    (singleton,boundary_f,expected_successor_epoch,expected_placement_version,required_receipt)
  VALUES (true,'F',6,8,'effect-after-r');
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
    reconciled_through_f boolean NOT NULL DEFAULT false
  );
  CREATE TABLE pitr_continuity_receipt (
    receipt_id text PRIMARY KEY
  );
  INSERT INTO pitr_local_state
    (singleton,business_state,poll_epoch,poll_generation,placement_version,reconciled_through_f)
  VALUES (true,'pre_R',4,9,7,false);
" >/dev/null

# Physical base backup predates R. The restore must therefore replay archived WAL
# and stop at the named restore point instead of merely cloning the latest data.
docker exec -u postgres -e PGPASSWORD="$password" "$source_container" \
  sh -c 'rm -rf /tmp/basebackup && pg_basebackup -h 127.0.0.1 -U postgres -D /tmp/basebackup -Fp -Xs -P' \
  >/dev/null

psql_in "$source_container" "
  UPDATE pitr_local_state
     SET business_state='state_at_R', poll_epoch=5, poll_generation=10
   WHERE singleton;
  SELECT pg_create_restore_point('jlmirror_R');

  UPDATE pitr_local_state
     SET business_state='post_R_business_change', poll_generation=11
   WHERE singleton;
  INSERT INTO pitr_continuity_receipt(receipt_id) VALUES ('effect-after-r');
  SELECT pg_create_restore_point('jlmirror_F');
  SELECT pg_switch_wal();
  CHECKPOINT;
  SELECT pg_switch_wal();
" >/dev/null

# Wait until archiving has definitely emitted WAL after the restore points.
for _ in $(seq 1 80); do
  archived_count="$(psql_in "$source_container" "SELECT archived_count FROM pg_stat_archiver;")"
  failed_count="$(psql_in "$source_container" "SELECT failed_count FROM pg_stat_archiver;")"
  if [[ "$failed_count" != "0" ]]; then
    echo "PITR WAL archive reported failures: $failed_count" >&2
    exit 1
  fi
  if [[ "$archived_count" -ge 2 ]]; then
    break
  fi
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
         (SELECT count(*) FROM pitr_continuity_receipt)
  FROM pitr_local_state WHERE singleton;
")"
assert_exact "physical_pitr_exact_R_state" "state_at_R|5|10|7|false|0" "$restored_state"

external_state="$(psql_in "$control_container" "
  SELECT expected_successor_epoch || '|' || expected_placement_version || '|' || required_receipt
  FROM pitr_external_evidence.authority WHERE singleton;
")"
assert_exact "physical_pitr_external_F_survives" "6|8|effect-after-r" "$external_state"

# A locally healthy restored database is still non-authoritative: it lacks F
# continuity and its epoch/placement are stale relative to the surviving owner.
before_admission="$(psql_in "$restored_container" "
  SELECT (
    s.reconciled_through_f
    AND s.poll_epoch = 6
    AND s.placement_version = 8
    AND EXISTS (SELECT 1 FROM pitr_continuity_receipt WHERE receipt_id='effect-after-r')
  )::text
  FROM pitr_local_state s WHERE singleton;
")"
assert_exact "physical_pitr_pre_reconcile_fail_closed" "false" "$before_admission"

# Reconcile only continuity/safety authority from (R,F]. The business rollback
# remains intentionally at R; we do not blindly replay post-R business state.
psql_in "$restored_container" "
  INSERT INTO pitr_continuity_receipt(receipt_id)
  VALUES ('effect-after-r') ON CONFLICT DO NOTHING;
  UPDATE pitr_local_state
     SET poll_epoch=6,
         poll_generation=1,
         placement_version=8,
         reconciled_through_f=true
   WHERE singleton;
" >/dev/null

after_state="$(psql_in "$restored_container" "
  SELECT business_state || '|' || poll_epoch || '|' || poll_generation || '|' ||
         placement_version || '|' || reconciled_through_f::text || '|' ||
         (SELECT count(*) FROM pitr_continuity_receipt)
  FROM pitr_local_state WHERE singleton;
")"
assert_exact "physical_pitr_reconciled_without_business_replay" \
  "state_at_R|6|1|8|true|1" "$after_state"

after_admission="$(psql_in "$restored_container" "
  SELECT (
    s.reconciled_through_f
    AND s.poll_epoch = 6
    AND s.placement_version = 8
    AND EXISTS (SELECT 1 FROM pitr_continuity_receipt WHERE receipt_id='effect-after-r')
  )::text
  FROM pitr_local_state s WHERE singleton;
")"
assert_exact "physical_pitr_post_reconcile_admission" "true" "$after_admission"

printf '%s\n' 'physical_pitr_rf_reconciliation=PASS'
