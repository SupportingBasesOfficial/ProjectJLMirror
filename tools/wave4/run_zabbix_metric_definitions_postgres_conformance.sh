#!/usr/bin/env bash
set -euo pipefail
trap 'status=$?; echo "wave4_zabbix_metric_definitions_postgres=FAIL line=$LINENO status=$status" >&2; exit "$status"' ERR

POSTGRES_IMAGE="${POSTGRES_IMAGE:-postgres@sha256:4ef4dbc939d61acea57712655ddb4b4ab27419c913f94cca0cd57cb3ea3c2280}"
PG_CONTAINER="${PG_CONTAINER:-jlmirror-wave4-metric-definitions-postgres}"
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
  sql/wave4/025_zabbix_metric_definitions_drift_visibility.sql; do
  docker exec -i "$PG_CONTAINER" psql -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" < "$migration" >/dev/null
done

docker exec -i "$PG_CONTAINER" psql -q -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" <<'SQL'
CREATE ROLE wave4_runtime NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS;
GRANT USAGE ON SCHEMA monitoring TO wave4_runtime;
GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA monitoring TO wave4_runtime;
REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON monitoring.monitoring_host_inventory_runtime_admission FROM wave4_runtime;
REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON monitoring.monitoring_metric_definition_runtime_admission FROM wave4_runtime;
SQL

fp="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
scope='{"host_group_refs":["10"]}'

docker exec "$PG_CONTAINER" psql -q -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c "BEGIN; SET LOCAL ROLE wave4_runtime; SET LOCAL jlmirror.tenant_id='tenant-a'; SELECT * FROM monitoring.create_zabbix_source('tenant-a','create-metric','$fp','source-metric','generation-metric','binding-metric','validation-metric','audit-metric','principal-metric','human_browser_session','credential-generation-metric','authz-metric','correlation-metric','Metric Zabbix','provider-instance:metric','https://zabbix.example.test/zabbix','credential-binding:metric','$scope'::jsonb); SELECT monitoring_source_id FROM monitoring.claim_zabbix_initial_validation('tenant-a','validation-metric','validation-claim-metric'); SELECT monitoring.complete_zabbix_initial_validation('tenant-a','validation-metric','validation-claim-metric','validation-evidence-metric','binding-metric','provider-instance:metric','current','succeeded',NULL,'[\"10\"]'::jsonb,'[]'::jsonb,'egress-validation-metric','credential-generation-metric'); COMMIT;" >/dev/null

docker exec "$PG_CONTAINER" psql -q -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c "BEGIN; SET LOCAL jlmirror.tenant_id='tenant-a'; SELECT monitoring.reestablish_zabbix_host_inventory_poll_epoch('tenant-a','source-metric',1,2,'placement-host','recovery-host','admission-host'); COMMIT;" >/dev/null
normalized_host='{"technical_name":"host-101","display_name":"Host 101","inventory":{},"interfaces":[],"groups":[{"ref":"10","name":"Core"}],"templates":[],"tags":[]}'
host_fp="$(python3 -c 'import hashlib,json,sys; print(hashlib.sha256(json.dumps(json.loads(sys.argv[1]),separators=(",",":"),sort_keys=True,ensure_ascii=False).encode("utf-8")).hexdigest())' "$normalized_host")"
host="{\"monitoring_resource_id\":\"resource-metric-101\",\"provider_evidence_id\":\"provider-host-metric-101\",\"hostid\":\"101\",\"display_name\":\"Host 101\",\"evidence_fingerprint\":\"$host_fp\",\"normalized_evidence\":$normalized_host}"
docker exec "$PG_CONTAINER" psql -q -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c "BEGIN; SET LOCAL ROLE jlmirror_wave4_host_inventory_invoker; SET LOCAL jlmirror.tenant_id='tenant-a'; SELECT monitoring.enqueue_zabbix_host_inventory_sync('tenant-a','source-metric','host-op'); SELECT monitoring_source_id FROM monitoring.claim_zabbix_host_inventory('tenant-a','host-op','host-claim'); SELECT monitoring.complete_zabbix_host_inventory('tenant-a','host-op','host-claim','host-snapshot','binding-metric','provider-instance:metric','current','succeeded',NULL,true,'[$host]'::jsonb,'egress-host','credential-generation-metric'); COMMIT;" >/dev/null

