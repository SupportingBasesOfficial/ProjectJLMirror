#!/usr/bin/env bash
set -euo pipefail
trap 'status=$?; echo "wave4_zabbix_host_inventory_postgres=FAIL line=$LINENO status=$status" >&2; exit "$status"' ERR

POSTGRES_IMAGE="${POSTGRES_IMAGE:-postgres@sha256:4ef4dbc939d61acea57712655ddb4b4ab27419c913f94cca0cd57cb3ea3c2280}"
PG_CONTAINER="${PG_CONTAINER:-jlmirror-wave4-host-inventory-postgres}"
PG_PASSWORD="${PG_PASSWORD:-wave4-monitoring-password}"
PG_DATABASE="${PG_DATABASE:-jlmirror}"

cleanup() { docker rm -f "$PG_CONTAINER" >/dev/null 2>&1 || true; }
trap cleanup EXIT
cleanup

docker pull "$POSTGRES_IMAGE" >/dev/null
docker image inspect "$POSTGRES_IMAGE" --format '{{range .RepoDigests}}{{println .}}{{end}}' | grep -Fx "$POSTGRES_IMAGE" >/dev/null

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
  sql/wave4/006_zabbix_host_inventory_boundary_hardening.sql; do
  docker exec -i "$PG_CONTAINER" psql -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" < "$migration" >/dev/null
done

docker exec -i "$PG_CONTAINER" psql -q -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" <<'SQL'
CREATE ROLE wave4_runtime NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS;
GRANT USAGE ON SCHEMA monitoring TO wave4_runtime;
GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA monitoring TO wave4_runtime;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA monitoring TO wave4_runtime;
SQL

rls_flags="$(docker exec "$PG_CONTAINER" psql -Atq -U postgres -d "$PG_DATABASE" -c "SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='monitoring' AND c.relname IN ('monitoring_source','monitoring_source_generation','monitoring_sync_operation','monitoring_source_create_idempotency','monitoring_source_audit_evidence','monitoring_source_validation_evidence','monitoring_resource','monitoring_host_inventory_snapshot_evidence','monitoring_resource_provider_evidence') AND c.relrowsecurity AND c.relforcerowsecurity;")"
test "$rls_flags" = "9"

missing_context="$(docker exec "$PG_CONTAINER" psql -Atq -U postgres -d "$PG_DATABASE" -c "BEGIN; SET LOCAL ROLE wave4_runtime; SELECT count(*) FROM monitoring.monitoring_resource; COMMIT;" | tail -n1)"
test "$missing_context" = "0"

fp="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
scope='{"host_group_refs":["10","20"]}'
create="$(docker exec "$PG_CONTAINER" psql -Atq -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c "BEGIN; SET LOCAL ROLE wave4_runtime; SET LOCAL jlmirror.tenant_id='tenant-a'; SELECT * FROM monitoring.create_zabbix_source('tenant-a','create-a','$fp','source-a','generation-a','binding-a','validation-a','audit-a','principal-a','human_browser_session','credential-generation-a','authz-a','correlation-a','Company A Zabbix','provider-instance:a','https://zabbix.example.test/zabbix','credential-binding:a','$scope'::jsonb); COMMIT;" | tail -n1)"
test "$create" = "source-a|validation-a|completed|f"

docker exec "$PG_CONTAINER" psql -q -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c "BEGIN; SET LOCAL ROLE wave4_runtime; SET LOCAL jlmirror.tenant_id='tenant-a'; SELECT monitoring_source_id FROM monitoring.claim_zabbix_initial_validation('tenant-a','validation-a','validation-claim-a'); SELECT monitoring.complete_zabbix_initial_validation('tenant-a','validation-a','validation-claim-a','validation-evidence-a','binding-a','provider-instance:a','current','succeeded',NULL,'[\"10\",\"20\"]'::jsonb,'[]'::jsonb,'egress-validation-a','credential-generation-a'); COMMIT;" >/dev/null

source_current="$(docker exec "$PG_CONTAINER" psql -Atq -U postgres -d "$PG_DATABASE" -c "BEGIN; SET LOCAL ROLE wave4_runtime; SET LOCAL jlmirror.tenant_id='tenant-a'; SELECT operational_evidence_state FROM monitoring.monitoring_source WHERE monitoring_source_id='source-a'; COMMIT;" | tail -n1)"
test "$source_current" = "current"

