#!/usr/bin/env bash
set -euo pipefail
trap 'status=$?; echo "wave4_zabbix_metric_current_state_postgres=FAIL line=$LINENO status=$status" >&2; exit "$status"' ERR

POSTGRES_IMAGE="${POSTGRES_IMAGE:-postgres@sha256:4ef4dbc939d61acea57712655ddb4b4ab27419c913f94cca0cd57cb3ea3c2280}"
PG_CONTAINER="${PG_CONTAINER:-jlmirror-wave4-metric-current-state-postgres}"
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
  sql/wave4/029_zabbix_metric_definitions_claimed_input_liveness.sql \
  sql/wave4/030_zabbix_metric_current_state.sql \
  sql/wave4/031_zabbix_metric_current_state_completion.sql \
  sql/wave4/032_zabbix_metric_current_state_recovery_authority.sql \
  sql/wave4/033_zabbix_metric_current_state_provider_authority.sql \
  sql/wave4/034_zabbix_metric_current_state_recovery_lifecycle.sql \
  sql/wave4/035_zabbix_metric_current_state_claimed_input_liveness.sql \
  sql/wave4/036_zabbix_metric_current_state_completion_totalization.sql \
  sql/wave4/037_zabbix_metric_current_state_supersession.sql \
  sql/wave4/038_zabbix_metric_current_state_least_privilege.sql; do
  docker exec -i "$PG_CONTAINER" psql -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" < "$migration" >/dev/null
done

docker exec -i "$PG_CONTAINER" psql -q -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" <<'SQL'
CREATE ROLE wave4_runtime NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS;
GRANT USAGE ON SCHEMA monitoring TO wave4_runtime;
GRANT SELECT,INSERT,UPDATE ON ALL TABLES IN SCHEMA monitoring TO wave4_runtime;
REVOKE INSERT,UPDATE,DELETE,TRUNCATE ON monitoring.monitoring_host_inventory_runtime_admission FROM wave4_runtime;
REVOKE INSERT,UPDATE,DELETE,TRUNCATE ON monitoring.monitoring_metric_definition_runtime_admission FROM wave4_runtime;
REVOKE INSERT,UPDATE,DELETE,TRUNCATE ON monitoring.monitoring_metric_current_state_runtime_admission FROM wave4_runtime;
REVOKE INSERT,UPDATE,DELETE,TRUNCATE ON monitoring.monitoring_metric_observation_acceptance FROM wave4_runtime;
REVOKE INSERT,UPDATE,DELETE,TRUNCATE ON monitoring.metric_current_state FROM wave4_runtime;
REVOKE INSERT,UPDATE,DELETE,TRUNCATE ON monitoring.monitoring_metric_current_state_transition FROM wave4_runtime;
SQL

fp="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
scope='{"host_group_refs":["10"]}'
docker exec "$PG_CONTAINER" psql -q -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c "BEGIN; SET LOCAL ROLE wave4_runtime; SET LOCAL jlmirror.tenant_id='tenant-a'; SELECT * FROM monitoring.create_zabbix_source('tenant-a','create-current','$fp','source-current','generation-current','binding-current','validation-current','audit-current','principal-current','human_browser_session','credential-generation-current','authz-current','correlation-current','Current Zabbix','provider-instance:current','https://zabbix.example.test/zabbix','credential-binding:current','$scope'::jsonb); SELECT monitoring_source_id FROM monitoring.claim_zabbix_initial_validation('tenant-a','validation-current','validation-claim-current'); SELECT monitoring.complete_zabbix_initial_validation('tenant-a','validation-current','validation-claim-current','validation-evidence-current','binding-current','provider-instance:current','current','succeeded',NULL,'[\"10\"]'::jsonb,'[]'::jsonb,'egress-validation-current','credential-generation-current'); COMMIT;" >/dev/null

