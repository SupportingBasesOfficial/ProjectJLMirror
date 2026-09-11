#!/usr/bin/env bash
set -euo pipefail
trap 'status=$?; echo "wave4_zabbix_metric_current_state_hardening_postgres=FAIL line=$LINENO status=$status" >&2; exit "$status"' ERR

POSTGRES_IMAGE="${POSTGRES_IMAGE:-postgres@sha256:4ef4dbc939d61acea57712655ddb4b4ab27419c913f94cca0cd57cb3ea3c2280}"
PG_CONTAINER="${PG_CONTAINER:-jlmirror-wave4-metric-current-state-hardening-postgres}"
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
  sql/wave4/038_zabbix_metric_current_state_least_privilege.sql \
  sql/wave4/039_zabbix_metric_current_state_owner_and_lock_order_hardening.sql; do
  docker exec -i "$PG_CONTAINER" psql -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" < "$migration" >/dev/null
done

normal_ts="$(docker exec "$PG_CONTAINER" psql -Atq -U postgres -d "$PG_DATABASE" -c "SELECT monitoring.wave4_current_provider_timestamp_is_valid(1700000000,123)::int;")"
test "$normal_ts" = "1"
overflow_ts="$(docker exec "$PG_CONTAINER" psql -Atq -U postgres -d "$PG_DATABASE" -c "SELECT monitoring.wave4_current_provider_timestamp_is_valid(9223372036854775807,0)::int;")"
test "$overflow_ts" = "0"

recovery_acl="$(docker exec "$PG_CONTAINER" psql -Atq -U postgres -d "$PG_DATABASE" -c "SELECT has_table_privilege('jlmirror_wave4_recovery_authority','monitoring.monitoring_sync_operation','UPDATE')::int||':'||has_column_privilege('jlmirror_wave4_recovery_authority','monitoring.monitoring_sync_operation','state','UPDATE')::int||':'||has_column_privilege('jlmirror_wave4_recovery_authority','monitoring.monitoring_sync_operation','claim_token','UPDATE')::int||':'||has_function_privilege('jlmirror_wave4_recovery_authority','monitoring.wave4_terminalize_superseded_metric_current_state_claims(text,text,bigint)','EXECUTE')::int;" )"
test "$recovery_acl" = "0:0:0:1"
invoker_bridge="$(docker exec "$PG_CONTAINER" psql -Atq -U postgres -d "$PG_DATABASE" -c "SELECT has_function_privilege('jlmirror_wave4_metric_current_state_invoker','monitoring.wave4_terminalize_superseded_metric_current_state_claims(text,text,bigint)','EXECUTE')::int;")"
test "$invoker_bridge" = "0"

owner_fk_count="$(docker exec "$PG_CONTAINER" psql -Atq -U postgres -d "$PG_DATABASE" -c "SELECT count(*) FROM pg_constraint WHERE conname IN ('metric_current_acceptance_definition_owner_fk','metric_current_acceptance_binding_owner_fk','metric_current_state_definition_owner_fk','metric_current_state_observation_owner_fk','metric_current_transition_definition_owner_fk','metric_current_transition_to_observation_owner_fk','metric_current_transition_from_observation_owner_fk') AND contype='f' AND convalidated;")"
test "$owner_fk_count" = "7"
owner_unique_count="$(docker exec "$PG_CONTAINER" psql -Atq -U postgres -d "$PG_DATABASE" -c "SELECT count(*) FROM pg_constraint WHERE conname IN ('metric_definition_binding_current_owner_ref_unique','metric_current_acceptance_owner_tuple_unique') AND contype='u' AND convalidated;")"
test "$owner_unique_count" = "2"

entry_acl="$(docker exec "$PG_CONTAINER" psql -Atq -U postgres -d "$PG_DATABASE" -c "SELECT has_function_privilege('jlmirror_wave4_metric_current_state_invoker','monitoring.claim_zabbix_metric_current_state(text,text,text)','EXECUTE')::int||':'||has_function_privilege('jlmirror_wave4_metric_current_state_invoker','monitoring.complete_zabbix_metric_current_state(text,text,text,jsonb)','EXECUTE')::int||':'||has_function_privilege('jlmirror_wave4_metric_current_state_invoker','monitoring.claim_zabbix_metric_current_state_v037_internal(text,text,text)','EXECUTE')::int||':'||has_function_privilege('jlmirror_wave4_metric_current_state_invoker','monitoring.complete_zabbix_metric_current_state_v036_internal(text,text,text,jsonb)','EXECUTE')::int;")"
test "$entry_acl" = "1:1:0:0"