if docker exec "$PG_CONTAINER" psql -q -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c "BEGIN; SET LOCAL ROLE wave4_runtime; SET LOCAL jlmirror.tenant_id='tenant-a'; SELECT monitoring.enqueue_zabbix_metric_definition_sync('tenant-a','source-metric','metric-public-forbidden'); COMMIT;" >/tmp/wave4-metric-public.out 2>&1; then
  echo "broad runtime unexpectedly invoked metric definition enqueue" >&2; exit 1
fi
grep -F "permission denied for function enqueue_zabbix_metric_definition_sync" /tmp/wave4-metric-public.out >/dev/null

metric_invoker_acl="$(docker exec "$PG_CONTAINER" psql -Atq -U postgres -d "$PG_DATABASE" -c "SELECT has_function_privilege('jlmirror_wave4_metric_definition_invoker','monitoring.enqueue_zabbix_metric_definition_sync(text,text,text)','EXECUTE')::int || ':' || has_function_privilege('jlmirror_wave4_metric_definition_invoker','monitoring.claim_zabbix_metric_definitions(text,text,text)','EXECUTE')::int || ':' || has_table_privilege('jlmirror_wave4_metric_definition_invoker','monitoring.metric_definition','INSERT')::int;")"
test "$metric_invoker_acl" = "1:1:0"

docker exec "$PG_CONTAINER" psql -q -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c "BEGIN; SET LOCAL ROLE jlmirror_wave4_metric_definition_invoker; SET LOCAL jlmirror.tenant_id='tenant-a'; SELECT monitoring.enqueue_zabbix_metric_definition_sync('tenant-a','source-metric','metric-op-1'); COMMIT;" >/dev/null

if docker exec "$PG_CONTAINER" psql -q -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c "BEGIN; SET LOCAL ROLE wave4_runtime; SET LOCAL jlmirror.tenant_id='tenant-a'; INSERT INTO monitoring.monitoring_metric_definition_snapshot_evidence(tenant_id,metric_definition_snapshot_evidence_id,monitoring_sync_operation_id,monitoring_source_id,source_instance_generation,configuration_revision,scope_revision,item_definition_poll_epoch,item_definition_poll_generation,snapshot_complete,item_count,operational_evidence_state,operation_state,failure_class) VALUES ('tenant-a','forged-snapshot','metric-op-1','source-metric','generation-metric',1,1,1,1,false,0,'incomplete','reconciliation_required','forged'); COMMIT;" >/tmp/wave4-metric-forged-snapshot.out 2>&1; then
  echo "broad runtime unexpectedly forged metric snapshot evidence" >&2; exit 1
fi
grep -F "Metric definition evidence creation requires guarded executor authority" /tmp/wave4-metric-forged-snapshot.out >/dev/null

if docker exec "$PG_CONTAINER" psql -q -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c "BEGIN; SET LOCAL ROLE jlmirror_wave4_metric_definition_invoker; SET LOCAL jlmirror.tenant_id='tenant-a'; SELECT monitoring_source_id FROM monitoring.claim_zabbix_metric_definitions('tenant-a','metric-op-1','metric-claim-1'); COMMIT;" >/tmp/wave4-metric-no-admission.out 2>&1; then
  echo "metric polling unexpectedly claimed without endpoint-specific recovery admission" >&2; exit 1
fi
grep -F "monitoring.metric_definition_recovery_admission_required" /tmp/wave4-metric-no-admission.out >/dev/null