# Establish one canonical host through the accepted Host Inventory entrypoints.
docker exec "$PG_CONTAINER" psql -q -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c "BEGIN; SET LOCAL jlmirror.tenant_id='tenant-a'; SELECT monitoring.reestablish_zabbix_host_inventory_poll_epoch('tenant-a','source-current',1,2,'placement-host','recovery-host','admission-host'); COMMIT;" >/dev/null
normalized_host='{"technical_name":"host-101","display_name":"Host 101","inventory":{},"interfaces":[],"groups":[{"ref":"10","name":"Core"}],"templates":[],"tags":[]}'
host_fp="$(python3 -c 'import hashlib,json,sys; print(hashlib.sha256(json.dumps(json.loads(sys.argv[1]),separators=(",",":"),sort_keys=True,ensure_ascii=False).encode()).hexdigest())' "$normalized_host")"
host="{\"monitoring_resource_id\":\"resource-current-101\",\"provider_evidence_id\":\"provider-host-current-101\",\"hostid\":\"101\",\"display_name\":\"Host 101\",\"evidence_fingerprint\":\"$host_fp\",\"normalized_evidence\":$normalized_host}"
docker exec "$PG_CONTAINER" psql -q -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c "BEGIN; SET LOCAL ROLE jlmirror_wave4_host_inventory_invoker; SET LOCAL jlmirror.tenant_id='tenant-a'; SELECT monitoring.enqueue_zabbix_host_inventory_sync('tenant-a','source-current','host-current-op'); SELECT monitoring_source_id FROM monitoring.claim_zabbix_host_inventory('tenant-a','host-current-op','host-current-claim'); SELECT monitoring.complete_zabbix_host_inventory('tenant-a','host-current-op','host-current-claim','host-current-snapshot','binding-current','provider-instance:current','current','succeeded',NULL,true,'[$host]'::jsonb,'egress-host-current','credential-generation-current'); COMMIT;" >/dev/null

# Establish one enabled canonical metric definition through the accepted Item Definition entrypoints.
docker exec "$PG_CONTAINER" psql -q -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c "BEGIN; SET LOCAL ROLE jlmirror_wave4_metric_definition_invoker; SET LOCAL jlmirror.tenant_id='tenant-a'; SELECT monitoring.enqueue_zabbix_metric_definition_sync('tenant-a','source-current','metric-current-op'); COMMIT;" >/dev/null
if docker exec "$PG_CONTAINER" psql -q -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c "BEGIN; SET LOCAL ROLE jlmirror_wave4_metric_definition_invoker; SET LOCAL jlmirror.tenant_id='tenant-a'; SELECT monitoring_source_id FROM monitoring.claim_zabbix_metric_definitions('tenant-a','metric-current-op','metric-current-claim'); COMMIT;" >/tmp/current-no-item-admission 2>&1; then exit 1; fi
grep -F "monitoring.metric_definition_recovery_admission_required" /tmp/current-no-item-admission >/dev/null
docker exec "$PG_CONTAINER" psql -q -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c "BEGIN; SET LOCAL jlmirror.tenant_id='tenant-a'; SELECT monitoring.reestablish_metric_definition_runtime_admission('tenant-a','source-current',2,'placement-item','recovery-item','admission-item'); COMMIT;" >/dev/null
docker exec "$PG_CONTAINER" psql -q -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c "BEGIN; SET LOCAL ROLE jlmirror_wave4_metric_definition_invoker; SET LOCAL jlmirror.tenant_id='tenant-a'; SELECT monitoring_source_id FROM monitoring.claim_zabbix_metric_definitions('tenant-a','metric-current-op','metric-current-claim'); SELECT monitoring.complete_zabbix_metric_definitions('tenant-a','metric-current-op','metric-current-claim','metric-current-snapshot','current','succeeded',NULL,'egress-metric-current','credential-generation-current',true,'[{\"itemid\":\"5001\",\"hostid\":\"101\",\"name\":\"CPU utilization\",\"key\":\"system.cpu.util\",\"unit\":\"%\",\"native_value_type\":\"float\",\"operational_state\":\"enabled\"}]'::jsonb); COMMIT;" >/dev/null
metric_id="$(docker exec "$PG_CONTAINER" psql -Atq -U postgres -d "$PG_DATABASE" -c "SELECT d.metric_definition_id FROM monitoring.metric_definition d JOIN monitoring.metric_definition_provider_binding b USING(tenant_id,metric_definition_id) WHERE d.tenant_id='tenant-a' AND b.provider_external_ref='5001';")"
test -n "$metric_id"