claim_order="$(docker exec "$PG_CONTAINER" psql -Atq -U postgres -d "$PG_DATABASE" -c "WITH d AS (SELECT pg_get_functiondef('monitoring.claim_zabbix_metric_current_state(text,text,text)'::regprocedure) AS f) SELECT ((strpos(f,'FROM monitoring.monitoring_source')>0) AND (strpos(f,'FOR UPDATE')>strpos(f,'FROM monitoring.monitoring_source')) AND (strpos(f,'claim_zabbix_metric_current_state_v037_internal')>strpos(f,'FOR UPDATE')))::int FROM d;")"
test "$claim_order" = "1"
completion_order="$(docker exec "$PG_CONTAINER" psql -Atq -U postgres -d "$PG_DATABASE" -c "WITH d AS (SELECT pg_get_functiondef('monitoring.complete_zabbix_metric_current_state(text,text,text,jsonb)'::regprocedure) AS f) SELECT ((strpos(f,'FROM monitoring.monitoring_source')>0) AND (strpos(f,'FOR UPDATE')>strpos(f,'FROM monitoring.monitoring_source')) AND (strpos(f,'complete_zabbix_metric_current_state_v036_internal')>strpos(f,'FOR UPDATE')))::int FROM d;")"
test "$completion_order" = "1"

# Runtime smoke across the final 039 wrappers: valid source -> recovery admission ->
# enqueue -> public claim wrapper -> public completion wrapper.  Empty observations are
# valid positive-object semantics and should close the operation successfully.
docker exec -i "$PG_CONTAINER" psql -q -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" <<'SQL'
CREATE ROLE wave4_hardening_runtime NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS;
GRANT USAGE ON SCHEMA monitoring TO wave4_hardening_runtime;
GRANT SELECT,INSERT,UPDATE ON ALL TABLES IN SCHEMA monitoring TO wave4_hardening_runtime;
REVOKE INSERT,UPDATE,DELETE,TRUNCATE ON monitoring.monitoring_host_inventory_runtime_admission FROM wave4_hardening_runtime;
REVOKE INSERT,UPDATE,DELETE,TRUNCATE ON monitoring.monitoring_metric_definition_runtime_admission FROM wave4_hardening_runtime;
REVOKE INSERT,UPDATE,DELETE,TRUNCATE ON monitoring.monitoring_metric_current_state_runtime_admission FROM wave4_hardening_runtime;
SQL

fp="bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
scope='{"host_group_refs":["10"]}'
docker exec "$PG_CONTAINER" psql -q -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c "BEGIN; SET LOCAL ROLE wave4_hardening_runtime; SET LOCAL jlmirror.tenant_id='tenant-hard'; SELECT * FROM monitoring.create_zabbix_source('tenant-hard','create-hard','$fp','source-hard','generation-hard','binding-hard','validation-hard','audit-hard','principal-hard','human_browser_session','credential-generation-hard','authz-hard','correlation-hard','Hardening Zabbix','provider-instance:hard','https://zabbix.example.test/zabbix','credential-binding:hard','$scope'::jsonb); SELECT monitoring_source_id FROM monitoring.claim_zabbix_initial_validation('tenant-hard','validation-hard','validation-claim-hard'); SELECT monitoring.complete_zabbix_initial_validation('tenant-hard','validation-hard','validation-claim-hard','validation-evidence-hard','binding-hard','provider-instance:hard','current','succeeded',NULL,'[\"10\"]'::jsonb,'[]'::jsonb,'egress-validation-hard','credential-generation-hard'); COMMIT;" >/dev/null

docker exec "$PG_CONTAINER" psql -q -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c "BEGIN; SET LOCAL ROLE jlmirror_wave4_recovery_authority; SET LOCAL jlmirror.tenant_id='tenant-hard'; SELECT monitoring.reestablish_metric_current_state_runtime_admission('tenant-hard','source-hard',2,'placement-hard','recovery-hard','admission-hard'); COMMIT;" >/dev/null

docker exec "$PG_CONTAINER" psql -q -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c "BEGIN; SET LOCAL ROLE jlmirror_wave4_metric_current_state_invoker; SET LOCAL jlmirror.tenant_id='tenant-hard'; SELECT monitoring.enqueue_zabbix_metric_current_state_sync('tenant-hard','source-hard','current-hard-op'); SELECT monitoring_source_id FROM monitoring.claim_zabbix_metric_current_state('tenant-hard','current-hard-op','current-hard-claim'); COMMIT;" >/dev/null
final_result="$(docker exec "$PG_CONTAINER" psql -Atq -U postgres -d "$PG_DATABASE" -c "BEGIN; SET LOCAL ROLE jlmirror_wave4_metric_current_state_invoker; SET LOCAL jlmirror.tenant_id='tenant-hard'; SELECT monitoring.complete_zabbix_metric_current_state('tenant-hard','current-hard-op','current-hard-claim','[]'::jsonb); COMMIT;")"
test "$final_result" = "succeeded"
test "$(docker exec "$PG_CONTAINER" psql -Atq -U postgres -d "$PG_DATABASE" -c "SELECT state||':'||(claim_token IS NULL)::int FROM monitoring.monitoring_sync_operation WHERE tenant_id='tenant-hard' AND monitoring_sync_operation_id='current-hard-op';")" = "succeeded:1"

echo "wave4_zabbix_metric_current_state_hardening_postgres=PASS schema=001-039 provider_timestamp=exception-safe recovery_operation_dml=none recovery_bridge=narrow owner_tuple=storage-enforced lock_order=source-first internal_entrypoints=sealed final_entrypoints=runtime-proven"
