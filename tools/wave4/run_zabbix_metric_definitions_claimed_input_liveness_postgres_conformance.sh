#!/usr/bin/env bash
set -euo pipefail
trap 'status=$?; echo "wave4_zabbix_metric_definitions_claimed_input_liveness=FAIL line=$LINENO status=$status" >&2; exit "$status"' ERR

POSTGRES_IMAGE="${POSTGRES_IMAGE:-postgres@sha256:4ef4dbc939d61acea57712655ddb4b4ab27419c913f94cca0cd57cb3ea3c2280}"
PG_CONTAINER="${PG_CONTAINER:-jlmirror-wave4-metric-definitions-claimed-input-postgres}"
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
  sql/wave4/028_zabbix_metric_definitions_completion_liveness.sql \
  sql/wave4/029_zabbix_metric_definitions_claimed_input_liveness.sql; do
  docker exec -i "$PG_CONTAINER" psql -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" < "$migration" >/dev/null
done

echo "claimed_input_checkpoint=migrations-applied"
fp="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
scope='{"host_group_refs":["10"]}'
docker exec "$PG_CONTAINER" psql -q -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c "BEGIN; SET LOCAL jlmirror.tenant_id='tenant-a'; SELECT * FROM monitoring.create_zabbix_source('tenant-a','create-input-live','$fp','source-input-live','generation-input-live','binding-input-live','validation-input-live','audit-input-live','principal-input-live','human_browser_session','credential-generation-input-live','authz-input-live','correlation-input-live','Input Liveness Zabbix','provider-instance:input-live','https://zabbix.example.test/zabbix','credential-binding:input-live','$scope'::jsonb); SELECT monitoring_source_id FROM monitoring.claim_zabbix_initial_validation('tenant-a','validation-input-live','validation-claim-input-live'); SELECT monitoring.complete_zabbix_initial_validation('tenant-a','validation-input-live','validation-claim-input-live','validation-evidence-input-live','binding-input-live','provider-instance:input-live','current','succeeded',NULL,'[\"10\"]'::jsonb,'[]'::jsonb,'egress-validation-input-live','credential-generation-input-live'); COMMIT;" >/dev/null

docker exec "$PG_CONTAINER" psql -q -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c "BEGIN; SET LOCAL jlmirror.tenant_id='tenant-a'; SELECT monitoring.reestablish_zabbix_host_inventory_poll_epoch('tenant-a','source-input-live',1,2,'placement-host-input-live','recovery-host-input-live','admission-host-input-live'); COMMIT;" >/dev/null
normalized_host='{"technical_name":"host-101","display_name":"Host 101","inventory":{},"interfaces":[],"groups":[{"ref":"10","name":"Core"}],"templates":[],"tags":[]}'
host_fp="$(python3 -c 'import hashlib,json,sys; print(hashlib.sha256(json.dumps(json.loads(sys.argv[1]),separators=(",",":"),sort_keys=True,ensure_ascii=False).encode()).hexdigest())' "$normalized_host")"
host="{\"monitoring_resource_id\":\"resource-input-live-101\",\"provider_evidence_id\":\"provider-host-input-live-101\",\"hostid\":\"101\",\"display_name\":\"Host 101\",\"evidence_fingerprint\":\"$host_fp\",\"normalized_evidence\":$normalized_host}"
docker exec "$PG_CONTAINER" psql -q -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c "BEGIN; SET LOCAL ROLE jlmirror_wave4_host_inventory_invoker; SET LOCAL jlmirror.tenant_id='tenant-a'; SELECT monitoring.enqueue_zabbix_host_inventory_sync('tenant-a','source-input-live','host-input-live-op'); SELECT monitoring_source_id FROM monitoring.claim_zabbix_host_inventory('tenant-a','host-input-live-op','host-input-live-claim'); SELECT monitoring.complete_zabbix_host_inventory('tenant-a','host-input-live-op','host-input-live-claim','host-input-live-snapshot','binding-input-live','provider-instance:input-live','current','succeeded',NULL,true,'[$host]'::jsonb,'egress-host-input-live','credential-generation-input-live'); COMMIT;" >/dev/null

docker exec "$PG_CONTAINER" psql -q -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c "BEGIN; SET LOCAL jlmirror.tenant_id='tenant-a'; SELECT monitoring.reestablish_metric_definition_runtime_admission('tenant-a','source-input-live',2,'placement-metric-input-live','recovery-metric-input-live','admission-metric-input-live'); COMMIT;" >/dev/null

echo "claimed_input_checkpoint=fixture-ready"
helper_acl="$(docker exec "$PG_CONTAINER" psql -Atq -U postgres -d "$PG_DATABASE" -c "SELECT has_function_privilege('jlmirror_wave4_metric_definition_invoker','monitoring.complete_zabbix_metric_definitions_v028(text,text,text,text,text,text,text,text,text,boolean,jsonb)','EXECUTE')::int;")"
echo "claimed_input_helper_acl=$helper_acl"
test "$helper_acl" = "0"

claim_op() {
  local op="$1" claim="$2"
  docker exec "$PG_CONTAINER" psql -q -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c "BEGIN; SET LOCAL ROLE jlmirror_wave4_metric_definition_invoker; SET LOCAL jlmirror.tenant_id='tenant-a'; SELECT monitoring.enqueue_zabbix_metric_definition_sync('tenant-a','source-input-live','$op'); SELECT monitoring_source_id FROM monitoring.claim_zabbix_metric_definitions('tenant-a','$op','$claim'); COMMIT;" >/dev/null
}

