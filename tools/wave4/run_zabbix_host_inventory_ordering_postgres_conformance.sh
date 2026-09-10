#!/usr/bin/env bash
set -euo pipefail
trap 'status=$?; echo "wave4_zabbix_host_inventory_ordering=FAIL line=$LINENO status=$status" >&2; exit "$status"' ERR

POSTGRES_IMAGE="${POSTGRES_IMAGE:-postgres@sha256:4ef4dbc939d61acea57712655ddb4b4ab27419c913f94cca0cd57cb3ea3c2280}"
PG_CONTAINER="${PG_CONTAINER:-jlmirror-wave4-host-inventory-ordering-postgres}"
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
  sql/wave4/008_zabbix_host_inventory_poll_ordering_hardening.sql; do
  docker exec -i "$PG_CONTAINER" psql -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" < "$migration" >/dev/null
done

docker exec -i "$PG_CONTAINER" psql -q -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" <<'SQL'
CREATE ROLE wave4_runtime NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS;
GRANT USAGE ON SCHEMA monitoring TO wave4_runtime;
GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA monitoring TO wave4_runtime;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA monitoring TO wave4_runtime;
SQL

# Even after a broad runtime function grant there must be no alternate unfenced completion entry point.
unfenced_helper_count="$(docker exec "$PG_CONTAINER" psql -Atq -U postgres -d "$PG_DATABASE" -c "SELECT count(*) FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace WHERE n.nspname='monitoring' AND p.proname='wave4_complete_zabbix_host_inventory_pre_poll_fence';")"
test "$unfenced_helper_count" = "0"

fp="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
scope='{"host_group_refs":["10"]}'
docker exec "$PG_CONTAINER" psql -q -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c "BEGIN; SET LOCAL ROLE wave4_runtime; SET LOCAL jlmirror.tenant_id='tenant-a'; SELECT * FROM monitoring.create_zabbix_source('tenant-a','create-a','$fp','source-a','generation-a','binding-a','validation-a','audit-a','principal-a','human_browser_session','credential-generation-a','authz-a','correlation-a','Company A Zabbix','provider-instance:a','https://zabbix.example.test/zabbix','credential-binding:a','$scope'::jsonb); SELECT monitoring_source_id FROM monitoring.claim_zabbix_initial_validation('tenant-a','validation-a','validation-claim-a'); SELECT monitoring.complete_zabbix_initial_validation('tenant-a','validation-a','validation-claim-a','validation-evidence-a','binding-a','provider-instance:a','current','succeeded',NULL,'[\"10\"]'::jsonb,'[]'::jsonb,'egress-validation-a','credential-generation-a'); COMMIT;" >/dev/null

empty='[]'
host1_positive='{"monitoring_resource_id":"resource-101","provider_evidence_id":"provider-evidence-101-positive","hostid":"101","display_name":"Core Switch","evidence_fingerprint":"1111111111111111111111111111111111111111111111111111111111111111","normalized_evidence":{"technical_name":"core-sw-01","display_name":"Core Switch","inventory":{"vendor":"Cisco","model":"C9300"},"interfaces":[],"groups":[{"ref":"10","name":"Network"}],"templates":[],"tags":[]}}'
host1_new='{"monitoring_resource_id":"resource-101","provider_evidence_id":"provider-evidence-101-new","hostid":"101","display_name":"Core Switch","evidence_fingerprint":"1111111111111111111111111111111111111111111111111111111111111111","normalized_evidence":{"technical_name":"core-sw-01","display_name":"Core Switch","inventory":{"vendor":"Cisco","model":"C9300"},"interfaces":[],"groups":[{"ref":"10","name":"Network"}],"templates":[],"tags":[]}}'
host2_new='{"monitoring_resource_id":"resource-102","provider_evidence_id":"provider-evidence-102-new","hostid":"102","display_name":"Edge Router","evidence_fingerprint":"2222222222222222222222222222222222222222222222222222222222222222","normalized_evidence":{"technical_name":"edge-rtr-01","display_name":"Edge Router","inventory":{"vendor":"Cisco","model":"ISR"},"interfaces":[],"groups":[{"ref":"10","name":"Network"}],"templates":[],"tags":[]}}'

# Establish an older complete negative snapshot, then a newer positive observation.
docker exec "$PG_CONTAINER" psql -q -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c "BEGIN; SET LOCAL ROLE wave4_runtime; SET LOCAL jlmirror.tenant_id='tenant-a'; SELECT monitoring.enqueue_zabbix_host_inventory_sync('tenant-a','source-a','inventory-base'); SELECT monitoring_source_id FROM monitoring.claim_zabbix_host_inventory('tenant-a','inventory-base','claim-base'); SELECT monitoring.complete_zabbix_host_inventory('tenant-a','inventory-base','claim-base','snapshot-base','binding-a','provider-instance:a','current','succeeded',NULL,true,'$empty'::jsonb,'egress-base','credential-generation-a'); COMMIT;" >/dev/null
sleep 0.02
docker exec "$PG_CONTAINER" psql -q -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c "BEGIN; SET LOCAL ROLE wave4_runtime; SET LOCAL jlmirror.tenant_id='tenant-a'; SELECT monitoring.enqueue_zabbix_host_inventory_sync('tenant-a','source-a','inventory-positive'); SELECT monitoring_source_id FROM monitoring.claim_zabbix_host_inventory('tenant-a','inventory-positive','claim-positive'); SELECT monitoring.complete_zabbix_host_inventory('tenant-a','inventory-positive','claim-positive','snapshot-positive','binding-a','provider-instance:a','current','succeeded',NULL,true,'[$host1_positive]'::jsonb,'egress-positive','credential-generation-a'); COMMIT;" >/dev/null