host1='{"monitoring_resource_id":"resource-101","provider_evidence_id":"provider-evidence-101-a","hostid":"101","display_name":"Core Switch","evidence_fingerprint":"1111111111111111111111111111111111111111111111111111111111111111","normalized_evidence":{"technical_name":"core-sw-01","display_name":"Core Switch","inventory":{"vendor":"Cisco","model":"C9300","os":"IOS-XE"},"interfaces":[{"interfaceid":"1","interface_type":"snmp","main":true,"use_ip":true,"ip":"10.0.0.2","port":"161"}],"groups":[{"ref":"10","name":"Network"}],"templates":[{"ref":"200","name":"Cisco IOS SNMP"}],"tags":[{"tag":"site","value":"hq"}]}}'
host2='{"monitoring_resource_id":"resource-102","provider_evidence_id":"provider-evidence-102-a","hostid":"102","display_name":"Application Server","evidence_fingerprint":"2222222222222222222222222222222222222222222222222222222222222222","normalized_evidence":{"technical_name":"app-01","display_name":"Application Server","inventory":{"vendor":"Dell","model":"PowerEdge"},"interfaces":[{"interfaceid":"2","interface_type":"agent","main":true,"use_ip":true,"ip":"10.0.0.3","port":"10050"}],"groups":[{"ref":"20","name":"Servers"}],"templates":[],"tags":[]}}'
complete_payload="[$host1,$host2]"

docker exec "$PG_CONTAINER" psql -q -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c "BEGIN; SET LOCAL ROLE wave4_runtime; SET LOCAL jlmirror.tenant_id='tenant-a'; SELECT monitoring.enqueue_zabbix_host_inventory_sync('tenant-a','source-a','inventory-a'); SELECT monitoring_source_id FROM monitoring.claim_zabbix_host_inventory('tenant-a','inventory-a','claim-inventory-a'); SELECT monitoring.complete_zabbix_host_inventory('tenant-a','inventory-a','claim-inventory-a','snapshot-a','binding-a','provider-instance:a','current','succeeded',NULL,true,'$complete_payload'::jsonb,'egress-a','credential-generation-a'); COMMIT;" >/dev/null

first_state="$(docker exec "$PG_CONTAINER" psql -Atq -U postgres -d "$PG_DATABASE" -c "BEGIN; SET LOCAL ROLE wave4_runtime; SET LOCAL jlmirror.tenant_id='tenant-a'; SELECT count(*) || '|' || count(*) FILTER (WHERE resource_kind='host' AND provider_object_kind='zabbix_host' AND presence_state='present') || '|' || count(DISTINCT latest_provider_evidence_id) FROM monitoring.monitoring_resource; COMMIT;" | tail -n1)"
test "$first_state" = "2|2|2"

# A truncated/incomplete snapshot may confirm returned positives but has no negative-removal authority.
host1b="${host1/provider-evidence-101-a/provider-evidence-101-b}"
incomplete_payload="[$host1b]"
docker exec "$PG_CONTAINER" psql -q -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c "BEGIN; SET LOCAL ROLE wave4_runtime; SET LOCAL jlmirror.tenant_id='tenant-a'; SELECT monitoring.enqueue_zabbix_host_inventory_sync('tenant-a','source-a','inventory-b'); SELECT monitoring_source_id FROM monitoring.claim_zabbix_host_inventory('tenant-a','inventory-b','claim-inventory-b'); SELECT monitoring.complete_zabbix_host_inventory('tenant-a','inventory-b','claim-inventory-b','snapshot-b','binding-a','provider-instance:a','incomplete','reconciliation_required','provider.snapshot_truncated',false,'$incomplete_payload'::jsonb,'egress-b','credential-generation-a'); COMMIT;" >/dev/null

truncated_state="$(docker exec "$PG_CONTAINER" psql -Atq -U postgres -d "$PG_DATABASE" -c "BEGIN; SET LOCAL ROLE wave4_runtime; SET LOCAL jlmirror.tenant_id='tenant-a'; SELECT count(*) FILTER (WHERE presence_state='removed') || '|' || count(*) FILTER (WHERE presence_state='present') FROM monitoring.monitoring_resource; COMMIT;" | tail -n1)"
test "$truncated_state" = "0|2"

# Recovery remains possible after an incomplete inventory because source validation authority is independent.
host1c="${host1/provider-evidence-101-a/provider-evidence-101-c}"
recovery_payload="[$host1c]"
docker exec "$PG_CONTAINER" psql -q -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c "BEGIN; SET LOCAL ROLE wave4_runtime; SET LOCAL jlmirror.tenant_id='tenant-a'; SELECT monitoring.enqueue_zabbix_host_inventory_sync('tenant-a','source-a','inventory-c'); SELECT monitoring_source_id FROM monitoring.claim_zabbix_host_inventory('tenant-a','inventory-c','claim-inventory-c'); SELECT monitoring.complete_zabbix_host_inventory('tenant-a','inventory-c','claim-inventory-c','snapshot-c','binding-a','provider-instance:a','current','succeeded',NULL,true,'$recovery_payload'::jsonb,'egress-c','credential-generation-a'); COMMIT;" >/dev/null