assert_terminal() {
  local op="$1" expected="$2"
  actual="$(docker exec "$PG_CONTAINER" psql -Atq -U postgres -d "$PG_DATABASE" -c "SELECT state||':'||last_error_class||':'||(claim_token IS NULL)::int||':'||(completed_at IS NOT NULL)::int FROM monitoring.monitoring_sync_operation WHERE monitoring_sync_operation_id='$op';")"
  echo "claimed_input_case=$op actual=$actual expected=reconciliation_required:$expected:1:1"
  test "$actual" = "reconciliation_required:$expected:1:1"
}

claim_op 'metric-input-null' 'metric-input-null-claim'
docker exec "$PG_CONTAINER" psql -q -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c "BEGIN; SET LOCAL ROLE jlmirror_wave4_metric_definition_invoker; SET LOCAL jlmirror.tenant_id='tenant-a'; SELECT monitoring.complete_zabbix_metric_definitions('tenant-a','metric-input-null','metric-input-null-claim','metric-input-null-snapshot','current','succeeded',NULL,'egress-input-live','credential-generation-input-live',true,NULL::jsonb); COMMIT;" >/dev/null
assert_terminal 'metric-input-null' 'provider.protocol_invalid'

claim_op 'metric-input-object' 'metric-input-object-claim'
docker exec "$PG_CONTAINER" psql -q -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c "BEGIN; SET LOCAL ROLE jlmirror_wave4_metric_definition_invoker; SET LOCAL jlmirror.tenant_id='tenant-a'; SELECT monitoring.complete_zabbix_metric_definitions('tenant-a','metric-input-object','metric-input-object-claim','metric-input-object-snapshot','current','succeeded',NULL,'egress-input-live','credential-generation-input-live',true,'{}'::jsonb); COMMIT;" >/dev/null
assert_terminal 'metric-input-object' 'provider.protocol_invalid'

claim_op 'metric-input-shape' 'metric-input-shape-claim'
docker exec "$PG_CONTAINER" psql -q -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c "BEGIN; SET LOCAL ROLE jlmirror_wave4_metric_definition_invoker; SET LOCAL jlmirror.tenant_id='tenant-a'; SELECT monitoring.complete_zabbix_metric_definitions('tenant-a','metric-input-shape','metric-input-shape-claim','metric-input-shape-snapshot','current','succeeded',NULL,'egress-input-live','credential-generation-input-live',false,'[]'::jsonb); COMMIT;" >/dev/null
assert_terminal 'metric-input-shape' 'execution.invalid_completion_shape'

claim_op 'metric-input-no-snapshot' 'metric-input-no-snapshot-claim'
docker exec "$PG_CONTAINER" psql -q -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c "BEGIN; SET LOCAL ROLE jlmirror_wave4_metric_definition_invoker; SET LOCAL jlmirror.tenant_id='tenant-a'; SELECT monitoring.complete_zabbix_metric_definitions('tenant-a','metric-input-no-snapshot','metric-input-no-snapshot-claim',NULL,'current','succeeded',NULL,'egress-input-live','credential-generation-input-live',true,'[]'::jsonb); COMMIT;" >/dev/null
assert_terminal 'metric-input-no-snapshot' 'execution.invalid_completion_shape'
fallback_snapshot="$(docker exec "$PG_CONTAINER" psql -Atq -U postgres -d "$PG_DATABASE" -c "SELECT metric_definition_snapshot_evidence_id FROM monitoring.monitoring_sync_operation WHERE monitoring_sync_operation_id='metric-input-no-snapshot';")"
echo "claimed_input_fallback_snapshot=$fallback_snapshot"
[[ "$fallback_snapshot" == metric-reconciliation-* ]]
test "$(docker exec "$PG_CONTAINER" psql -Atq -U postgres -d "$PG_DATABASE" -c "SELECT count(*) FROM monitoring.monitoring_metric_definition_snapshot_evidence WHERE metric_definition_snapshot_evidence_id='$fallback_snapshot' AND item_count=0;")" = "1"

claim_op 'metric-input-overbound' 'metric-input-overbound-claim'
docker exec "$PG_CONTAINER" psql -q -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" <<'SQL' >/dev/null
BEGIN;
SET LOCAL ROLE jlmirror_wave4_metric_definition_invoker;
SET LOCAL jlmirror.tenant_id='tenant-a';
WITH payload AS (
    SELECT jsonb_agg('{}'::jsonb) AS items
      FROM generate_series(1,200001)
)
SELECT monitoring.complete_zabbix_metric_definitions(
    'tenant-a','metric-input-overbound','metric-input-overbound-claim',
    'metric-input-overbound-snapshot','current','succeeded',NULL,
    'egress-input-live','credential-generation-input-live',true,(SELECT items FROM payload)
);
COMMIT;
SQL
assert_terminal 'metric-input-overbound' 'provider.protocol_invalid'
overbound_count="$(docker exec "$PG_CONTAINER" psql -Atq -U postgres -d "$PG_DATABASE" -c "SELECT item_count FROM monitoring.monitoring_metric_definition_snapshot_evidence WHERE metric_definition_snapshot_evidence_id='metric-input-overbound-snapshot';")"
echo "claimed_input_overbound_accepted_item_count=$overbound_count"
test "$overbound_count" = "0"

canonical_count="$(docker exec "$PG_CONTAINER" psql -Atq -U postgres -d "$PG_DATABASE" -c "SELECT count(*) FROM monitoring.metric_definition WHERE monitoring_source_id='source-input-live';")"
echo "claimed_input_canonical_metric_count=$canonical_count"
test "$canonical_count" = "0"

echo "wave4_zabbix_metric_definitions_claimed_input_liveness=PASS schema=001-029 null=terminal nonarray=terminal overbound=terminal invalid_shape=terminal missing_snapshot=fallback-id helper=executor-only partial_mutation=none claim=retired"
