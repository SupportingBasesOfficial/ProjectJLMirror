#!/usr/bin/env bash
set -euo pipefail
trap 'status=$?; echo "wave4_zabbix_host_inventory_final_schema=FAIL line=$LINENO status=$status" >&2; exit "$status"' ERR

POSTGRES_IMAGE="${POSTGRES_IMAGE:-postgres@sha256:4ef4dbc939d61acea57712655ddb4b4ab27419c913f94cca0cd57cb3ea3c2280}"
PG_CONTAINER="${PG_CONTAINER:-jlmirror-wave4-host-inventory-final-schema-postgres}"
PG_PASSWORD="${PG_PASSWORD:-wave4-monitoring-password}"
PG_DATABASE="${PG_DATABASE:-jlmirror}"
RECOVERED_DATABASE="${RECOVERED_DATABASE:-jlmirror_recovered}"

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
  sql/wave4/017_zabbix_host_inventory_superseded_epoch_retirement.sql; do
  docker exec -i "$PG_CONTAINER" psql -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" < "$migration" >/dev/null
done

docker exec -i "$PG_CONTAINER" psql -q -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" <<'SQL'
CREATE ROLE wave4_runtime NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS;
GRANT USAGE ON SCHEMA monitoring TO wave4_runtime;
GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA monitoring TO wave4_runtime;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA monitoring TO wave4_runtime;
REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON monitoring.monitoring_host_inventory_runtime_admission FROM wave4_runtime;
REVOKE EXECUTE ON FUNCTION monitoring.reestablish_zabbix_host_inventory_poll_epoch(TEXT,TEXT,BIGINT,BIGINT,TEXT,TEXT,TEXT) FROM wave4_runtime;
SQL

fp="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
scope='{"host_group_refs":["10"]}'

docker exec "$PG_CONTAINER" psql -q -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c "BEGIN; SET LOCAL ROLE wave4_runtime; SET LOCAL jlmirror.tenant_id='tenant-a'; SELECT * FROM monitoring.create_zabbix_source('tenant-a','create-final','$fp','source-final','generation-final','binding-final','validation-final','audit-final','principal-final','human_browser_session','credential-generation-final','authz-final','correlation-final','Final Schema Zabbix','provider-instance:final','https://zabbix.example.test/zabbix','credential-binding:final','$scope'::jsonb); SELECT monitoring_source_id FROM monitoring.claim_zabbix_initial_validation('tenant-a','validation-final','validation-claim-final'); SELECT monitoring.complete_zabbix_initial_validation('tenant-a','validation-final','validation-claim-final','validation-evidence-final','binding-final','provider-instance:final','current','succeeded',NULL,'[\"10\"]'::jsonb,'[]'::jsonb,'egress-validation-final','credential-generation-final'); COMMIT;" >/dev/null

# Fresh/reintroduced sources fail closed until recovery/placement authority explicitly admits them.
admission_before="$(docker exec "$PG_CONTAINER" psql -Atq -U postgres -d "$PG_DATABASE" -c "SELECT count(*) FROM monitoring.monitoring_host_inventory_runtime_admission WHERE monitoring_source_id='source-final';")"
test "$admission_before" = "0"
docker exec "$PG_CONTAINER" psql -q -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c "BEGIN; SET LOCAL ROLE wave4_runtime; SET LOCAL jlmirror.tenant_id='tenant-a'; SELECT monitoring.enqueue_zabbix_host_inventory_sync('tenant-a','source-final','inventory-blocked'); COMMIT;" >/dev/null
if docker exec "$PG_CONTAINER" psql -q -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c "BEGIN; SET LOCAL ROLE wave4_runtime; SET LOCAL jlmirror.tenant_id='tenant-a'; SELECT monitoring_source_id FROM monitoring.claim_zabbix_host_inventory('tenant-a','inventory-blocked','claim-blocked'); COMMIT;" >/tmp/wave4-final-blocked.out 2>&1; then
  echo "host inventory claimed without explicit runtime admission" >&2
  exit 1
fi
grep -F "Host inventory current-state polling requires current recovery/placement admission" /tmp/wave4-final-blocked.out >/dev/null

docker exec "$PG_CONTAINER" psql -q -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c "BEGIN; SET LOCAL jlmirror.tenant_id='tenant-a'; SELECT monitoring.reestablish_zabbix_host_inventory_poll_epoch('tenant-a','source-final',1,2,'placement-final','recovery-final','recovery-admission-final'); COMMIT;" >/dev/null
admission_after="$(docker exec "$PG_CONTAINER" psql -Atq -U postgres -d "$PG_DATABASE" -c "SELECT host_inventory_poll_epoch FROM monitoring.monitoring_host_inventory_runtime_admission WHERE monitoring_source_id='source-final';")"
test "$admission_after" = "2"

