#!/usr/bin/env bash
set -euo pipefail
trap 'status=$?; echo "wave4_zabbix_host_inventory_evidence_authority=FAIL line=$LINENO status=$status" >&2; exit "$status"' ERR

POSTGRES_IMAGE="${POSTGRES_IMAGE:-postgres@sha256:4ef4dbc939d61acea57712655ddb4b4ab27419c913f94cca0cd57cb3ea3c2280}"
PG_CONTAINER="${PG_CONTAINER:-jlmirror-wave4-host-inventory-authority-postgres}"
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
  sql/wave4/010_zabbix_host_inventory_final_authority_hardening.sql; do
  docker exec -i "$PG_CONTAINER" psql -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" < "$migration" >/dev/null
done

docker exec -i "$PG_CONTAINER" psql -q -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" <<'SQL'
CREATE ROLE wave4_runtime NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS;
GRANT USAGE ON SCHEMA monitoring TO wave4_runtime;
GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA monitoring TO wave4_runtime;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA monitoring TO wave4_runtime;
SQL

fp="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
scope='{"host_group_refs":["10"]}'
docker exec "$PG_CONTAINER" psql -q -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c "BEGIN; SET LOCAL ROLE wave4_runtime; SET LOCAL jlmirror.tenant_id='tenant-a'; SELECT * FROM monitoring.create_zabbix_source('tenant-a','create-a','$fp','source-a','generation-a','binding-a','validation-a','audit-a','principal-a','human_browser_session','credential-generation-a','authz-a','correlation-a','Company A Zabbix','provider-instance:a','https://zabbix.example.test/zabbix','credential-binding:a','$scope'::jsonb); SELECT monitoring_source_id FROM monitoring.claim_zabbix_initial_validation('tenant-a','validation-a','validation-claim-a'); SELECT monitoring.complete_zabbix_initial_validation('tenant-a','validation-a','validation-claim-a','validation-evidence-a','binding-a','provider-instance:a','current','succeeded',NULL,'[\"10\"]'::jsonb,'[]'::jsonb,'egress-validation-a','credential-generation-a'); COMMIT;" >/dev/null

normalized='{"technical_name":"core-sw-01","display_name":"Core Switch","inventory":{"vendor":"Cisco","model":"C9300"},"interfaces":[],"groups":[{"ref":"10","name":"Network"}],"templates":[],"tags":[]}'
correct_fp="$(python3 -c 'import hashlib,json,sys; print(hashlib.sha256(json.dumps(json.loads(sys.argv[1]),separators=(",",":"),sort_keys=True,ensure_ascii=False).encode("utf-8")).hexdigest())' "$normalized")"
host_positive="{\"monitoring_resource_id\":\"resource-101\",\"provider_evidence_id\":\"provider-evidence-101-positive\",\"hostid\":\"101\",\"display_name\":\"Core Switch\",\"evidence_fingerprint\":\"$correct_fp\",\"normalized_evidence\":$normalized}"

# A snapshot row cannot claim authority that differs from the running operation that owns it.
docker exec "$PG_CONTAINER" psql -q -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c "BEGIN; SET LOCAL ROLE wave4_runtime; SET LOCAL jlmirror.tenant_id='tenant-a'; SELECT monitoring.enqueue_zabbix_host_inventory_sync('tenant-a','source-a','inventory-bind'); SELECT monitoring_source_id FROM monitoring.claim_zabbix_host_inventory('tenant-a','inventory-bind','claim-bind'); COMMIT;" >/dev/null
poll="$(docker exec "$PG_CONTAINER" psql -Atq -U postgres -d "$PG_DATABASE" -c "BEGIN; SET LOCAL ROLE wave4_runtime; SET LOCAL jlmirror.tenant_id='tenant-a'; SELECT host_inventory_poll_generation FROM monitoring.monitoring_sync_operation WHERE monitoring_sync_operation_id='inventory-bind'; COMMIT;" | tail -n1)"
if docker exec "$PG_CONTAINER" psql -q -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c "BEGIN; SET LOCAL ROLE wave4_runtime; SET LOCAL jlmirror.tenant_id='tenant-a'; INSERT INTO monitoring.monitoring_host_inventory_snapshot_evidence(tenant_id,host_inventory_snapshot_evidence_id,monitoring_sync_operation_id,monitoring_source_id,provider_scope_tenant_binding_id,source_instance_generation,configuration_revision,scope_revision,provider_instance_ref,snapshot_complete,host_count,operational_evidence_state,operation_state,failure_class,egress_decision_ref,credential_generation_ref,observed_at,host_inventory_poll_generation) SELECT 'tenant-a','snapshot-forged-binding','inventory-bind','source-a','binding-a','generation-a',configuration_revision,scope_revision,'provider-instance:a',true,0,'current','succeeded',NULL,'egress-forged','credential-generation-a',transaction_timestamp(),$poll+1 FROM monitoring.monitoring_sync_operation WHERE monitoring_sync_operation_id='inventory-bind'; COMMIT;" >/tmp/wave4-binding.out 2>&1; then
  echo "unbound snapshot evidence unexpectedly accepted" >&2
  exit 1