host_epoch_before="$(docker exec "$PG_CONTAINER" psql -Atq -U postgres -d "$PG_DATABASE" -c "SELECT host_inventory_poll_epoch FROM monitoring.monitoring_source WHERE monitoring_source_id='source-metric';")"
host_poll_before="$(docker exec "$PG_CONTAINER" psql -Atq -U postgres -d "$PG_DATABASE" -c "SELECT host_inventory_poll_generation FROM monitoring.monitoring_source WHERE monitoring_source_id='source-metric';")"
docker exec "$PG_CONTAINER" psql -q -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c "BEGIN; SET LOCAL jlmirror.tenant_id='tenant-a'; SELECT monitoring.reestablish_metric_definition_runtime_admission('tenant-a','source-metric',2,'placement-metric','recovery-metric','admission-metric'); COMMIT;" >/dev/null
host_epoch_after="$(docker exec "$PG_CONTAINER" psql -Atq -U postgres -d "$PG_DATABASE" -c "SELECT host_inventory_poll_epoch FROM monitoring.monitoring_source WHERE monitoring_source_id='source-metric';")"
host_poll_after="$(docker exec "$PG_CONTAINER" psql -Atq -U postgres -d "$PG_DATABASE" -c "SELECT host_inventory_poll_generation FROM monitoring.monitoring_source WHERE monitoring_source_id='source-metric';")"
test "$host_epoch_before:$host_poll_before" = "$host_epoch_after:$host_poll_after"

docker exec "$PG_CONTAINER" psql -q -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c "BEGIN; SET LOCAL ROLE jlmirror_wave4_metric_definition_invoker; SET LOCAL jlmirror.tenant_id='tenant-a'; SELECT monitoring_source_id FROM monitoring.claim_zabbix_metric_definitions('tenant-a','metric-op-1','metric-claim-1'); SELECT monitoring.complete_zabbix_metric_definitions('tenant-a','metric-op-1','metric-claim-1','metric-snapshot-1','current','succeeded',NULL,'egress-metric','credential-generation-metric',true,'[{\"itemid\":\"5001\",\"hostid\":\"101\",\"name\":\"CPU utilization\",\"key\":\"system.cpu.util\",\"unit\":\"%\",\"native_value_type\":\"float\",\"operational_state\":\"enabled\"},{\"itemid\":\"5002\",\"hostid\":\"101\",\"name\":\"Agent state\",\"key\":\"agent.ping\",\"unit\":\"\",\"native_value_type\":\"unsigned\",\"operational_state\":\"disabled\"}]'::jsonb); COMMIT;" >/dev/null
metric_count="$(docker exec "$PG_CONTAINER" psql -Atq -U postgres -d "$PG_DATABASE" -c "SELECT count(*) FROM monitoring.metric_definition WHERE tenant_id='tenant-a' AND monitoring_source_id='source-metric';")"
test "$metric_count" = "2"
disabled_state="$(docker exec "$PG_CONTAINER" psql -Atq -U postgres -d "$PG_DATABASE" -c "SELECT d.definition_state || ':' || b.provider_operational_state FROM monitoring.metric_definition d JOIN monitoring.metric_definition_provider_binding b USING (tenant_id,metric_definition_id) WHERE b.provider_external_ref='5002';")"
test "$disabled_state" = "active:disabled"
value_kinds="$(docker exec "$PG_CONTAINER" psql -Atq -U postgres -d "$PG_DATABASE" -c "SELECT string_agg(b.provider_external_ref || '=' || d.value_kind,',' ORDER BY b.provider_external_ref) FROM monitoring.metric_definition d JOIN monitoring.metric_definition_provider_binding b USING (tenant_id,metric_definition_id) WHERE d.monitoring_source_id='source-metric';")"
test "$value_kinds" = "5001=number,5002=integer"

