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
  sql/wave4/038_zabbix_metric_current_state_least_privilege.sql; do
  docker exec -i "$PG_CONTAINER" psql -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" < "$migration" >/dev/null
done

normal_ts="$(docker exec "$PG_CONTAINER" psql -Atq -U postgres -d "$PG_DATABASE" -c "SELECT monitoring.wave4_current_provider_timestamp_is_valid(1700000000,123)::int;")"
test "$normal_ts" = "1"

# BIGINT-valid but timestamptz-invalid provider time must be classified, never raise.
overflow_ts="$(docker exec "$PG_CONTAINER" psql -Atq -U postgres -d "$PG_DATABASE" -c "SELECT monitoring.wave4_current_provider_timestamp_is_valid(9223372036854775807,0)::int;")"
test "$overflow_ts" = "0"

# Recovery has only the dedicated function bridge, never direct operation DML.
recovery_acl="$(docker exec "$PG_CONTAINER" psql -Atq -U postgres -d "$PG_DATABASE" -c "SELECT has_table_privilege('jlmirror_wave4_recovery_authority','monitoring.monitoring_sync_operation','UPDATE')::int||':'||has_column_privilege('jlmirror_wave4_recovery_authority','monitoring.monitoring_sync_operation','state','UPDATE')::int||':'||has_column_privilege('jlmirror_wave4_recovery_authority','monitoring.monitoring_sync_operation','claim_token','UPDATE')::int||':'||has_function_privilege('jlmirror_wave4_recovery_authority','monitoring.wave4_terminalize_superseded_metric_current_state_claims(text,text,bigint)','EXECUTE')::int;" )"
test "$recovery_acl" = "0:0:0:1"

invoker_bridge="$(docker exec "$PG_CONTAINER" psql -Atq -U postgres -d "$PG_DATABASE" -c "SELECT has_function_privilege('jlmirror_wave4_metric_current_state_invoker','monitoring.wave4_terminalize_superseded_metric_current_state_claims(text,text,bigint)','EXECUTE')::int;")"
test "$invoker_bridge" = "0"

echo "wave4_zabbix_metric_current_state_hardening_postgres=PASS schema=001-038 provider_timestamp=exception-safe recovery_operation_dml=none recovery_bridge=narrow"