fi
grep -E "not bound to its claimed running operation|requires current claimed poll authority" /tmp/wave4-binding.out >/dev/null

# Complete one legitimate positive snapshot with a fingerprint derived from normalized evidence.
docker exec "$PG_CONTAINER" psql -q -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c "BEGIN; SET LOCAL ROLE wave4_runtime; SET LOCAL jlmirror.tenant_id='tenant-a'; SELECT monitoring.complete_zabbix_host_inventory('tenant-a','inventory-bind','claim-bind','snapshot-positive','binding-a','provider-instance:a','current','succeeded',NULL,true,'[$host_positive]'::jsonb,'egress-positive','credential-generation-a'); COMMIT;" >/dev/null
stored_fp="$(docker exec "$PG_CONTAINER" psql -Atq -U postgres -d "$PG_DATABASE" -c "BEGIN; SET LOCAL ROLE wave4_runtime; SET LOCAL jlmirror.tenant_id='tenant-a'; SELECT evidence_fingerprint FROM monitoring.monitoring_resource_provider_evidence WHERE provider_evidence_id='provider-evidence-101-positive'; COMMIT;" | tail -n1)"
test "$stored_fp" = "$correct_fp"

# Completed snapshots are closed: later provider-evidence membership cannot be appended.
if docker exec "$PG_CONTAINER" psql -q -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c "BEGIN; SET LOCAL ROLE wave4_runtime; SET LOCAL jlmirror.tenant_id='tenant-a'; INSERT INTO monitoring.monitoring_resource_provider_evidence(tenant_id,provider_evidence_id,host_inventory_snapshot_evidence_id,monitoring_resource_id,monitoring_source_id,source_instance_generation,provider_object_kind,provider_external_ref,evidence_fingerprint,normalized_evidence,observed_at) SELECT 'tenant-a','late-evidence','snapshot-positive','resource-101','source-a','generation-a','zabbix_host','101','$correct_fp','$normalized'::jsonb,observed_at FROM monitoring.monitoring_host_inventory_snapshot_evidence WHERE host_inventory_snapshot_evidence_id='snapshot-positive'; COMMIT;" >/tmp/wave4-closed-snapshot.out 2>&1; then
  echo "completed snapshot unexpectedly accepted later evidence membership" >&2
  exit 1
fi
grep -F "open claimed snapshot operation" /tmp/wave4-closed-snapshot.out >/dev/null

# Fingerprints cannot be fabricated independently from normalized evidence.
docker exec "$PG_CONTAINER" psql -q -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c "BEGIN; SET LOCAL ROLE wave4_runtime; SET LOCAL jlmirror.tenant_id='tenant-a'; SELECT monitoring.enqueue_zabbix_host_inventory_sync('tenant-a','source-a','inventory-fingerprint'); SELECT monitoring_source_id FROM monitoring.claim_zabbix_host_inventory('tenant-a','inventory-fingerprint','claim-fingerprint'); COMMIT;" >/dev/null
bad_host="{\"monitoring_resource_id\":\"resource-101\",\"provider_evidence_id\":\"provider-evidence-bad-fingerprint\",\"hostid\":\"101\",\"display_name\":\"Core Switch\",\"evidence_fingerprint\":\"1111111111111111111111111111111111111111111111111111111111111111\",\"normalized_evidence\":$normalized}"
if docker exec "$PG_CONTAINER" psql -q -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c "BEGIN; SET LOCAL ROLE wave4_runtime; SET LOCAL jlmirror.tenant_id='tenant-a'; SELECT monitoring.complete_zabbix_host_inventory('tenant-a','inventory-fingerprint','claim-fingerprint','snapshot-bad-fingerprint','binding-a','provider-instance:a','current','succeeded',NULL,true,'[$bad_host]'::jsonb,'egress-bad-fingerprint','credential-generation-a'); COMMIT;" >/tmp/wave4-fingerprint.out 2>&1; then
  echo "false evidence fingerprint unexpectedly accepted" >&2
  exit 1