# Invoker can use guarded functions but cannot fabricate owner state directly.
acl="$(docker exec "$PG_CONTAINER" psql -Atq -U postgres -d "$PG_DATABASE" -c "SELECT has_function_privilege('jlmirror_wave4_metric_current_state_invoker','monitoring.enqueue_zabbix_metric_current_state_sync(text,text,text)','EXECUTE')::int||':'||has_function_privilege('jlmirror_wave4_metric_current_state_invoker','monitoring.complete_zabbix_metric_current_state(text,text,text,jsonb)','EXECUTE')::int||':'||has_table_privilege('jlmirror_wave4_metric_current_state_invoker','monitoring.metric_current_state','INSERT')::int||':'||has_table_privilege('jlmirror_wave4_metric_current_state_invoker','monitoring.monitoring_metric_observation_acceptance','INSERT')::int;")"
test "$acl" = "1:1:0:0"
source_acl="$(docker exec "$PG_CONTAINER" psql -Atq -U postgres -d "$PG_DATABASE" -c "SELECT has_table_privilege('jlmirror_wave4_metric_current_state_executor','monitoring.monitoring_source','INSERT')::int||':'||has_column_privilege('jlmirror_wave4_metric_current_state_executor','monitoring.monitoring_source','current_state_poll_generation','UPDATE')::int||':'||has_column_privilege('jlmirror_wave4_metric_current_state_executor','monitoring.monitoring_source','active_source_instance_generation','UPDATE')::int;")"
test "$source_acl" = "0:1:0"

# Current work is fail-closed until this independent stream is explicitly admitted.
docker exec "$PG_CONTAINER" psql -q -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c "BEGIN; SET LOCAL ROLE jlmirror_wave4_metric_current_state_invoker; SET LOCAL jlmirror.tenant_id='tenant-a'; SELECT monitoring.enqueue_zabbix_metric_current_state_sync('tenant-a','source-current','current-op-1'); COMMIT;" >/dev/null
if docker exec "$PG_CONTAINER" psql -q -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c "BEGIN; SET LOCAL ROLE jlmirror_wave4_metric_current_state_invoker; SET LOCAL jlmirror.tenant_id='tenant-a'; SELECT monitoring_source_id FROM monitoring.claim_zabbix_metric_current_state('tenant-a','current-op-1','current-claim-1'); COMMIT;" >/tmp/current-no-admission 2>&1; then exit 1; fi
grep -F "monitoring.metric_current_state_recovery_admission_required" /tmp/current-no-admission >/dev/null

host_item_before="$(docker exec "$PG_CONTAINER" psql -Atq -U postgres -d "$PG_DATABASE" -c "SELECT host_inventory_poll_epoch||':'||host_inventory_poll_generation||':'||item_definition_poll_epoch||':'||item_definition_poll_generation FROM monitoring.monitoring_source WHERE monitoring_source_id='source-current';")"
docker exec "$PG_CONTAINER" psql -q -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c "BEGIN; SET LOCAL ROLE jlmirror_wave4_recovery_authority; SET LOCAL jlmirror.tenant_id='tenant-a'; SELECT monitoring.reestablish_metric_current_state_runtime_admission('tenant-a','source-current',2,'placement-current','recovery-current','admission-current'); COMMIT;" >/dev/null
host_item_after="$(docker exec "$PG_CONTAINER" psql -Atq -U postgres -d "$PG_DATABASE" -c "SELECT host_inventory_poll_epoch||':'||host_inventory_poll_generation||':'||item_definition_poll_epoch||':'||item_definition_poll_generation FROM monitoring.monitoring_source WHERE monitoring_source_id='source-current';")"
test "$host_item_before" = "$host_item_after"