# Direct INSERT cannot mint already-claimed host-inventory authority.
if docker exec "$PG_CONTAINER" psql -q -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c "BEGIN; SET LOCAL ROLE wave4_runtime; SET LOCAL jlmirror.tenant_id='tenant-a'; INSERT INTO monitoring.monitoring_sync_operation(tenant_id,monitoring_sync_operation_id,monitoring_source_id,source_instance_generation,configuration_revision,scope_revision,responsibility_kind,state,started_at,claim_token,attempt_count,host_inventory_poll_generation,host_inventory_poll_epoch) VALUES ('tenant-a','inventory-forged-running','source-final','generation-final',1,1,'host_inventory_sync','running',transaction_timestamp(),'forged-claim',1,0,2); COMMIT;" >/tmp/wave4-final-forged-insert.out 2>&1; then
  echo "runtime writer unexpectedly inserted claimed host inventory operation" >&2
  exit 1
fi
grep -F "Host inventory operation insert must be unclaimed pending work" /tmp/wave4-final-forged-insert.out >/dev/null

normalized1='{"technical_name":"core-sw-01","display_name":"Core Switch","inventory":{"vendor":"Cisco","model":"C9300"},"interfaces":[],"groups":[{"ref":"10","name":"Network"}],"templates":[],"tags":[]}'
normalized2='{"technical_name":"edge-rtr-01","display_name":"Edge Router","inventory":{"vendor":"Cisco","model":"ISR"},"interfaces":[],"groups":[{"ref":"10","name":"Network"}],"templates":[],"tags":[]}'
fp1="$(python3 -c 'import hashlib,json,sys; print(hashlib.sha256(json.dumps(json.loads(sys.argv[1]),separators=(",",":"),sort_keys=True,ensure_ascii=False).encode("utf-8")).hexdigest())' "$normalized1")"
fp2="$(python3 -c 'import hashlib,json,sys; print(hashlib.sha256(json.dumps(json.loads(sys.argv[1]),separators=(",",":"),sort_keys=True,ensure_ascii=False).encode("utf-8")).hexdigest())' "$normalized2")"
host1="{\"monitoring_resource_id\":\"resource-final-101\",\"provider_evidence_id\":\"provider-evidence-final-101-a\",\"hostid\":\"101\",\"display_name\":\"Core Switch\",\"evidence_fingerprint\":\"$fp1\",\"normalized_evidence\":$normalized1}"
host2="{\"monitoring_resource_id\":\"resource-final-102\",\"provider_evidence_id\":\"provider-evidence-final-102-a\",\"hostid\":\"102\",\"display_name\":\"Edge Router\",\"evidence_fingerprint\":\"$fp2\",\"normalized_evidence\":$normalized2}"

# Final-schema successful complete snapshot through the effective migration 017 completion function.
docker exec "$PG_CONTAINER" psql -q -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c "BEGIN; SET LOCAL ROLE wave4_runtime; SET LOCAL jlmirror.tenant_id='tenant-a'; SELECT monitoring.enqueue_zabbix_host_inventory_sync('tenant-a','source-final','inventory-present'); SELECT monitoring_source_id FROM monitoring.claim_zabbix_host_inventory('tenant-a','inventory-present','claim-present'); SELECT monitoring.complete_zabbix_host_inventory('tenant-a','inventory-present','claim-present','snapshot-present','binding-final','provider-instance:final','current','succeeded',NULL,true,'[$host1,$host2]'::jsonb,'egress-present','credential-generation-final'); COMMIT;" >/dev/null
present_count="$(docker exec "$PG_CONTAINER" psql -Atq -U postgres -d "$PG_DATABASE" -c "BEGIN; SET LOCAL ROLE wave4_runtime; SET LOCAL jlmirror.tenant_id='tenant-a'; SELECT count(*) FROM monitoring.monitoring_resource WHERE monitoring_source_id='source-final' AND presence_state='present'; COMMIT;" | tail -n1)"
test "$present_count" = "2"