fi
grep -F "fingerprint does not match normalized evidence" /tmp/wave4-fingerprint.out >/dev/null

# A complete newer negative snapshot legitimately removes the host.
docker exec "$PG_CONTAINER" psql -q -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c "BEGIN; SET LOCAL ROLE wave4_runtime; SET LOCAL jlmirror.tenant_id='tenant-a'; SELECT monitoring.enqueue_zabbix_host_inventory_sync('tenant-a','source-a','inventory-remove'); SELECT monitoring_source_id FROM monitoring.claim_zabbix_host_inventory('tenant-a','inventory-remove','claim-remove'); SELECT monitoring.complete_zabbix_host_inventory('tenant-a','inventory-remove','claim-remove','snapshot-remove','binding-a','provider-instance:a','current','succeeded',NULL,true,'[]'::jsonb,'egress-remove','credential-generation-a'); COMMIT;" >/dev/null
removed_state="$(docker exec "$PG_CONTAINER" psql -Atq -U postgres -d "$PG_DATABASE" -c "BEGIN; SET LOCAL ROLE wave4_runtime; SET LOCAL jlmirror.tenant_id='tenant-a'; SELECT presence_state FROM monitoring.monitoring_resource WHERE monitoring_resource_id='resource-101'; COMMIT;" | tail -n1)"
test "$removed_state" = "removed"

# A direct reverse transition cannot resurrect a removed resource from historical positive evidence.
if docker exec "$PG_CONTAINER" psql -q -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c "BEGIN; SET LOCAL ROLE wave4_runtime; SET LOCAL jlmirror.tenant_id='tenant-a'; UPDATE monitoring.monitoring_resource SET presence_state='present',removed_at=NULL,removed_poll_generation=NULL WHERE monitoring_resource_id='resource-101'; COMMIT;" >/tmp/wave4-positive-authority.out 2>&1; then
  echo "historical positive evidence unexpectedly resurrected a removed resource" >&2
  exit 1
fi
grep -F "positive presence requires a poll newer than removal authority" /tmp/wave4-positive-authority.out >/dev/null

# The source-local poll fence cannot be rewound by a direct same-tenant runtime write.
current_poll="$(docker exec "$PG_CONTAINER" psql -Atq -U postgres -d "$PG_DATABASE" -c "BEGIN; SET LOCAL ROLE wave4_runtime; SET LOCAL jlmirror.tenant_id='tenant-a'; SELECT host_inventory_poll_generation FROM monitoring.monitoring_source WHERE monitoring_source_id='source-a'; COMMIT;" | tail -n1)"
if docker exec "$PG_CONTAINER" psql -q -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c "BEGIN; SET LOCAL ROLE wave4_runtime; SET LOCAL jlmirror.tenant_id='tenant-a'; UPDATE monitoring.monitoring_source SET host_inventory_poll_generation=$current_poll-1 WHERE monitoring_source_id='source-a'; COMMIT;" >/tmp/wave4-poll-rewind.out 2>&1; then
  echo "poll generation rewind unexpectedly accepted" >&2
  exit 1
fi
grep -F "poll generation cannot rewind" /tmp/wave4-poll-rewind.out >/dev/null

# A superseded operation cannot insert snapshot evidence merely because it matches its own old poll generation.
docker exec "$PG_CONTAINER" psql -q -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c "BEGIN; SET LOCAL ROLE wave4_runtime; SET LOCAL jlmirror.tenant_id='tenant-a'; SELECT monitoring.enqueue_zabbix_host_inventory_sync('tenant-a','source-a','inventory-old'); SELECT monitoring_source_id FROM monitoring.claim_zabbix_host_inventory('tenant-a','inventory-old','claim-old'); SELECT monitoring.enqueue_zabbix_host_inventory_sync('tenant-a','source-a','inventory-new'); SELECT monitoring_source_id FROM monitoring.claim_zabbix_host_inventory('tenant-a','inventory-new','claim-new'); COMMIT;" >/dev/null
old_poll="$(docker exec "$PG_CONTAINER" psql -Atq -U postgres -d "$PG_DATABASE" -c "BEGIN; SET LOCAL ROLE wave4_runtime; SET LOCAL jlmirror.tenant_id='tenant-a'; SELECT host_inventory_poll_generation FROM monitoring.monitoring_sync_operation WHERE monitoring_sync_operation_id='inventory-old'; COMMIT;" | tail -n1)"
if docker exec "$PG_CONTAINER" psql -q -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c "BEGIN; SET LOCAL ROLE wave4_runtime; SET LOCAL jlmirror.tenant_id='tenant-a'; INSERT INTO monitoring.monitoring_host_inventory_snapshot_evidence(tenant_id,host_inventory_snapshot_evidence_id,monitoring_sync_operation_id,monitoring_source_id,provider_scope_tenant_binding_id,source_instance_generation,configuration_revision,scope_revision,provider_instance_ref,snapshot_complete,host_count,operational_evidence_state,operation_state,failure_class,egress_decision_ref,credential_generation_ref,observed_at,host_inventory_poll_generation) SELECT 'tenant-a','snapshot-superseded','inventory-old','source-a','binding-a','generation-a',configuration_revision,scope_revision,'provider-instance:a',true,0,'current','succeeded',NULL,'egress-old','credential-generation-a',transaction_timestamp(),$old_poll FROM monitoring.monitoring_sync_operation WHERE monitoring_sync_operation_id='inventory-old'; COMMIT;" >/tmp/wave4-current-poll.out 2>&1; then
  echo "superseded operation snapshot unexpectedly accepted" >&2
  exit 1