claim_row="$(docker exec "$PG_CONTAINER" psql -Atq -F '|' -U postgres -d "$PG_DATABASE" -c "BEGIN; SET LOCAL ROLE jlmirror_wave4_metric_current_state_invoker; SET LOCAL jlmirror.tenant_id='tenant-a'; SELECT monitoring_source_id||'|'||provider_instance_ref||'|'||provider_base_url||'|'||credential_binding_ref FROM monitoring.claim_zabbix_metric_current_state('tenant-a','current-op-1','current-claim-1'); COMMIT;")"
test "$claim_row" = "source-current|provider-instance:current|https://zabbix.example.test/zabbix|credential-binding:current"
target_row="$(docker exec "$PG_CONTAINER" psql -Atq -F '|' -U postgres -d "$PG_DATABASE" -c "BEGIN; SET LOCAL ROLE jlmirror_wave4_metric_current_state_invoker; SET LOCAL jlmirror.tenant_id='tenant-a'; SELECT provider_external_ref||'|'||value_kind FROM monitoring.list_zabbix_metric_current_targets('tenant-a','current-op-1','current-claim-1',NULL,100); COMMIT;")"
test "$target_row" = "5001|number"

obs1="[{\"metric_definition_id\":\"$metric_id\",\"provider_external_ref\":\"5001\",\"observation_id\":\"obs-current-1\",\"provider_clock\":1700000000,\"provider_ns\":1,\"value_kind\":\"number\",\"canonical_value\":42.5}]"
docker exec "$PG_CONTAINER" psql -q -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c "BEGIN; SET LOCAL ROLE jlmirror_wave4_metric_current_state_invoker; SET LOCAL jlmirror.tenant_id='tenant-a'; SELECT monitoring.complete_zabbix_metric_current_state('tenant-a','current-op-1','current-claim-1','$obs1'::jsonb); COMMIT;" >/dev/null
test "$(docker exec "$PG_CONTAINER" psql -Atq -U postgres -d "$PG_DATABASE" -c "SELECT count(*)||':'||min(history_projection_state) FROM monitoring.monitoring_metric_observation_acceptance WHERE tenant_id='tenant-a';")" = "1:pending"
test "$(docker exec "$PG_CONTAINER" psql -Atq -U postgres -d "$PG_DATABASE" -c "SELECT current_observation_id||':'||canonical_value::text||':'||projection_revision||':'||evidence_state FROM monitoring.metric_current_state WHERE tenant_id='tenant-a' AND metric_definition_id='$metric_id';")" = "obs-current-1:42.5:1:current"
test "$(docker exec "$PG_CONTAINER" psql -Atq -U postgres -d "$PG_DATABASE" -c "SELECT count(*) FROM monitoring.monitoring_metric_current_state_transition WHERE tenant_id='tenant-a';")" = "1"

# Exact provider observation replay is idempotent even if the caller proposes another platform ID.
docker exec "$PG_CONTAINER" psql -q -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c "BEGIN; SET LOCAL ROLE jlmirror_wave4_metric_current_state_invoker; SET LOCAL jlmirror.tenant_id='tenant-a'; SELECT monitoring.enqueue_zabbix_metric_current_state_sync('tenant-a','source-current','current-op-2'); SELECT monitoring_source_id FROM monitoring.claim_zabbix_metric_current_state('tenant-a','current-op-2','current-claim-2'); SELECT monitoring.complete_zabbix_metric_current_state('tenant-a','current-op-2','current-claim-2','[{\"metric_definition_id\":\"$metric_id\",\"provider_external_ref\":\"5001\",\"observation_id\":\"obs-replay-proposed\",\"provider_clock\":1700000000,\"provider_ns\":1,\"value_kind\":\"number\",\"canonical_value\":42.5}]'::jsonb); COMMIT;" >/dev/null
test "$(docker exec "$PG_CONTAINER" psql -Atq -U postgres -d "$PG_DATABASE" -c "SELECT count(*) FROM monitoring.monitoring_metric_observation_acceptance WHERE tenant_id='tenant-a';")" = "1"
test "$(docker exec "$PG_CONTAINER" psql -Atq -U postgres -d "$PG_DATABASE" -c "SELECT current_observation_id||':'||projection_revision FROM monitoring.metric_current_state WHERE tenant_id='tenant-a' AND metric_definition_id='$metric_id';")" = "obs-current-1:1"