# Same source/epoch/generation authority tuple is single-owner even for privileged SQL.
current_generation="$(docker exec "$PG_CONTAINER" psql -Atq -U postgres -d "$PG_DATABASE" -c "SELECT host_inventory_poll_generation FROM monitoring.monitoring_source WHERE tenant_id='tenant-a' AND monitoring_source_id='source-final';")"
if docker exec "$PG_CONTAINER" psql -q -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c "BEGIN; SET LOCAL jlmirror.tenant_id='tenant-a'; SET LOCAL ROLE jlmirror_wave4_host_inventory_executor; INSERT INTO monitoring.monitoring_sync_operation(tenant_id,monitoring_sync_operation_id,monitoring_source_id,source_instance_generation,configuration_revision,scope_revision,responsibility_kind,state,started_at,claim_token,attempt_count,host_inventory_poll_generation,host_inventory_poll_epoch) VALUES ('tenant-a','inventory-duplicate-authority','source-final','generation-final',1,1,'host_inventory_sync','running',transaction_timestamp(),'duplicate-claim',1,$current_generation,2); COMMIT;" >/tmp/wave4-final-duplicate-authority.out 2>&1; then
  echo "duplicate host inventory poll authority tuple unexpectedly inserted" >&2
  exit 1
fi
duplicate_index="$(docker exec "$PG_CONTAINER" psql -Atq -U postgres -d "$PG_DATABASE" -c "SELECT indexdef FROM pg_indexes WHERE schemaname='monitoring' AND indexname='monitoring_sync_operation_host_inventory_poll_authority_uniq';")"
printf '%s' "$duplicate_index" | grep -F "UNIQUE INDEX monitoring_sync_operation_host_inventory_poll_authority_uniq" >/dev/null
printf '%s' "$duplicate_index" | grep -F "host_inventory_poll_epoch" >/dev/null
printf '%s' "$duplicate_index" | grep -F "host_inventory_poll_generation" >/dev/null

# Final-schema complete omission has negative authority and removes both resources.
docker exec "$PG_CONTAINER" psql -q -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c "BEGIN; SET LOCAL ROLE wave4_runtime; SET LOCAL jlmirror.tenant_id='tenant-a'; SELECT monitoring.enqueue_zabbix_host_inventory_sync('tenant-a','source-final','inventory-empty'); SELECT monitoring_source_id FROM monitoring.claim_zabbix_host_inventory('tenant-a','inventory-empty','claim-empty'); SELECT monitoring.complete_zabbix_host_inventory('tenant-a','inventory-empty','claim-empty','snapshot-empty','binding-final','provider-instance:final','current','succeeded',NULL,true,'[]'::jsonb,'egress-empty','credential-generation-final'); COMMIT;" >/dev/null
removed_count="$(docker exec "$PG_CONTAINER" psql -Atq -U postgres -d "$PG_DATABASE" -c "BEGIN; SET LOCAL ROLE wave4_runtime; SET LOCAL jlmirror.tenant_id='tenant-a'; SELECT count(*) FROM monitoring.monitoring_resource WHERE monitoring_source_id='source-final' AND presence_state='removed'; COMMIT;" | tail -n1)"
test "$removed_count" = "2"

# Terminal operations remain immutable on the composed schema.
if docker exec "$PG_CONTAINER" psql -q -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c "BEGIN; SET LOCAL ROLE wave4_runtime; SET LOCAL jlmirror.tenant_id='tenant-a'; UPDATE monitoring.monitoring_sync_operation SET state='running' WHERE monitoring_sync_operation_id='inventory-empty'; COMMIT;" >/tmp/wave4-final-terminal.out 2>&1; then
  echo "terminal host inventory operation unexpectedly reopened" >&2
  exit 1
fi
grep -F "Terminal host inventory sync operations are immutable" /tmp/wave4-final-terminal.out >/dev/null

