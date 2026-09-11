#!/usr/bin/env bash
set -euo pipefail
trap 'status=$?; echo "wave4_zabbix_metric_definitions_liveness=FAIL line=$LINENO status=$status" >&2; exit "$status"' ERR

POSTGRES_IMAGE="${POSTGRES_IMAGE:-postgres@sha256:4ef4dbc939d61acea57712655ddb4b4ab27419c913f94cca0cd57cb3ea3c2280}"
PG_CONTAINER="${PG_CONTAINER:-jlmirror-wave4-metric-definitions-liveness-postgres}"
PG_PASSWORD="${PG_PASSWORD:-wave4-monitoring-password}"
PG_DATABASE="${PG_DATABASE:-jlmirror}"
cleanup(){ docker rm -f "$PG_CONTAINER" >/dev/null 2>&1 || true; }
trap cleanup EXIT
cleanup

docker pull "$POSTGRES_IMAGE" >/dev/null
docker run -d --rm --name "$PG_CONTAINER" -e POSTGRES_PASSWORD="$PG_PASSWORD" -e POSTGRES_DB="$PG_DATABASE" "$POSTGRES_IMAGE" >/dev/null
stable_ready=0
for _ in $(seq 1 90); do
  if docker inspect -f '{{.State.Running}}' "$PG_CONTAINER" 2>/dev/null | grep -qx true \
     && docker exec "$PG_CONTAINER" psql -Atq -U postgres -d "$PG_DATABASE" -c 'SELECT 1' 2>/dev/null | grep -qx 1; then
    stable_ready=$((stable_ready+1)); [[ "$stable_ready" -ge 3 ]] && break
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
  sql/wave4/011_zabbix_host_inventory_terminal_operation_hardening.sql \
  sql/wave4/011a_zabbix_host_inventory_executor_roles.sql \
  sql/wave4/012_zabbix_host_inventory_recovery_authority_hardening.sql \
  sql/wave4/013_zabbix_host_inventory_executor_privileges.sql \
  sql/wave4/014_zabbix_host_inventory_resource_epoch_insert.sql \
  sql/wave4/015_zabbix_host_inventory_explicit_admission_and_resource_authority.sql \
  sql/wave4/016_zabbix_host_inventory_operation_insert_authority.sql \
  sql/wave4/017_zabbix_host_inventory_superseded_epoch_retirement.sql \
  sql/wave4/018_zabbix_host_inventory_claim_revision_immutability.sql \
  sql/wave4/019_zabbix_host_inventory_work_identity_and_invocation_authority.sql \
  sql/wave4/020_zabbix_metric_definitions.sql \
  sql/wave4/021_zabbix_metric_definitions_authority_hardening.sql \
  sql/wave4/022_zabbix_metric_definitions_atomic_preflight.sql \
  sql/wave4/023_zabbix_metric_definitions_qualified_claim.sql \
  sql/wave4/024_zabbix_metric_definitions_evidence_and_drift_authority.sql \
  sql/wave4/025_zabbix_metric_definitions_drift_visibility.sql \
  sql/wave4/026_zabbix_metric_definitions_provenance_closure.sql \
  sql/wave4/027_zabbix_metric_definitions_completion_authority.sql \
  sql/wave4/028_zabbix_metric_definitions_completion_liveness.sql; do
  docker exec -i "$PG_CONTAINER" psql -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" < "$migration" >/dev/null
done

docker exec -i "$PG_CONTAINER" psql -q -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" <<'SQL'
CREATE ROLE wave4_runtime NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS;
GRANT USAGE ON SCHEMA monitoring TO wave4_runtime;
GRANT SELECT,INSERT,UPDATE ON ALL TABLES IN SCHEMA monitoring TO wave4_runtime;
REVOKE INSERT,UPDATE,DELETE,TRUNCATE ON monitoring.monitoring_host_inventory_runtime_admission FROM wave4_runtime;
REVOKE INSERT,UPDATE,DELETE,TRUNCATE ON monitoring.monitoring_metric_definition_runtime_admission FROM wave4_runtime;
SQL

fp="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
scope='{"host_group_refs":["10"]}'
docker exec "$PG_CONTAINER" psql -q -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c "BEGIN; SET LOCAL ROLE wave4_runtime; SET LOCAL jlmirror.tenant_id='tenant-a'; SELECT * FROM monitoring.create_zabbix_source('tenant-a','create-live','$fp','source-live','generation-live','binding-live','validation-live','audit-live','principal-live','human_browser_session','credential-generation-live','authz-live','correlation-live','Liveness Zabbix','provider-instance:live','https://zabbix.example.test/zabbix','credential-binding:live','$scope'::jsonb); SELECT monitoring_source_id FROM monitoring.claim_zabbix_initial_validation('tenant-a','validation-live','validation-claim-live'); SELECT monitoring.complete_zabbix_initial_validation('tenant-a','validation-live','validation-claim-live','validation-evidence-live','binding-live','provider-instance:live','current','succeeded',NULL,'[\"10\"]'::jsonb,'[]'::jsonb,'egress-validation-live','credential-generation-live'); COMMIT;" >/dev/null

