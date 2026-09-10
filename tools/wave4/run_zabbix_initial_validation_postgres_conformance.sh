#!/usr/bin/env bash
set -euo pipefail

POSTGRES_IMAGE="${POSTGRES_IMAGE:-postgres@sha256:4ef4dbc939d61acea57712655ddb4b4ab27419c913f94cca0cd57cb3ea3c2280}"
PG_CONTAINER="${PG_CONTAINER:-jlmirror-wave4-zabbix-validation-postgres}"
PG_PASSWORD="${PG_PASSWORD:-wave4-monitoring-password}"
PG_DATABASE="${PG_DATABASE:-jlmirror}"

cleanup() { docker rm -f "$PG_CONTAINER" >/dev/null 2>&1 || true; }
trap cleanup EXIT
cleanup

docker pull "$POSTGRES_IMAGE" >/dev/null
docker run -d --rm --name "$PG_CONTAINER" -e POSTGRES_PASSWORD="$PG_PASSWORD" -e POSTGRES_DB="$PG_DATABASE" "$POSTGRES_IMAGE" >/dev/null

stable=0
for _ in $(seq 1 90); do
  if docker exec "$PG_CONTAINER" pg_isready -U postgres -d "$PG_DATABASE" >/dev/null 2>&1; then
    stable=$((stable + 1))
    if [ "$stable" -ge 3 ]; then break; fi
  else
    stable=0
  fi
  sleep 1
done
test "$stable" -ge 3

for migration in sql/wave4/001_monitoring_source_foundation.sql sql/wave4/002_monitoring_source_audit_evidence.sql sql/wave4/003_zabbix_initial_validation_worker.sql; do
  docker exec -i "$PG_CONTAINER" psql -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" < "$migration" >/dev/null
done

fp="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
scope='{"host_group_refs":["10","20"]}'
docker exec "$PG_CONTAINER" psql -Atq -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c \
"SELECT * FROM monitoring.create_zabbix_source('tenant-a','create-a','$fp','source-a','generation-a','binding-a','sync-a','audit-a','principal-a','human_browser_session','cred-gen-a','authz-a','corr-a','Company A','provider-instance:central','https://zabbix.example.test/zabbix','credential-binding:central','$scope'::jsonb);" >/dev/null

claim="$(docker exec "$PG_CONTAINER" psql -Atq -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c \
"SELECT monitoring_source_id || '|' || provider_scope_tenant_binding_id || '|' || source_instance_generation || '|' || provider_instance_ref FROM monitoring.claim_zabbix_initial_validation('tenant-a','sync-a','claim-a');")"
test "$claim" = "source-a|binding-a|generation-a|provider-instance:central"

if docker exec "$PG_CONTAINER" psql -q -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c \
"SELECT * FROM monitoring.claim_zabbix_initial_validation('tenant-a','sync-a','claim-b');" >/tmp/wave4-double-claim.out 2>&1; then
  echo "second claim unexpectedly succeeded" >&2; exit 1
fi
grep -F "monitoring.initial_validation_not_claimable" /tmp/wave4-double-claim.out >/dev/null

docker exec "$PG_CONTAINER" psql -q -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c \
"SELECT monitoring.complete_zabbix_initial_validation('tenant-a','sync-a','claim-a','validation-a','binding-a','provider-instance:central','current','succeeded',NULL,'[\"10\",\"20\"]'::jsonb,'[]'::jsonb,'egress-decision:1','credential-generation:1');" >/dev/null

state="$(docker exec "$PG_CONTAINER" psql -Atq -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c \
"SELECT o.state || '|' || s.operational_evidence_state || '|' || (s.last_successful_sync_at IS NOT NULL)::text || '|' || e.operation_state FROM monitoring.monitoring_sync_operation o JOIN monitoring.monitoring_source s ON s.tenant_id=o.tenant_id AND s.monitoring_source_id=o.monitoring_source_id JOIN monitoring.monitoring_source_validation_evidence e ON e.tenant_id=o.tenant_id AND e.monitoring_sync_operation_id=o.monitoring_sync_operation_id WHERE o.tenant_id='tenant-a' AND o.monitoring_sync_operation_id='sync-a';")"
test "$state" = "succeeded|current|true|succeeded"

