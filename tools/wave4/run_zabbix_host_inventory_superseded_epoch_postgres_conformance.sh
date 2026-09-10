#!/usr/bin/env bash
set -euo pipefail
trap 'status=$?; echo "wave4_zabbix_host_inventory_superseded_epoch=FAIL line=$LINENO status=$status" >&2; exit "$status"' ERR

POSTGRES_IMAGE="${POSTGRES_IMAGE:-postgres@sha256:4ef4dbc939d61acea57712655ddb4b4ab27419c913f94cca0cd57cb3ea3c2280}"
PG_CONTAINER="${PG_CONTAINER:-jlmirror-wave4-host-inventory-superseded-epoch-postgres}"
PG_PASSWORD="${PG_PASSWORD:-wave4-monitoring-password}"
PG_DATABASE="${PG_DATABASE:-jlmirror}"
cleanup() { docker rm -f "$PG_CONTAINER" >/dev/null 2>&1 || true; }
trap cleanup EXIT
cleanup

docker pull "$POSTGRES_IMAGE" >/dev/null
docker run -d --rm --name "$PG_CONTAINER" -e POSTGRES_PASSWORD="$PG_PASSWORD" -e POSTGRES_DB="$PG_DATABASE" "$POSTGRES_IMAGE" >/dev/null
for _ in $(seq 1 90); do
  if docker exec "$PG_CONTAINER" psql -Atq -U postgres -d "$PG_DATABASE" -c 'SELECT 1' 2>/dev/null | grep -qx 1; then break; fi
  sleep 1
done

for migration in \
  sql/wave4/001_monitoring_source_foundation.sql \
  sql/wave4/002_monitoring_source_audit_evidence.sql \
  sql/wave4/003_zabbix_initial_validation_worker.sql \
  sql/wave4/004_monitoring_boundary_hardening.sql \
  sql/wave4/005_zabbix_host_inventory.sql \
  sql/wave4/006_zabbix_host_inventory_boundary_hardening.sql \
  sql/wave4/007_zabbix_host_inventory_integrity_hardening.sql \
  sql/wave4/008_zabbix_host_inventory_poll_ordering_hardening.sql \
  sql/wave4/009_zabbix_host_inventory_evidence_authority_hardening.sql \
  sql/wave4/010_zabbix_host_inventory_final_authority_hardening.sql \
  sql/wave4/011_zabbix_host_inventory_terminal_operation_hardening.sql \
  sql/wave4/011a_zabbix_host_inventory_executor_roles.sql \
  sql/wave4/012_zabbix_host_inventory_recovery_authority_hardening.sql \
  sql/wave4/013_zabbix_host_inventory_executor_privileges.sql \
  sql/wave4/014_zabbix_host_inventory_resource_epoch_insert.sql \
  sql/wave4/015_zabbix_host_inventory_explicit_admission_and_resource_authority.sql \
  sql/wave4/016_zabbix_host_inventory_operation_insert_authority.sql \
  sql/wave4/017_zabbix_host_inventory_superseded_epoch_retirement.sql \
  sql/wave4/018_zabbix_host_inventory_claim_revision_immutability.sql \
  sql/wave4/019_zabbix_host_inventory_work_identity_and_invocation_authority.sql; do
  docker exec -i "$PG_CONTAINER" psql -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" < "$migration" >/dev/null
done

docker exec -i "$PG_CONTAINER" psql -q -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" <<'SQL'
CREATE ROLE wave4_runtime NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS;
GRANT USAGE ON SCHEMA monitoring TO wave4_runtime;
GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA monitoring TO wave4_runtime;
REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON monitoring.monitoring_host_inventory_runtime_admission FROM wave4_runtime;
SQL

fp="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
scope='{"host_group_refs":["10"]}'