# Distinct observation with same semantic value owns History obligation but emits no current transition.
docker exec "$PG_CONTAINER" psql -q -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c "BEGIN; SET LOCAL ROLE jlmirror_wave4_metric_current_state_invoker; SET LOCAL jlmirror.tenant_id='tenant-a'; SELECT monitoring.enqueue_zabbix_metric_current_state_sync('tenant-a','source-current','current-op-3'); SELECT monitoring_source_id FROM monitoring.claim_zabbix_metric_current_state('tenant-a','current-op-3','current-claim-3'); SELECT monitoring.complete_zabbix_metric_current_state('tenant-a','current-op-3','current-claim-3','[{\"metric_definition_id\":\"$metric_id\",\"provider_external_ref\":\"5001\",\"observation_id\":\"obs-current-2\",\"provider_clock\":1700000010,\"provider_ns\":2,\"value_kind\":\"number\",\"canonical_value\":42.5}]'::jsonb); COMMIT;" >/dev/null
test "$(docker exec "$PG_CONTAINER" psql -Atq -U postgres -d "$PG_DATABASE" -c "SELECT count(*)||':'||count(*) FILTER (WHERE history_projection_state='pending') FROM monitoring.monitoring_metric_observation_acceptance WHERE tenant_id='tenant-a';")" = "2:2"
test "$(docker exec "$PG_CONTAINER" psql -Atq -U postgres -d "$PG_DATABASE" -c "SELECT current_observation_id||':'||projection_revision FROM monitoring.metric_current_state WHERE tenant_id='tenant-a' AND metric_definition_id='$metric_id';")" = "obs-current-2:2"
test "$(docker exec "$PG_CONTAINER" psql -Atq -U postgres -d "$PG_DATABASE" -c "SELECT count(*) FROM monitoring.monitoring_metric_current_state_transition WHERE tenant_id='tenant-a';")" = "1"

# A later valid poll may advance semantic value even when provider event time moves backwards.
docker exec "$PG_CONTAINER" psql -q -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c "BEGIN; SET LOCAL ROLE jlmirror_wave4_metric_current_state_invoker; SET LOCAL jlmirror.tenant_id='tenant-a'; SELECT monitoring.enqueue_zabbix_metric_current_state_sync('tenant-a','source-current','current-op-4'); SELECT monitoring_source_id FROM monitoring.claim_zabbix_metric_current_state('tenant-a','current-op-4','current-claim-4'); SELECT monitoring.complete_zabbix_metric_current_state('tenant-a','current-op-4','current-claim-4','[{\"metric_definition_id\":\"$metric_id\",\"provider_external_ref\":\"5001\",\"observation_id\":\"obs-current-3\",\"provider_clock\":1699999990,\"provider_ns\":3,\"value_kind\":\"number\",\"canonical_value\":43.5}]'::jsonb); COMMIT;" >/dev/null
test "$(docker exec "$PG_CONTAINER" psql -Atq -U postgres -d "$PG_DATABASE" -c "SELECT current_observation_id||':'||canonical_value::text||':'||projection_revision FROM monitoring.metric_current_state WHERE tenant_id='tenant-a' AND metric_definition_id='$metric_id';")" = "obs-current-3:43.5:3"
test "$(docker exec "$PG_CONTAINER" psql -Atq -U postgres -d "$PG_DATABASE" -c "SELECT count(*) FROM monitoring.monitoring_metric_current_state_transition WHERE tenant_id='tenant-a';")" = "2"