if docker exec "$PG_CONTAINER" psql -q -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c \
"UPDATE monitoring.monitoring_source_validation_evidence SET failure_class='changed' WHERE tenant_id='tenant-a' AND validation_evidence_id='validation-a';" >/tmp/wave4-evidence-mutation.out 2>&1; then
  echo "validation evidence mutation unexpectedly succeeded" >&2; exit 1
fi
grep -F "Monitoring source validation evidence is immutable" /tmp/wave4-evidence-mutation.out >/dev/null

fp2="bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
docker exec "$PG_CONTAINER" psql -Atq -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c \
"SELECT * FROM monitoring.create_zabbix_source('tenant-b','create-b','$fp2','source-b','generation-b','binding-b','sync-b','audit-b','principal-b','human_browser_session','cred-gen-b','authz-b','corr-b','Company B','provider-instance:central','https://zabbix.example.test/zabbix','credential-binding:central','{\"host_group_refs\":[\"30\"]}'::jsonb);" >/dev/null

docker exec "$PG_CONTAINER" psql -Atq -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c \
"SELECT monitoring_source_id FROM monitoring.claim_zabbix_initial_validation('tenant-b','sync-b','claim-b');" >/dev/null

docker exec "$PG_CONTAINER" psql -q -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c \
"UPDATE monitoring.monitoring_source SET configuration_revision=2, credential_binding_ref='credential-binding:rotated' WHERE tenant_id='tenant-b' AND monitoring_source_id='source-b';" >/dev/null

docker exec "$PG_CONTAINER" psql -q -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c \
"SELECT monitoring.complete_zabbix_initial_validation('tenant-b','sync-b','claim-b','validation-b','binding-b','provider-instance:central','current','succeeded',NULL,'[\"30\"]'::jsonb,'[]'::jsonb,'egress-decision:2','credential-generation:2');" >/dev/null

stale_state="$(docker exec "$PG_CONTAINER" psql -Atq -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c \
"SELECT o.state || '|' || (o.validation_evidence_id IS NULL)::text || '|' || coalesce(o.last_error_class,'') || '|' || s.operational_evidence_state || '|' || (SELECT count(*) FROM monitoring.monitoring_source_validation_evidence e WHERE e.tenant_id='tenant-b' AND e.monitoring_sync_operation_id='sync-b') FROM monitoring.monitoring_sync_operation o JOIN monitoring.monitoring_source s ON s.tenant_id=o.tenant_id AND s.monitoring_source_id=o.monitoring_source_id WHERE o.tenant_id='tenant-b' AND o.monitoring_sync_operation_id='sync-b';")"
test "$stale_state" = "reconciliation_required|true|execution.stale_authority|reconciliation_required|0"

# Deterministic concurrency falsifier for the late-review TOCTOU race.
# The test-only trigger acquires an uncontended transaction-scoped advisory lock only after
# the completion function has crossed its authority fence. Pollers probe that lock using
# pg_try_advisory_lock and immediately release it when they win, so they never block the
# completion. Once the lock becomes unavailable, we know completion is inside the trigger;
# with the fix, the authoritative source row is already locked. The pre-fix implementation
# reaches the same trigger without that row lock, so the concurrent edit finishes and fails
# this falsifier.
fp3="cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc"
docker exec "$PG_CONTAINER" psql -Atq -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c \
"SELECT * FROM monitoring.create_zabbix_source('tenant-c','create-c','$fp3','source-c','generation-c','binding-c','sync-c','audit-c','principal-c','human_browser_session','cred-gen-c','authz-c','corr-c','Company C','provider-instance:central','https://zabbix.example.test/zabbix','credential-binding:central','{\"host_group_refs\":[\"40\"]}'::jsonb); SELECT monitoring_source_id FROM monitoring.claim_zabbix_initial_validation('tenant-c','sync-c','claim-c');" >/dev/null