# Historical negative evidence must not reverse the newer positive observation.
if docker exec "$PG_CONTAINER" psql -q -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c "BEGIN; SET LOCAL ROLE wave4_runtime; SET LOCAL jlmirror.tenant_id='tenant-a'; UPDATE monitoring.monitoring_resource SET presence_state='removed', removed_at=(SELECT observed_at FROM monitoring.monitoring_host_inventory_snapshot_evidence WHERE host_inventory_snapshot_evidence_id='snapshot-base') WHERE monitoring_resource_id='resource-101'; COMMIT;" >/tmp/wave4-stale-negative.out 2>&1; then
  echo "historical negative snapshot unexpectedly reversed newer positive presence" >&2
  exit 1
fi
grep -F "newer complete authoritative negative snapshot evidence" /tmp/wave4-stale-negative.out >/dev/null

# Claim two polls in order. The later claim supersedes the older completion authority.
docker exec "$PG_CONTAINER" psql -q -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c "BEGIN; SET LOCAL ROLE wave4_runtime; SET LOCAL jlmirror.tenant_id='tenant-a'; SELECT monitoring.enqueue_zabbix_host_inventory_sync('tenant-a','source-a','inventory-old'); SELECT monitoring.enqueue_zabbix_host_inventory_sync('tenant-a','source-a','inventory-new'); SELECT monitoring_source_id FROM monitoring.claim_zabbix_host_inventory('tenant-a','inventory-old','claim-old'); SELECT monitoring_source_id FROM monitoring.claim_zabbix_host_inventory('tenant-a','inventory-new','claim-new'); COMMIT;" >/dev/null

ordering="$(docker exec "$PG_CONTAINER" psql -Atq -U postgres -d "$PG_DATABASE" -c "BEGIN; SET LOCAL ROLE wave4_runtime; SET LOCAL jlmirror.tenant_id='tenant-a'; SELECT (SELECT host_inventory_poll_generation FROM monitoring.monitoring_sync_operation WHERE monitoring_sync_operation_id='inventory-old') || '|' || (SELECT host_inventory_poll_generation FROM monitoring.monitoring_sync_operation WHERE monitoring_sync_operation_id='inventory-new') || '|' || (SELECT host_inventory_poll_generation FROM monitoring.monitoring_source WHERE monitoring_source_id='source-a'); COMMIT;" | tail -n1)"
test "$ordering" = "3|4|4"

# Newer poll completes first and introduces host 102.
docker exec "$PG_CONTAINER" psql -q -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c "BEGIN; SET LOCAL ROLE wave4_runtime; SET LOCAL jlmirror.tenant_id='tenant-a'; SELECT monitoring.complete_zabbix_host_inventory('tenant-a','inventory-new','claim-new','snapshot-new','binding-a','provider-instance:a','current','succeeded',NULL,true,'[$host1_new,$host2_new]'::jsonb,'egress-new','credential-generation-a'); COMMIT;" >/dev/null

# Older completion arrives later with an empty snapshot. It must be retired without snapshot/resource mutation.
docker exec "$PG_CONTAINER" psql -q -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c "BEGIN; SET LOCAL ROLE wave4_runtime; SET LOCAL jlmirror.tenant_id='tenant-a'; SELECT monitoring.complete_zabbix_host_inventory('tenant-a','inventory-old','claim-old','snapshot-old-late','binding-a','provider-instance:a','current','succeeded',NULL,true,'$empty'::jsonb,'egress-old','credential-generation-a'); COMMIT;" >/dev/null

final_state="$(docker exec "$PG_CONTAINER" psql -Atq -U postgres -d "$PG_DATABASE" -c "BEGIN; SET LOCAL ROLE wave4_runtime; SET LOCAL jlmirror.tenant_id='tenant-a'; SELECT (SELECT state || ':' || coalesce(last_error_class,'') FROM monitoring.monitoring_sync_operation WHERE monitoring_sync_operation_id='inventory-old') || '|' || (SELECT count(*) FROM monitoring.monitoring_host_inventory_snapshot_evidence WHERE host_inventory_snapshot_evidence_id='snapshot-old-late') || '|' || (SELECT count(*) FROM monitoring.monitoring_resource WHERE presence_state='present') || '|' || (SELECT count(*) FROM monitoring.monitoring_resource WHERE provider_external_ref='102' AND presence_state='present'); COMMIT;" | tail -n1)"
test "$final_state" = "reconciliation_required:execution.superseded_poll_authority|0|2|1"

printf '%s\n' "wave4_zabbix_host_inventory_ordering=PASS poll_generation=claim_ordered late_completion=retired_without_mutation stale_negative=blocked newer_positive=preserved unfenced_helper=absent"