# Two claims prove the final composed poll fence still retires the older completion.
docker exec "$PG_CONTAINER" psql -q -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c "BEGIN; SET LOCAL ROLE wave4_runtime; SET LOCAL jlmirror.tenant_id='tenant-a'; SELECT monitoring.enqueue_zabbix_host_inventory_sync('tenant-a','source-final','inventory-old'); SELECT monitoring.enqueue_zabbix_host_inventory_sync('tenant-a','source-final','inventory-new'); SELECT monitoring_source_id FROM monitoring.claim_zabbix_host_inventory('tenant-a','inventory-old','claim-old'); SELECT monitoring_source_id FROM monitoring.claim_zabbix_host_inventory('tenant-a','inventory-new','claim-new'); COMMIT;" >/dev/null
host1_new="{\"monitoring_resource_id\":\"resource-final-101\",\"provider_evidence_id\":\"provider-evidence-final-101-new\",\"hostid\":\"101\",\"display_name\":\"Core Switch\",\"evidence_fingerprint\":\"$fp1\",\"normalized_evidence\":$normalized1}"
docker exec "$PG_CONTAINER" psql -q -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c "BEGIN; SET LOCAL ROLE wave4_runtime; SET LOCAL jlmirror.tenant_id='tenant-a'; SELECT monitoring.complete_zabbix_host_inventory('tenant-a','inventory-new','claim-new','snapshot-new','binding-final','provider-instance:final','current','succeeded',NULL,true,'[$host1_new]'::jsonb,'egress-new','credential-generation-final'); COMMIT;" >/dev/null
docker exec "$PG_CONTAINER" psql -q -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c "BEGIN; SET LOCAL ROLE wave4_runtime; SET LOCAL jlmirror.tenant_id='tenant-a'; SELECT monitoring.complete_zabbix_host_inventory('tenant-a','inventory-old','claim-old','snapshot-old-late','binding-final','provider-instance:final','current','succeeded',NULL,true,'[]'::jsonb,'egress-old','credential-generation-final'); COMMIT;" >/dev/null
superseded_state="$(docker exec "$PG_CONTAINER" psql -Atq -U postgres -d "$PG_DATABASE" -c "BEGIN; SET LOCAL ROLE wave4_runtime; SET LOCAL jlmirror.tenant_id='tenant-a'; SELECT state || ':' || coalesce(last_error_class,'') FROM monitoring.monitoring_sync_operation WHERE monitoring_sync_operation_id='inventory-old'; COMMIT;" | tail -n1)"
test "$superseded_state" = "reconciliation_required:execution.superseded_poll_authority"
old_snapshot_count="$(docker exec "$PG_CONTAINER" psql -Atq -U postgres -d "$PG_DATABASE" -c "SELECT count(*) FROM monitoring.monitoring_host_inventory_snapshot_evidence WHERE host_inventory_snapshot_evidence_id='snapshot-old-late';")"
test "$old_snapshot_count" = "0"

# Provider-derived freshness remains executor-owned on the final schema.
if docker exec "$PG_CONTAINER" psql -q -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c "BEGIN; SET LOCAL ROLE wave4_runtime; SET LOCAL jlmirror.tenant_id='tenant-a'; UPDATE monitoring.monitoring_resource SET last_observed_at=now()+interval '1 day' WHERE monitoring_resource_id='resource-final-101'; COMMIT;" >/tmp/wave4-final-observed.out 2>&1; then
  echo "last_observed_at unexpectedly mutated by runtime writer" >&2
  exit 1
fi
grep -F "Monitoring resource authority fields require guarded host-inventory executor" /tmp/wave4-final-observed.out >/dev/null

# Logical recovery/relocation uses the canonical dump wrapper. It MUST restore the
# durable source while excluding the volatile runtime-admission row.
docker cp tools/wave4/pg_dump_recovery_safe.sh "$PG_CONTAINER":/tmp/pg_dump_recovery_safe.sh
docker exec "$PG_CONTAINER" chmod +x /tmp/pg_dump_recovery_safe.sh
docker exec "$PG_CONTAINER" /tmp/pg_dump_recovery_safe.sh -U postgres -d "$PG_DATABASE" -Fc -f /tmp/wave4-recovery.dump
docker exec "$PG_CONTAINER" createdb -U postgres "$RECOVERED_DATABASE"
docker exec "$PG_CONTAINER" pg_restore -U postgres -d "$RECOVERED_DATABASE" /tmp/wave4-recovery.dump >/dev/null
recovered_source_count="$(docker exec "$PG_CONTAINER" psql -Atq -U postgres -d "$RECOVERED_DATABASE" -c "SELECT count(*) FROM monitoring.monitoring_source WHERE monitoring_source_id='source-final';")"
recovered_admission_count="$(docker exec "$PG_CONTAINER" psql -Atq -U postgres -d "$RECOVERED_DATABASE" -c "SELECT count(*) FROM monitoring.monitoring_host_inventory_runtime_admission WHERE monitoring_source_id='source-final';")"
test "$recovered_source_count" = "1"
test "$recovered_admission_count" = "0"

printf '%s\n' "wave4_zabbix_host_inventory_final_schema=PASS schema=001-017 complete_snapshot=accepted negative_removal=accepted superseded_poll=retired terminal_reopen=blocked claimed_operation_insert=blocked poll_authority=single-owner observation_forgery=blocked logical_recovery_admission=excluded"