if docker exec "$PG_CONTAINER" psql -q -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c "BEGIN; SET LOCAL ROLE wave4_runtime; SET LOCAL jlmirror.tenant_id='tenant-a'; INSERT INTO monitoring.monitoring_metric_definition_provider_evidence(tenant_id,provider_evidence_id,metric_definition_snapshot_evidence_id,metric_definition_id,monitoring_resource_id,monitoring_source_id,source_instance_generation,provider_external_ref,provider_host_ref,evidence_fingerprint,normalized_evidence) SELECT 'tenant-a','forged-provider','metric-snapshot-1',b.metric_definition_id,b.monitoring_resource_id,b.monitoring_source_id,b.source_instance_generation,b.provider_external_ref,b.provider_host_ref,repeat('a',64),'{}'::jsonb FROM monitoring.metric_definition_provider_binding b WHERE b.provider_external_ref='5001'; COMMIT;" >/tmp/wave4-metric-forged-provider.out 2>&1; then
  echo "broad runtime unexpectedly forged metric provider evidence" >&2; exit 1
fi
grep -F "Metric definition evidence creation requires guarded executor authority" /tmp/wave4-metric-forged-provider.out >/dev/null

docker exec "$PG_CONTAINER" psql -q -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c "BEGIN; SET LOCAL ROLE jlmirror_wave4_metric_definition_invoker; SET LOCAL jlmirror.tenant_id='tenant-a'; SELECT monitoring.enqueue_zabbix_metric_definition_sync('tenant-a','source-metric','metric-op-drift'); SELECT monitoring_source_id FROM monitoring.claim_zabbix_metric_definitions('tenant-a','metric-op-drift','metric-claim-drift'); SELECT monitoring.complete_zabbix_metric_definitions('tenant-a','metric-op-drift','metric-claim-drift','metric-snapshot-drift','current','succeeded',NULL,'egress-metric','credential-generation-metric',true,'[{\"itemid\":\"5001\",\"hostid\":\"101\",\"name\":\"SHOULD NOT APPLY\",\"key\":\"system.cpu.util\",\"unit\":\"%\",\"native_value_type\":\"float\",\"operational_state\":\"enabled\"},{\"itemid\":\"5002\",\"hostid\":\"101\",\"name\":\"Agent state\",\"key\":\"agent.ping\",\"unit\":\"\",\"native_value_type\":\"float\",\"operational_state\":\"enabled\"}]'::jsonb); COMMIT;" >/dev/null
drift_outcome="$(docker exec "$PG_CONTAINER" psql -Atq -U postgres -d "$PG_DATABASE" -c "SELECT state || ':' || last_error_class FROM monitoring.monitoring_sync_operation WHERE monitoring_sync_operation_id='metric-op-drift';")"
test "$drift_outcome" = "reconciliation_required:provider.value_kind_drift"
name_after_drift="$(docker exec "$PG_CONTAINER" psql -Atq -U postgres -d "$PG_DATABASE" -c "SELECT d.name FROM monitoring.metric_definition d JOIN monitoring.metric_definition_provider_binding b USING (tenant_id,metric_definition_id) WHERE b.provider_external_ref='5001';")"
test "$name_after_drift" = "CPU utilization"
drift_visibility="$(docker exec "$PG_CONTAINER" psql -Atq -U postgres -d "$PG_DATABASE" -c "SELECT d.definition_evidence_state || ':' || b.evidence_state || ':' || d.value_kind FROM monitoring.metric_definition d JOIN monitoring.metric_definition_provider_binding b USING (tenant_id,metric_definition_id) WHERE b.provider_external_ref='5002';")"
test "$drift_visibility" = "reconciliation_required:reconciliation_required:integer"