docker exec "$PG_CONTAINER" psql -q -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c "BEGIN; SET LOCAL ROLE wave4_runtime; SET LOCAL jlmirror.tenant_id='tenant-a'; SELECT * FROM monitoring.create_zabbix_source('tenant-a','create-epoch','$fp','source-epoch','generation-epoch','binding-epoch','validation-epoch','audit-epoch','principal-epoch','human_browser_session','credential-generation-epoch','authz-epoch','correlation-epoch','Epoch Zabbix','provider-instance:epoch','https://zabbix.example.test/zabbix','credential-binding:epoch','$scope'::jsonb); SELECT monitoring_source_id FROM monitoring.claim_zabbix_initial_validation('tenant-a','validation-epoch','validation-claim-epoch'); SELECT monitoring.complete_zabbix_initial_validation('tenant-a','validation-epoch','validation-claim-epoch','validation-evidence-epoch','binding-epoch','provider-instance:epoch','current','succeeded',NULL,'[\"10\"]'::jsonb,'[]'::jsonb,'egress-validation-epoch','credential-generation-epoch'); COMMIT;" >/dev/null

# Explicitly establish epoch 2, then claim one poll under provider-worker authority.
docker exec "$PG_CONTAINER" psql -q -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c "BEGIN; SET LOCAL jlmirror.tenant_id='tenant-a'; SELECT monitoring.reestablish_zabbix_host_inventory_poll_epoch('tenant-a','source-epoch',1,2,'placement-2','recovery-2','admission-2'); COMMIT;" >/dev/null

docker exec "$PG_CONTAINER" psql -q -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c "BEGIN; SET LOCAL ROLE jlmirror_wave4_host_inventory_invoker; SET LOCAL jlmirror.tenant_id='tenant-a'; SELECT monitoring.enqueue_zabbix_host_inventory_sync('tenant-a','source-epoch','inventory-old-epoch'); SELECT monitoring_source_id FROM monitoring.claim_zabbix_host_inventory('tenant-a','inventory-old-epoch','claim-old-epoch'); COMMIT;" >/dev/null
old_authority="$(docker exec "$PG_CONTAINER" psql -Atq -U postgres -d "$PG_DATABASE" -c "SELECT host_inventory_poll_epoch || ':' || host_inventory_poll_generation FROM monitoring.monitoring_sync_operation WHERE monitoring_sync_operation_id='inventory-old-epoch';")"
test "$old_authority" = "2:1"

# Recovery establishes epoch 3 while preserving local generation 1.
docker exec "$PG_CONTAINER" psql -q -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c "BEGIN; SET LOCAL jlmirror.tenant_id='tenant-a'; SELECT monitoring.reestablish_zabbix_host_inventory_poll_epoch('tenant-a','source-epoch',2,3,'placement-3','recovery-3','admission-3'); COMMIT;" >/dev/null
source_authority="$(docker exec "$PG_CONTAINER" psql -Atq -U postgres -d "$PG_DATABASE" -c "SELECT host_inventory_poll_epoch || ':' || host_inventory_poll_generation FROM monitoring.monitoring_source WHERE monitoring_source_id='source-epoch';")"
test "$source_authority" = "3:1"

# Late completion from epoch 2 must retire cleanly before snapshot insertion.
docker exec "$PG_CONTAINER" psql -q -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c "BEGIN; SET LOCAL ROLE jlmirror_wave4_host_inventory_invoker; SET LOCAL jlmirror.tenant_id='tenant-a'; SELECT monitoring.complete_zabbix_host_inventory('tenant-a','inventory-old-epoch','claim-old-epoch','snapshot-old-epoch','binding-epoch','provider-instance:epoch','current','succeeded',NULL,true,'[]'::jsonb,'egress-old-epoch','credential-generation-epoch'); COMMIT;" >/dev/null

retired="$(docker exec "$PG_CONTAINER" psql -Atq -U postgres -d "$PG_DATABASE" -c "SELECT state || ':' || coalesce(last_error_class,'') || ':' || coalesce(claim_token,'') FROM monitoring.monitoring_sync_operation WHERE monitoring_sync_operation_id='inventory-old-epoch';")"
test "$retired" = "reconciliation_required:execution.superseded_poll_epoch_authority:"
snapshot_count="$(docker exec "$PG_CONTAINER" psql -Atq -U postgres -d "$PG_DATABASE" -c "SELECT count(*) FROM monitoring.monitoring_host_inventory_snapshot_evidence WHERE host_inventory_snapshot_evidence_id='snapshot-old-epoch';")"
test "$snapshot_count" = "0"

printf '%s\n' "wave4_zabbix_host_inventory_superseded_epoch=PASS schema=001-019 old_epoch=retired reconciliation=required stale_snapshot=absent invocation_authority=provider-worker-only"