docker exec "$PG_CONTAINER" psql -q -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" <<'SQL' >/dev/null
CREATE OR REPLACE FUNCTION monitoring.wave4_test_pause_validation_evidence()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
  PERFORM pg_advisory_xact_lock(424242);
  PERFORM pg_sleep(5);
  RETURN NEW;
END;
$$;
CREATE TRIGGER wave4_test_pause_validation_evidence
BEFORE INSERT ON monitoring.monitoring_source_validation_evidence
FOR EACH ROW EXECUTE FUNCTION monitoring.wave4_test_pause_validation_evidence();
SQL

(
  docker exec "$PG_CONTAINER" psql -q -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c \
  "SELECT monitoring.complete_zabbix_initial_validation('tenant-c','sync-c','claim-c','validation-c','binding-c','provider-instance:central','current','succeeded',NULL,'[\"40\"]'::jsonb,'[]'::jsonb,'egress-decision:3','credential-generation:3');" >/tmp/wave4-race-complete.out 2>&1
) &
complete_pid=$!

barrier_seen=0
for _ in $(seq 1 50); do
  lock_busy="$(docker exec "$PG_CONTAINER" psql -Atq -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c \
  "WITH probe AS (SELECT pg_try_advisory_lock(424242) AS acquired), release AS (SELECT CASE WHEN acquired THEN pg_advisory_unlock(424242) ELSE false END AS released FROM probe) SELECT CASE WHEN (SELECT acquired FROM probe) THEN 'f' ELSE 't' END;")"
  if [ "$lock_busy" = "t" ]; then
    barrier_seen=1
    break
  fi
  if ! kill -0 "$complete_pid" 2>/dev/null; then
    echo "completion exited before publishing post-fence advisory barrier" >&2
    cat /tmp/wave4-race-complete.out >&2 || true
    exit 1
  fi
  sleep 0.1
done
test "$barrier_seen" -eq 1

(
  docker exec "$PG_CONTAINER" psql -q -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c \
  "UPDATE monitoring.monitoring_source SET configuration_revision=2, credential_binding_ref='credential-binding:rotated-after-fence' WHERE tenant_id='tenant-c' AND monitoring_source_id='source-c';" >/tmp/wave4-race-edit.out 2>&1
) &
edit_pid=$!
sleep 1

if ! kill -0 "$edit_pid" 2>/dev/null; then
  echo "concurrent configuration edit crossed the completion fence before source lock release" >&2
  cat /tmp/wave4-race-edit.out >&2 || true
  exit 1
fi

wait "$complete_pid"
wait "$edit_pid"

docker exec "$PG_CONTAINER" psql -q -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c \
"DROP TRIGGER wave4_test_pause_validation_evidence ON monitoring.monitoring_source_validation_evidence; DROP FUNCTION monitoring.wave4_test_pause_validation_evidence();" >/dev/null

race_state="$(docker exec "$PG_CONTAINER" psql -Atq -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c \
"SELECT o.state || '|' || s.configuration_revision || '|' || s.operational_evidence_state || '|' || (SELECT count(*) FROM monitoring.monitoring_source_validation_evidence e WHERE e.tenant_id='tenant-c' AND e.monitoring_sync_operation_id='sync-c') FROM monitoring.monitoring_sync_operation o JOIN monitoring.monitoring_source s ON s.tenant_id=o.tenant_id AND s.monitoring_source_id=o.monitoring_source_id WHERE o.tenant_id='tenant-c' AND o.monitoring_sync_operation_id='sync-c';")"
test "$race_state" = "succeeded|2|current|1"

printf '%s\n' "wave4_zabbix_initial_validation_postgres=PASS claim=single-winner completion=fenced stale=retired_without_source_mutation race=source_row_lock_blocks_concurrent_edit evidence=immutable shared_provider=preserved retry_policy=not_selected"
