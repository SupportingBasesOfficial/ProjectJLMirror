#!/usr/bin/env bash
set -euo pipefail
trap 'status=$?; echo "wave4_zabbix_host_inventory_recovery_authority=FAIL line=$LINENO status=$status" >&2; exit "$status"' ERR

POSTGRES_IMAGE="${POSTGRES_IMAGE:-postgres@sha256:4ef4dbc939d61acea57712655ddb4b4ab27419c913f94cca0cd57cb3ea3c2280}"
PG_CONTAINER="${PG_CONTAINER:-jlmirror-wave4-host-inventory-recovery-postgres}"
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
  sql/wave4/015_zabbix_host_inventory_explicit_admission_and_resource_authority.sql; do
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

docker exec "$PG_CONTAINER" psql -q -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c "BEGIN; SET LOCAL ROLE wave4_runtime; SET LOCAL jlmirror.tenant_id='tenant-a'; SELECT * FROM monitoring.create_zabbix_source('tenant-a','create-recovery','$fp','source-recovery','generation-recovery','binding-recovery','validation-recovery','audit-recovery','principal-recovery','human_browser_session','credential-generation-recovery','authz-recovery','correlation-recovery','Recovery Guard Zabbix','provider-instance:recovery','https://zabbix.example.test/zabbix','credential-binding:recovery','$scope'::jsonb); SELECT monitoring_source_id FROM monitoring.claim_zabbix_initial_validation('tenant-a','validation-recovery','validation-claim-recovery'); SELECT monitoring.complete_zabbix_initial_validation('tenant-a','validation-recovery','validation-claim-recovery','validation-evidence-recovery','binding-recovery','provider-instance:recovery','current','succeeded',NULL,'[\"10\"]'::jsonb,'[]'::jsonb,'egress-validation-recovery','credential-generation-recovery'); COMMIT;" >/dev/null

# Source creation must never self-admit current-state polling. A logical restore/COPY
# is therefore indistinguishable from creation until trusted recovery/placement
# authority explicitly establishes a successor epoch.
admission_count="$(docker exec "$PG_CONTAINER" psql -Atq -U postgres -d "$PG_DATABASE" -c "BEGIN; SET LOCAL ROLE wave4_runtime; SET LOCAL jlmirror.tenant_id='tenant-a'; SELECT count(*) FROM monitoring.monitoring_host_inventory_runtime_admission WHERE monitoring_source_id='source-recovery'; COMMIT;" | tail -n1)"
test "$admission_count" = "0"

docker exec "$PG_CONTAINER" psql -q -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c "BEGIN; SET LOCAL ROLE wave4_runtime; SET LOCAL jlmirror.tenant_id='tenant-a'; SELECT monitoring.enqueue_zabbix_host_inventory_sync('tenant-a','source-recovery','inventory-not-admitted'); COMMIT;" >/dev/null
if docker exec "$PG_CONTAINER" psql -q -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c "BEGIN; SET LOCAL ROLE wave4_runtime; SET LOCAL jlmirror.tenant_id='tenant-a'; SELECT monitoring_source_id FROM monitoring.claim_zabbix_host_inventory('tenant-a','inventory-not-admitted','claim-not-admitted'); COMMIT;" >/tmp/wave4-create-not-admitted.out 2>&1; then
  echo "new/reintroduced source unexpectedly self-admitted polling" >&2
  exit 1
fi
grep -F "Host inventory current-state polling requires current recovery/placement admission" /tmp/wave4-create-not-admitted.out >/dev/null

# Trusted authority explicitly establishes the first usable authority epoch. The
# durable source row starts at epoch 1 but epoch 1 is never admitted implicitly.
docker exec "$PG_CONTAINER" psql -q -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c "BEGIN; SET LOCAL jlmirror.tenant_id='tenant-a'; SELECT monitoring.reestablish_zabbix_host_inventory_poll_epoch('tenant-a','source-recovery',1,2,'placement-v1','recovery-v1','initial-admission-v1'); COMMIT;" >/dev/null

# Claim one poll and leave it running so it becomes stale across a simulated recovery epoch change.
docker exec "$PG_CONTAINER" psql -q -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c "BEGIN; SET LOCAL ROLE wave4_runtime; SET LOCAL jlmirror.tenant_id='tenant-a'; SELECT monitoring.enqueue_zabbix_host_inventory_sync('tenant-a','source-recovery','inventory-pre-recovery'); SELECT monitoring_source_id FROM monitoring.claim_zabbix_host_inventory('tenant-a','inventory-pre-recovery','claim-pre-recovery'); COMMIT;" >/dev/null
pre_epoch="$(docker exec "$PG_CONTAINER" psql -Atq -U postgres -d "$PG_DATABASE" -c "BEGIN; SET LOCAL ROLE wave4_runtime; SET LOCAL jlmirror.tenant_id='tenant-a'; SELECT host_inventory_poll_epoch FROM monitoring.monitoring_sync_operation WHERE monitoring_sync_operation_id='inventory-pre-recovery'; COMMIT;" | tail -n1)"
test "$pre_epoch" = "2"