negative_authority="$(docker exec "$PG_CONTAINER" psql -Atq -U postgres -d "$PG_DATABASE" -c "BEGIN; SET LOCAL ROLE wave4_runtime; SET LOCAL jlmirror.tenant_id='tenant-a'; SELECT provider_external_ref || ':' || presence_state FROM monitoring.monitoring_resource ORDER BY provider_external_ref; COMMIT;" | grep -E '^(101|102):' | paste -sd '|' -)"
test "$negative_authority" = "101:present|102:removed"

# Provider evidence cannot escape the allowlist or configured scope even through direct SQL.
if docker exec "$PG_CONTAINER" psql -q -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c "BEGIN; SET LOCAL ROLE wave4_runtime; SET LOCAL jlmirror.tenant_id='tenant-a'; INSERT INTO monitoring.monitoring_resource_provider_evidence(tenant_id,provider_evidence_id,host_inventory_snapshot_evidence_id,monitoring_resource_id,monitoring_source_id,source_instance_generation,provider_object_kind,provider_external_ref,evidence_fingerprint,normalized_evidence,observed_at) VALUES ('tenant-a','bad-evidence','snapshot-c','resource-101','source-a','generation-a','zabbix_host','101','3333333333333333333333333333333333333333333333333333333333333333','{\"technical_name\":\"x\",\"display_name\":\"x\",\"inventory\":{},\"interfaces\":[],\"groups\":[{\"ref\":\"999\"}],\"templates\":[],\"tags\":[],\"canonical_device_class\":\"switch\"}'::jsonb,transaction_timestamp()); COMMIT;" >/tmp/wave4-host-bad-evidence.out 2>&1; then
  echo "forged provider evidence unexpectedly persisted" >&2; exit 1
fi
grep -Ei 'bounded_shape|configured-scope|check constraint' /tmp/wave4-host-bad-evidence.out >/dev/null

# Cross-tenant reads fail closed under the runtime role.
tenant_b_count="$(docker exec "$PG_CONTAINER" psql -Atq -U postgres -d "$PG_DATABASE" -c "BEGIN; SET LOCAL ROLE wave4_runtime; SET LOCAL jlmirror.tenant_id='tenant-b'; SELECT count(*) FROM monitoring.monitoring_resource; COMMIT;" | tail -n1)"
test "$tenant_b_count" = "0"

# Completion after a scope-revision change is stale: no snapshot/evidence/resource mutation is accepted.
docker exec "$PG_CONTAINER" psql -q -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c "BEGIN; SET LOCAL ROLE wave4_runtime; SET LOCAL jlmirror.tenant_id='tenant-a'; SELECT monitoring.enqueue_zabbix_host_inventory_sync('tenant-a','source-a','inventory-stale'); SELECT monitoring_source_id FROM monitoring.claim_zabbix_host_inventory('tenant-a','inventory-stale','claim-stale'); UPDATE monitoring.monitoring_source SET configured_provider_scope='{\"host_group_refs\":[\"10\"]}'::jsonb,scope_revision=2 WHERE tenant_id='tenant-a' AND monitoring_source_id='source-a'; SELECT monitoring.complete_zabbix_host_inventory('tenant-a','inventory-stale','claim-stale','snapshot-stale','binding-a','provider-instance:a','current','succeeded',NULL,true,'$recovery_payload'::jsonb,'egress-stale','credential-generation-a'); COMMIT;" >/dev/null

stale_state="$(docker exec "$PG_CONTAINER" psql -Atq -U postgres -d "$PG_DATABASE" -c "BEGIN; SET LOCAL ROLE wave4_runtime; SET LOCAL jlmirror.tenant_id='tenant-a'; SELECT state || '|' || coalesce(last_error_class,'') || '|' || (SELECT count(*) FROM monitoring.monitoring_host_inventory_snapshot_evidence WHERE host_inventory_snapshot_evidence_id='snapshot-stale') FROM monitoring.monitoring_sync_operation WHERE monitoring_sync_operation_id='inventory-stale'; COMMIT;" | tail -n1)"
test "$stale_state" = "reconciliation_required|execution.stale_authority|0"

printf '%s\n' "wave4_zabbix_host_inventory_postgres=PASS resources=canonical provider_evidence=bounded tenant_rls=fail_closed truncated_snapshot=no_negative_authority complete_snapshot=removal_authority stale_scope=fenced recovery=available"