docker exec "$PG_CONTAINER" psql -q -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c "BEGIN; SET LOCAL jlmirror.tenant_id='tenant-a'; SELECT monitoring.reestablish_zabbix_host_inventory_poll_epoch('tenant-a','source-live',1,2,'placement-host-live','recovery-host-live','admission-host-live'); COMMIT;" >/dev/null
normalized_host='{"technical_name":"host-101","display_name":"Host 101","inventory":{},"interfaces":[],"groups":[{"ref":"10","name":"Core"}],"templates":[],"tags":[]}'
host_fp="$(python3 -c 'import hashlib,json,sys; print(hashlib.sha256(json.dumps(json.loads(sys.argv[1]),separators=(",",":"),sort_keys=True,ensure_ascii=False).encode()).hexdigest())' "$normalized_host")"
host="{\"monitoring_resource_id\":\"resource-live-101\",\"provider_evidence_id\":\"provider-host-live-101\",\"hostid\":\"101\",\"display_name\":\"Host 101\",\"evidence_fingerprint\":\"$host_fp\",\"normalized_evidence\":$normalized_host}"
docker exec "$PG_CONTAINER" psql -q -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c "BEGIN; SET LOCAL ROLE jlmirror_wave4_host_inventory_invoker; SET LOCAL jlmirror.tenant_id='tenant-a'; SELECT monitoring.enqueue_zabbix_host_inventory_sync('tenant-a','source-live','host-live-op'); SELECT monitoring_source_id FROM monitoring.claim_zabbix_host_inventory('tenant-a','host-live-op','host-live-claim'); SELECT monitoring.complete_zabbix_host_inventory('tenant-a','host-live-op','host-live-claim','host-live-snapshot','binding-live','provider-instance:live','current','succeeded',NULL,true,'[$host]'::jsonb,'egress-host-live','credential-generation-live'); COMMIT;" >/dev/null

docker exec "$PG_CONTAINER" psql -q -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c "BEGIN; SET LOCAL jlmirror.tenant_id='tenant-a'; SELECT monitoring.reestablish_metric_definition_runtime_admission('tenant-a','source-live',2,'placement-metric-live','recovery-metric-live','admission-metric-live'); COMMIT;" >/dev/null

run_case() {
  local op="$1" claim="$2" snapshot="$3" expected="$4" payload="$5"
  docker exec "$PG_CONTAINER" psql -q -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c "BEGIN; SET LOCAL ROLE jlmirror_wave4_metric_definition_invoker; SET LOCAL jlmirror.tenant_id='tenant-a'; SELECT monitoring.enqueue_zabbix_metric_definition_sync('tenant-a','source-live','$op'); SELECT monitoring_source_id FROM monitoring.claim_zabbix_metric_definitions('tenant-a','$op','$claim'); SELECT monitoring.complete_zabbix_metric_definitions('tenant-a','$op','$claim','$snapshot','current','succeeded',NULL,'egress-live','credential-generation-live',true,'$payload'::jsonb); COMMIT;" >/dev/null
  actual="$(docker exec "$PG_CONTAINER" psql -Atq -U postgres -d "$PG_DATABASE" -c "SELECT state||':'||last_error_class||':'||(claim_token IS NULL)::int FROM monitoring.monitoring_sync_operation WHERE monitoring_sync_operation_id='$op';")"
  test "$actual" = "reconciliation_required:$expected:1"
  snap="$(docker exec "$PG_CONTAINER" psql -Atq -U postgres -d "$PG_DATABASE" -c "SELECT operation_state||':'||operational_evidence_state||':'||snapshot_complete::int FROM monitoring.monitoring_metric_definition_snapshot_evidence WHERE metric_definition_snapshot_evidence_id='$snapshot';")"
  test "$snap" = "reconciliation_required:reconciliation_required:0"
}

# Malformed item evidence becomes a durable terminal outcome instead of leaving work running.
run_case 'metric-live-malformed' 'metric-live-malformed-claim' 'metric-live-malformed-snapshot' 'provider.protocol_invalid' '[{"itemid":"","hostid":"101","name":"CPU","key":"system.cpu.util","unit":"%","native_value_type":"float","operational_state":"enabled"}]'
test "$(docker exec "$PG_CONTAINER" psql -Atq -U postgres -d "$PG_DATABASE" -c "SELECT count(*) FROM monitoring.metric_definition WHERE monitoring_source_id='source-live';")" = "0"

# Duplicate itemid is also terminalized and cannot partially create the first entry.
run_case 'metric-live-duplicate' 'metric-live-duplicate-claim' 'metric-live-duplicate-snapshot' 'provider.protocol_invalid' '[{"itemid":"5001","hostid":"101","name":"CPU","key":"system.cpu.util","unit":"%","native_value_type":"float","operational_state":"enabled"},{"itemid":"5001","hostid":"101","name":"CPU duplicate","key":"system.cpu.util","unit":"%","native_value_type":"float","operational_state":"enabled"}]'
test "$(docker exec "$PG_CONTAINER" psql -Atq -U postgres -d "$PG_DATABASE" -c "SELECT count(*) FROM monitoring.metric_definition WHERE monitoring_source_id='source-live';")" = "0"

# A provider item referencing a host outside the current canonical evidence domain is terminalized.
run_case 'metric-live-missing-host' 'metric-live-missing-host-claim' 'metric-live-missing-host-snapshot' 'provider.host_association_invalid' '[{"itemid":"5002","hostid":"999","name":"Orphan","key":"orphan.metric","unit":"","native_value_type":"unsigned","operational_state":"enabled"}]'
test "$(docker exec "$PG_CONTAINER" psql -Atq -U postgres -d "$PG_DATABASE" -c "SELECT count(*) FROM monitoring.metric_definition WHERE monitoring_source_id='source-live';")" = "0"

# Final schema proof markers.
echo "wave4_zabbix_metric_definitions_liveness=PASS schema=001-028 malformed=terminal-reconciliation duplicate=terminal-reconciliation missing_host=terminal-reconciliation partial_mutation=none claim=retired"