# Replaying the older accepted observation under a later poll cannot regress Current.
docker exec "$PG_CONTAINER" psql -q -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c "BEGIN; SET LOCAL ROLE jlmirror_wave4_metric_current_state_invoker; SET LOCAL jlmirror.tenant_id='tenant-a'; SELECT monitoring.enqueue_zabbix_metric_current_state_sync('tenant-a','source-current','current-op-5'); SELECT monitoring_source_id FROM monitoring.claim_zabbix_metric_current_state('tenant-a','current-op-5','current-claim-5'); SELECT monitoring.complete_zabbix_metric_current_state('tenant-a','current-op-5','current-claim-5','[{\"metric_definition_id\":\"$metric_id\",\"provider_external_ref\":\"5001\",\"observation_id\":\"obs-old-replay\",\"provider_clock\":1700000000,\"provider_ns\":1,\"value_kind\":\"number\",\"canonical_value\":42.5}]'::jsonb); COMMIT;" >/dev/null
test "$(docker exec "$PG_CONTAINER" psql -Atq -U postgres -d "$PG_DATABASE" -c "SELECT current_observation_id||':'||canonical_value::text||':'||projection_revision FROM monitoring.metric_current_state WHERE tenant_id='tenant-a' AND metric_definition_id='$metric_id';")" = "obs-current-3:43.5:3"

# Claimed-input faults terminalize instead of orphaning work.
for case_name in null object badvalue collision; do
  op="bad-$case_name"; claim="claim-$case_name"
  docker exec "$PG_CONTAINER" psql -q -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c "BEGIN; SET LOCAL ROLE jlmirror_wave4_metric_current_state_invoker; SET LOCAL jlmirror.tenant_id='tenant-a'; SELECT monitoring.enqueue_zabbix_metric_current_state_sync('tenant-a','source-current','$op'); SELECT monitoring_source_id FROM monitoring.claim_zabbix_metric_current_state('tenant-a','$op','$claim'); COMMIT;" >/dev/null
  case "$case_name" in
    null) payload="NULL::jsonb" ;;
    object) payload="'{}'::jsonb" ;;
    badvalue) payload="'[{\"metric_definition_id\":\"$metric_id\",\"provider_external_ref\":\"5001\",\"observation_id\":\"bad-value-id\",\"provider_clock\":1700000200,\"provider_ns\":1,\"value_kind\":\"number\",\"canonical_value\":\"not-a-number\"}]'::jsonb" ;;
    collision) payload="'[{\"metric_definition_id\":\"$metric_id\",\"provider_external_ref\":\"5001\",\"observation_id\":\"obs-current-1\",\"provider_clock\":1700000201,\"provider_ns\":1,\"value_kind\":\"number\",\"canonical_value\":99}]'::jsonb" ;;
  esac
  result="$(docker exec "$PG_CONTAINER" psql -Atq -U postgres -d "$PG_DATABASE" -c "BEGIN; SET LOCAL ROLE jlmirror_wave4_metric_current_state_invoker; SET LOCAL jlmirror.tenant_id='tenant-a'; SELECT monitoring.complete_zabbix_metric_current_state('tenant-a','$op','$claim',$payload); COMMIT;")"
  test "$result" = "reconciliation_required"
  test "$(docker exec "$PG_CONTAINER" psql -Atq -U postgres -d "$PG_DATABASE" -c "SELECT state||':'||coalesce(last_error_class,'')||':'||(claim_token IS NULL)::int FROM monitoring.monitoring_sync_operation WHERE tenant_id='tenant-a' AND monitoring_sync_operation_id='$op';")" = "reconciliation_required:provider.protocol_invalid:1"
done