# Same-tenant runtime writers cannot advance the poll fence directly.
if docker exec "$PG_CONTAINER" psql -q -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c "BEGIN; SET LOCAL ROLE wave4_runtime; SET LOCAL jlmirror.tenant_id='tenant-a'; UPDATE monitoring.monitoring_source SET host_inventory_poll_generation=host_inventory_poll_generation+1 WHERE monitoring_source_id='source-recovery'; COMMIT;" >/tmp/wave4-forward-poll.out 2>&1; then
  echo "direct forward poll increment unexpectedly accepted" >&2
  exit 1
fi
grep -F "Host inventory poll authority requires guarded executor authority" /tmp/wave4-forward-poll.out >/dev/null

# Simulate recovery/failover: volatile admission is absent in the recovered writer.
docker exec "$PG_CONTAINER" psql -q -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c "TRUNCATE monitoring.monitoring_host_inventory_runtime_admission;" >/dev/null
docker exec "$PG_CONTAINER" psql -q -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c "BEGIN; SET LOCAL ROLE wave4_runtime; SET LOCAL jlmirror.tenant_id='tenant-a'; SELECT monitoring.enqueue_zabbix_host_inventory_sync('tenant-a','source-recovery','inventory-blocked-after-recovery'); COMMIT;" >/dev/null
if docker exec "$PG_CONTAINER" psql -q -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c "BEGIN; SET LOCAL ROLE wave4_runtime; SET LOCAL jlmirror.tenant_id='tenant-a'; SELECT monitoring_source_id FROM monitoring.claim_zabbix_host_inventory('tenant-a','inventory-blocked-after-recovery','claim-blocked-after-recovery'); COMMIT;" >/tmp/wave4-recovery-blocked.out 2>&1; then
  echo "polling resumed without recovery admission" >&2
  exit 1
fi
grep -F "Host inventory current-state polling requires current recovery/placement admission" /tmp/wave4-recovery-blocked.out >/dev/null

# Runtime cannot self-issue a successor epoch.
if docker exec "$PG_CONTAINER" psql -q -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c "BEGIN; SET LOCAL ROLE wave4_runtime; SET LOCAL jlmirror.tenant_id='tenant-a'; SELECT monitoring.reestablish_zabbix_host_inventory_poll_epoch('tenant-a','source-recovery',2,3,'placement-v2','recovery-v2','recovery-admission-v2'); COMMIT;" >/tmp/wave4-runtime-readmit.out 2>&1; then
  echo "runtime unexpectedly re-established recovery authority" >&2
  exit 1
fi
grep -E "permission denied|not allowed" /tmp/wave4-runtime-readmit.out >/dev/null

# Trusted recovery authority re-establishes admission and a successor epoch after continuity/reconciliation.
docker exec "$PG_CONTAINER" psql -q -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c "BEGIN; SET LOCAL jlmirror.tenant_id='tenant-a'; SELECT monitoring.reestablish_zabbix_host_inventory_poll_epoch('tenant-a','source-recovery',2,3,'placement-v2','recovery-v2','recovery-admission-v2'); COMMIT;" >/dev/null
source_epoch="$(docker exec "$PG_CONTAINER" psql -Atq -U postgres -d "$PG_DATABASE" -c "BEGIN; SET LOCAL ROLE wave4_runtime; SET LOCAL jlmirror.tenant_id='tenant-a'; SELECT host_inventory_poll_epoch FROM monitoring.monitoring_source WHERE monitoring_source_id='source-recovery'; COMMIT;" | tail -n1)"
test "$source_epoch" = "3"

# A pre-recovery running poll cannot publish in the successor epoch.
if docker exec "$PG_CONTAINER" psql -q -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c "BEGIN; SET LOCAL ROLE wave4_runtime; SET LOCAL jlmirror.tenant_id='tenant-a'; SELECT monitoring.complete_zabbix_host_inventory('tenant-a','inventory-pre-recovery','claim-pre-recovery','snapshot-stale-epoch','binding-recovery','provider-instance:recovery','current','succeeded',NULL,true,'[]'::jsonb,'egress-stale-epoch','credential-generation-recovery'); COMMIT;" >/tmp/wave4-stale-epoch.out 2>&1; then
  echo "pre-recovery poll unexpectedly published after successor epoch" >&2
  exit 1
fi
grep -F "Host inventory snapshot requires current recovery-safe poll epoch authority" /tmp/wave4-stale-epoch.out >/dev/null

