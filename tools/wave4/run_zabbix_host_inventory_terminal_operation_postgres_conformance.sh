#!/usr/bin/env bash
set -euo pipefail
trap 'status=$?; echo "wave4_zabbix_host_inventory_terminal_operation=FAIL line=$LINENO status=$status" >&2; exit "$status"' ERR

POSTGRES_IMAGE="${POSTGRES_IMAGE:-postgres@sha256:4ef4dbc939d61acea57712655ddb4b4ab27419c913f94cca0cd57cb3ea3c2280}"
PG_CONTAINER="${PG_CONTAINER:-jlmirror-wave4-host-inventory-terminal-postgres}"
PG_PASSWORD="${PG_PASSWORD:-wave4-monitoring-password}"
PG_DATABASE="${PG_DATABASE:-jlmirror}"

cleanup() { docker rm -f "$PG_CONTAINER" >/dev/null 2>&1 || true; }
trap cleanup EXIT
cleanup

docker pull "$POSTGRES_IMAGE" >/dev/null
docker run -d --rm --name "$PG_CONTAINER" -e POSTGRES_PASSWORD="$PG_PASSWORD" -e POSTGRES_DB="$PG_DATABASE" "$POSTGRES_IMAGE" >/dev/null
stable_ready=0
for _ in $(seq 1 90); do
  if docker inspect -f '{{.State.Running}}' "$PG_CONTAINER" 2>/dev/null | grep -qx true \
     && docker exec "$PG_CONTAINER" psql -Atq -U postgres -d "$PG_DATABASE" -c 'SELECT 1' 2>/dev/null | grep -qx 1; then
    stable_ready=$((stable_ready + 1)); [[ "$stable_ready" -ge 3 ]] && break
  else stable_ready=0; fi
  sleep 1
done
test "$stable_ready" -ge 3

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
  sql/wave4/011_zabbix_host_inventory_terminal_operation_hardening.sql; do
  docker exec -i "$PG_CONTAINER" psql -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" < "$migration" >/dev/null
done

docker exec -i "$PG_CONTAINER" psql -q -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" <<'SQL'
CREATE ROLE wave4_runtime NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS;
GRANT USAGE ON SCHEMA monitoring TO wave4_runtime;
GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA monitoring TO wave4_runtime;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA monitoring TO wave4_runtime;
SQL

fp="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
scope='{"host_group_refs":["10"]}'
docker exec "$PG_CONTAINER" psql -q -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c "BEGIN; SET LOCAL ROLE wave4_runtime; SET LOCAL jlmirror.tenant_id='tenant-a'; SELECT * FROM monitoring.create_zabbix_source('tenant-a','create-terminal','$fp','source-terminal','generation-terminal','binding-terminal','validation-terminal','audit-terminal','principal-terminal','human_browser_session','credential-generation-terminal','authz-terminal','correlation-terminal','Terminal Guard Zabbix','provider-instance:terminal','https://zabbix.example.test/zabbix','credential-binding:terminal','$scope'::jsonb); SELECT monitoring_source_id FROM monitoring.claim_zabbix_initial_validation('tenant-a','validation-terminal','validation-claim-terminal'); SELECT monitoring.complete_zabbix_initial_validation('tenant-a','validation-terminal','validation-claim-terminal','validation-evidence-terminal','binding-terminal','provider-instance:terminal','current','succeeded',NULL,'[\"10\"]'::jsonb,'[]'::jsonb,'egress-validation-terminal','credential-generation-terminal'); SELECT monitoring.enqueue_zabbix_host_inventory_sync('tenant-a','source-terminal','inventory-terminal'); SELECT monitoring_source_id FROM monitoring.claim_zabbix_host_inventory('tenant-a','inventory-terminal','claim-terminal'); SELECT monitoring.complete_zabbix_host_inventory('tenant-a','inventory-terminal','claim-terminal','snapshot-terminal','binding-terminal','provider-instance:terminal','current','succeeded',NULL,true,'[]'::jsonb,'egress-terminal','credential-generation-terminal'); COMMIT;" >/dev/null

terminal_state="$(docker exec "$PG_CONTAINER" psql -Atq -U postgres -d "$PG_DATABASE" -c "BEGIN; SET LOCAL ROLE wave4_runtime; SET LOCAL jlmirror.tenant_id='tenant-a'; SELECT state FROM monitoring.monitoring_sync_operation WHERE monitoring_sync_operation_id='inventory-terminal'; COMMIT;" | tail -n1)"
test "$terminal_state" = "succeeded"

if docker exec "$PG_CONTAINER" psql -q -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c "BEGIN; SET LOCAL ROLE wave4_runtime; SET LOCAL jlmirror.tenant_id='tenant-a'; UPDATE monitoring.monitoring_sync_operation SET state='running', completed_at=NULL WHERE monitoring_sync_operation_id='inventory-terminal'; COMMIT;" >/tmp/wave4-terminal-reopen.out 2>&1; then
  echo "terminal host-inventory operation unexpectedly reopened" >&2
  exit 1
fi
grep -F "Terminal host inventory operation is immutable" /tmp/wave4-terminal-reopen.out >/dev/null

after_state="$(docker exec "$PG_CONTAINER" psql -Atq -U postgres -d "$PG_DATABASE" -c "BEGIN; SET LOCAL ROLE wave4_runtime; SET LOCAL jlmirror.tenant_id='tenant-a'; SELECT state FROM monitoring.monitoring_sync_operation WHERE monitoring_sync_operation_id='inventory-terminal'; COMMIT;" | tail -n1)"
test "$after_state" = "succeeded"

echo "wave4_zabbix_host_inventory_terminal_operation=PASS terminal_operation=immutable retry=new-operation-only snapshot_membership=closed"