# Over-bound input also terminalizes without iterating/mutating provider evidence.
docker exec "$PG_CONTAINER" psql -q -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c "BEGIN; SET LOCAL ROLE jlmirror_wave4_metric_current_state_invoker; SET LOCAL jlmirror.tenant_id='tenant-a'; SELECT monitoring.enqueue_zabbix_metric_current_state_sync('tenant-a','source-current','bad-overbound'); SELECT monitoring_source_id FROM monitoring.claim_zabbix_metric_current_state('tenant-a','bad-overbound','claim-overbound'); COMMIT;" >/dev/null
over_result="$(docker exec "$PG_CONTAINER" psql -Atq -U postgres -d "$PG_DATABASE" -c "BEGIN; SET LOCAL ROLE jlmirror_wave4_metric_current_state_invoker; SET LOCAL jlmirror.tenant_id='tenant-a'; WITH payload AS (SELECT jsonb_agg(1) AS v FROM generate_series(1,200001)) SELECT monitoring.complete_zabbix_metric_current_state('tenant-a','bad-overbound','claim-overbound',payload.v) FROM payload; COMMIT;")"
test "$over_result" = "reconciliation_required"

# A newer normal claim supersedes the previous in-flight generation before provider work continues.
docker exec "$PG_CONTAINER" psql -q -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c "BEGIN; SET LOCAL ROLE jlmirror_wave4_metric_current_state_invoker; SET LOCAL jlmirror.tenant_id='tenant-a'; SELECT monitoring.enqueue_zabbix_metric_current_state_sync('tenant-a','source-current','supersede-a'); SELECT monitoring.enqueue_zabbix_metric_current_state_sync('tenant-a','source-current','supersede-b'); SELECT monitoring_source_id FROM monitoring.claim_zabbix_metric_current_state('tenant-a','supersede-a','claim-supersede-a'); SELECT monitoring_source_id FROM monitoring.claim_zabbix_metric_current_state('tenant-a','supersede-b','claim-supersede-b'); COMMIT;" >/dev/null
test "$(docker exec "$PG_CONTAINER" psql -Atq -U postgres -d "$PG_DATABASE" -c "SELECT state||':'||last_error_class||':'||(claim_token IS NULL)::int FROM monitoring.monitoring_sync_operation WHERE tenant_id='tenant-a' AND monitoring_sync_operation_id='supersede-a';")" = "reconciliation_required:execution.superseded_current_state_poll_authority:1"
if docker exec "$PG_CONTAINER" psql -q -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c "BEGIN; SET LOCAL ROLE jlmirror_wave4_metric_current_state_invoker; SET LOCAL jlmirror.tenant_id='tenant-a'; SELECT * FROM monitoring.list_zabbix_metric_current_targets('tenant-a','supersede-a','claim-supersede-a',NULL,100); COMMIT;" >/tmp/current-stale-target 2>&1; then exit 1; fi
grep -F "monitoring.metric_current_state_claim_not_current" /tmp/current-stale-target >/dev/null
docker exec "$PG_CONTAINER" psql -q -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c "BEGIN; SET LOCAL ROLE jlmirror_wave4_metric_current_state_invoker; SET LOCAL jlmirror.tenant_id='tenant-a'; SELECT monitoring.complete_zabbix_metric_current_state('tenant-a','supersede-b','claim-supersede-b','[]'::jsonb); COMMIT;" >/dev/null