fi
grep -F "requires current claimed poll authority" /tmp/wave4-current-poll.out >/dev/null

# A snapshot cannot close with a host_count different from final provider evidence membership.
docker exec "$PG_CONTAINER" psql -q -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c "BEGIN; SET LOCAL ROLE wave4_runtime; SET LOCAL jlmirror.tenant_id='tenant-a'; SELECT monitoring.complete_zabbix_host_inventory('tenant-a','inventory-new','claim-new','snapshot-new','binding-a','provider-instance:a','current','succeeded',NULL,true,'[]'::jsonb,'egress-new','credential-generation-a'); COMMIT;" >/dev/null
docker exec "$PG_CONTAINER" psql -q -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c "BEGIN; SET LOCAL ROLE wave4_runtime; SET LOCAL jlmirror.tenant_id='tenant-a'; SELECT monitoring.enqueue_zabbix_host_inventory_sync('tenant-a','source-a','inventory-count'); SELECT monitoring_source_id FROM monitoring.claim_zabbix_host_inventory('tenant-a','inventory-count','claim-count'); COMMIT;" >/dev/null
count_poll="$(docker exec "$PG_CONTAINER" psql -Atq -U postgres -d "$PG_DATABASE" -c "BEGIN; SET LOCAL ROLE wave4_runtime; SET LOCAL jlmirror.tenant_id='tenant-a'; SELECT host_inventory_poll_generation FROM monitoring.monitoring_sync_operation WHERE monitoring_sync_operation_id='inventory-count'; COMMIT;" | tail -n1)"
if docker exec "$PG_CONTAINER" psql -q -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c "BEGIN; SET LOCAL ROLE wave4_runtime; SET LOCAL jlmirror.tenant_id='tenant-a'; INSERT INTO monitoring.monitoring_host_inventory_snapshot_evidence(tenant_id,host_inventory_snapshot_evidence_id,monitoring_sync_operation_id,monitoring_source_id,provider_scope_tenant_binding_id,source_instance_generation,configuration_revision,scope_revision,provider_instance_ref,snapshot_complete,host_count,operational_evidence_state,operation_state,failure_class,egress_decision_ref,credential_generation_ref,observed_at,host_inventory_poll_generation) SELECT 'tenant-a','snapshot-count-mismatch','inventory-count','source-a','binding-a','generation-a',configuration_revision,scope_revision,'provider-instance:a',true,1,'current','succeeded',NULL,'egress-count','credential-generation-a',transaction_timestamp(),$count_poll FROM monitoring.monitoring_sync_operation WHERE monitoring_sync_operation_id='inventory-count'; UPDATE monitoring.monitoring_sync_operation SET state='succeeded',completed_at=transaction_timestamp(),host_inventory_snapshot_evidence_id='snapshot-count-mismatch' WHERE monitoring_sync_operation_id='inventory-count'; COMMIT;" >/tmp/wave4-host-count.out 2>&1; then
  echo "snapshot host_count mismatch unexpectedly accepted" >&2
  exit 1
fi
grep -F "host_count must equal final provider evidence membership" /tmp/wave4-host-count.out >/dev/null

printf '%s\n' "wave4_zabbix_host_inventory_evidence_authority=PASS snapshot_operation_binding=closed membership_after_completion=closed positive_transition=evidence_bound fingerprint=verified negative_transition=completed_operation_bound poll_rewind=blocked superseded_snapshot=current-poll-bound host_count=final-membership-verified"