# A newly claimed poll receives the successor epoch and remains executable.
docker exec "$PG_CONTAINER" psql -q -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c "BEGIN; SET LOCAL ROLE wave4_runtime; SET LOCAL jlmirror.tenant_id='tenant-a'; SELECT monitoring.enqueue_zabbix_host_inventory_sync('tenant-a','source-recovery','inventory-current'); SELECT monitoring_source_id FROM monitoring.claim_zabbix_host_inventory('tenant-a','inventory-current','claim-current'); COMMIT;" >/dev/null
current_epoch="$(docker exec "$PG_CONTAINER" psql -Atq -U postgres -d "$PG_DATABASE" -c "BEGIN; SET LOCAL ROLE wave4_runtime; SET LOCAL jlmirror.tenant_id='tenant-a'; SELECT host_inventory_poll_epoch FROM monitoring.monitoring_sync_operation WHERE monitoring_sync_operation_id='inventory-current'; COMMIT;" | tail -n1)"
test "$current_epoch" = "3"

normalized='{"technical_name":"core-sw-01","display_name":"Core Switch","inventory":{"vendor":"Cisco","model":"C9300"},"interfaces":[],"groups":[{"ref":"10","name":"Network"}],"templates":[],"tags":[]}'
correct_fp="$(python3 -c 'import hashlib,json,sys; print(hashlib.sha256(json.dumps(json.loads(sys.argv[1]),separators=(",",":"),sort_keys=True,ensure_ascii=False).encode("utf-8")).hexdigest())' "$normalized")"
host="{\"monitoring_resource_id\":\"resource-recovery-101\",\"provider_evidence_id\":\"provider-evidence-recovery-101\",\"hostid\":\"101\",\"display_name\":\"Core Switch\",\"evidence_fingerprint\":\"$correct_fp\",\"normalized_evidence\":$normalized}"

docker exec "$PG_CONTAINER" psql -q -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c "BEGIN; SET LOCAL ROLE wave4_runtime; SET LOCAL jlmirror.tenant_id='tenant-a'; SELECT monitoring.complete_zabbix_host_inventory('tenant-a','inventory-current','claim-current','snapshot-current','binding-recovery','provider-instance:recovery','incomplete','reconciliation_required','provider.snapshot_truncated',false,'[$host]'::jsonb,'egress-current','credential-generation-recovery'); COMMIT;" >/dev/null
resource_epoch="$(docker exec "$PG_CONTAINER" psql -Atq -U postgres -d "$PG_DATABASE" -c "BEGIN; SET LOCAL ROLE wave4_runtime; SET LOCAL jlmirror.tenant_id='tenant-a'; SELECT last_confirmed_present_poll_epoch FROM monitoring.monitoring_resource WHERE monitoring_resource_id='resource-recovery-101'; COMMIT;" | tail -n1)"
test "$resource_epoch" = "3"

# Degraded/incomplete evidence cannot be laundered to current by a direct writer.
if docker exec "$PG_CONTAINER" psql -q -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c "BEGIN; SET LOCAL ROLE wave4_runtime; SET LOCAL jlmirror.tenant_id='tenant-a'; UPDATE monitoring.monitoring_resource SET presence_evidence_state='current' WHERE monitoring_resource_id='resource-recovery-101'; COMMIT;" >/tmp/wave4-presence-launder.out 2>&1; then
  echo "incomplete evidence unexpectedly laundered to current" >&2
  exit 1
fi
grep -F "Monitoring resource host-inventory projection requires guarded executor authority" /tmp/wave4-presence-launder.out >/dev/null

# Scope state cannot be changed without the governed host-inventory/scope authority path.
if docker exec "$PG_CONTAINER" psql -q -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c "BEGIN; SET LOCAL ROLE wave4_runtime; SET LOCAL jlmirror.tenant_id='tenant-a'; UPDATE monitoring.monitoring_resource SET scope_state='out_of_scope' WHERE monitoring_resource_id='resource-recovery-101'; COMMIT;" >/tmp/wave4-scope-mutation.out 2>&1; then
  echo "direct scope-state transition unexpectedly accepted" >&2
  exit 1
fi
grep -F "Monitoring resource host-inventory projection requires guarded executor authority" /tmp/wave4-scope-mutation.out >/dev/null

# Provider-derived observation freshness is authority-bearing and cannot be forged.
if docker exec "$PG_CONTAINER" psql -q -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c "BEGIN; SET LOCAL ROLE wave4_runtime; SET LOCAL jlmirror.tenant_id='tenant-a'; UPDATE monitoring.monitoring_resource SET last_observed_at=last_observed_at + interval '1 day' WHERE monitoring_resource_id='resource-recovery-101'; COMMIT;" >/tmp/wave4-observed-at-mutation.out 2>&1; then
  echo "provider observation timestamp unexpectedly caller-writable" >&2
  exit 1
fi
grep -F "Monitoring resource host-inventory projection requires guarded executor authority" /tmp/wave4-observed-at-mutation.out >/dev/null

echo "wave4_zabbix_host_inventory_recovery_authority=PASS poll_epoch=recovery-safe source_creation=not-self-admitted explicit_admission=required runtime_forward_increment=blocked presence_evidence_laundering=blocked scope_state_direct_mutation=blocked observation_timestamp_direct_mutation=blocked executor=dedicated-nobypassrls"