# Recovery advances only the Current epoch and terminalizes old Current claims.
docker exec "$PG_CONTAINER" psql -q -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c "BEGIN; SET LOCAL ROLE jlmirror_wave4_metric_current_state_invoker; SET LOCAL jlmirror.tenant_id='tenant-a'; SELECT monitoring.enqueue_zabbix_metric_current_state_sync('tenant-a','source-current','recovery-stale'); SELECT monitoring_source_id FROM monitoring.claim_zabbix_metric_current_state('tenant-a','recovery-stale','recovery-stale-claim'); COMMIT;" >/dev/null
other_streams_before="$(docker exec "$PG_CONTAINER" psql -Atq -U postgres -d "$PG_DATABASE" -c "SELECT host_inventory_poll_epoch||':'||host_inventory_poll_generation||':'||item_definition_poll_epoch||':'||item_definition_poll_generation FROM monitoring.monitoring_source WHERE monitoring_source_id='source-current';")"
current_generation_before="$(docker exec "$PG_CONTAINER" psql -Atq -U postgres -d "$PG_DATABASE" -c "SELECT current_state_poll_generation FROM monitoring.monitoring_source WHERE monitoring_source_id='source-current';")"
docker exec "$PG_CONTAINER" psql -q -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c "BEGIN; SET LOCAL ROLE jlmirror_wave4_recovery_authority; SET LOCAL jlmirror.tenant_id='tenant-a'; SELECT monitoring.reestablish_metric_current_state_runtime_admission('tenant-a','source-current',3,'placement-current-r2','recovery-current-r2','admission-current-r2'); COMMIT;" >/dev/null
other_streams_after="$(docker exec "$PG_CONTAINER" psql -Atq -U postgres -d "$PG_DATABASE" -c "SELECT host_inventory_poll_epoch||':'||host_inventory_poll_generation||':'||item_definition_poll_epoch||':'||item_definition_poll_generation FROM monitoring.monitoring_source WHERE monitoring_source_id='source-current';")"
test "$other_streams_before" = "$other_streams_after"
test "$(docker exec "$PG_CONTAINER" psql -Atq -U postgres -d "$PG_DATABASE" -c "SELECT current_state_poll_epoch||':'||current_state_poll_generation FROM monitoring.monitoring_source WHERE monitoring_source_id='source-current';")" = "3:$current_generation_before"
test "$(docker exec "$PG_CONTAINER" psql -Atq -U postgres -d "$PG_DATABASE" -c "SELECT state||':'||last_error_class||':'||(claim_token IS NULL)::int FROM monitoring.monitoring_sync_operation WHERE tenant_id='tenant-a' AND monitoring_sync_operation_id='recovery-stale';")" = "reconciliation_required:execution.superseded_current_state_poll_authority:1"
if docker exec "$PG_CONTAINER" psql -q -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c "BEGIN; SET LOCAL ROLE jlmirror_wave4_metric_current_state_invoker; SET LOCAL jlmirror.tenant_id='tenant-a'; SELECT monitoring.complete_zabbix_metric_current_state('tenant-a','recovery-stale','recovery-stale-claim','[]'::jsonb); COMMIT;" >/tmp/current-recovery-stale 2>&1; then exit 1; fi
grep -F "monitoring.metric_current_state_completion_not_claimed" /tmp/current-recovery-stale >/dev/null

# History remains an obligation only; no metric_observation materialization exists in this slice.
test "$(docker exec "$PG_CONTAINER" psql -Atq -U postgres -d "$PG_DATABASE" -c "SELECT (to_regclass('monitoring.metric_observation') IS NULL)::int;")" = "1"
test "$(docker exec "$PG_CONTAINER" psql -Atq -U postgres -d "$PG_DATABASE" -c "SELECT count(*) FILTER (WHERE history_projection_state='pending') FROM monitoring.monitoring_metric_observation_acceptance WHERE tenant_id='tenant-a';")" = "3"

# Final current value survived replay, malformed inputs, supersession and recovery unchanged.
test "$(docker exec "$PG_CONTAINER" psql -Atq -U postgres -d "$PG_DATABASE" -c "SELECT current_observation_id||':'||canonical_value::text||':'||projection_revision FROM monitoring.metric_current_state WHERE tenant_id='tenant-a' AND metric_definition_id='$metric_id';")" = "obs-current-3:43.5:3"

echo "wave4_zabbix_metric_current_state_postgres=PASS schema=001-038 durable_acceptance=pending-history exact_replay=idempotent same_value=no-transition backward_provider_time=allowed-by-fence claimed_input=terminalized supersession=single-winner recovery=stream-local"