docker exec "$PG_CONTAINER" psql -q -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c "BEGIN; SET LOCAL ROLE jlmirror_wave4_metric_definition_invoker; SET LOCAL jlmirror.tenant_id='tenant-a'; SELECT monitoring.enqueue_zabbix_metric_definition_sync('tenant-a','source-metric','metric-op-incomplete'); SELECT monitoring_source_id FROM monitoring.claim_zabbix_metric_definitions('tenant-a','metric-op-incomplete','metric-claim-incomplete'); SELECT monitoring.complete_zabbix_metric_definitions('tenant-a','metric-op-incomplete','metric-claim-incomplete','metric-snapshot-incomplete','incomplete','reconciliation_required','provider.snapshot_truncated','egress-metric','credential-generation-metric',false,'[{\"itemid\":\"5001\",\"hostid\":\"101\",\"name\":\"CPU utilization\",\"key\":\"system.cpu.util\",\"unit\":\"%\",\"native_value_type\":\"float\",\"operational_state\":\"enabled\"}]'::jsonb); COMMIT;" >/dev/null
still_active="$(docker exec "$PG_CONTAINER" psql -Atq -U postgres -d "$PG_DATABASE" -c "SELECT count(*) FROM monitoring.metric_definition d JOIN monitoring.metric_definition_provider_binding b USING (tenant_id,metric_definition_id) WHERE b.provider_external_ref='5002' AND d.definition_state='active';")"
test "$still_active" = "1"

docker exec "$PG_CONTAINER" psql -q -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c "BEGIN; SET LOCAL ROLE jlmirror_wave4_metric_definition_invoker; SET LOCAL jlmirror.tenant_id='tenant-a'; SELECT monitoring.enqueue_zabbix_metric_definition_sync('tenant-a','source-metric','metric-op-retire'); SELECT monitoring_source_id FROM monitoring.claim_zabbix_metric_definitions('tenant-a','metric-op-retire','metric-claim-retire'); SELECT monitoring.complete_zabbix_metric_definitions('tenant-a','metric-op-retire','metric-claim-retire','metric-snapshot-retire','current','succeeded',NULL,'egress-metric','credential-generation-metric',true,'[{\"itemid\":\"5001\",\"hostid\":\"101\",\"name\":\"CPU utilization\",\"key\":\"system.cpu.util\",\"unit\":\"%\",\"native_value_type\":\"float\",\"operational_state\":\"enabled\"}]'::jsonb); COMMIT;" >/dev/null
retired="$(docker exec "$PG_CONTAINER" psql -Atq -U postgres -d "$PG_DATABASE" -c "SELECT d.definition_state FROM monitoring.metric_definition d JOIN monitoring.metric_definition_provider_binding b USING (tenant_id,metric_definition_id) WHERE b.provider_external_ref='5002';")"
test "$retired" = "retired"

if docker exec "$PG_CONTAINER" psql -q -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c "BEGIN; SET LOCAL ROLE wave4_runtime; SET LOCAL jlmirror.tenant_id='tenant-a'; UPDATE monitoring.monitoring_source SET item_definition_poll_generation=item_definition_poll_generation+1 WHERE monitoring_source_id='source-metric'; COMMIT;" >/tmp/wave4-metric-direct-poll.out 2>&1; then
  echo "broad runtime unexpectedly advanced item poll authority" >&2; exit 1
fi
grep -F "Metric definition poll authority requires guarded executor authority" /tmp/wave4-metric-direct-poll.out >/dev/null

dump_acl="$(docker exec "$PG_CONTAINER" sh -lc "pg_dump -U postgres -d '$PG_DATABASE' --data-only --inserts --exclude-table-data=monitoring.monitoring_host_inventory_runtime_admission --exclude-table-data=monitoring.monitoring_metric_definition_runtime_admission | grep -c 'monitoring_metric_definition_runtime_admission' || true")"
test "$dump_acl" = "0"

echo "wave4_zabbix_metric_definitions_postgres=PASS schema=001-025 canonical_binding=separate disabled=active drift=visible+atomic_fail_closed evidence_insert=executor-only negative=authoritative poll_stream=independent recovery_admission=volatile"
