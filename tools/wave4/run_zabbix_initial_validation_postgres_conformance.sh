#!/usr/bin/env bash
set -euo pipefail

POSTGRES_IMAGE="${POSTGRES_IMAGE:-postgres@sha256:4ef4dbc939d61acea57712655ddb4b4ab27419c913f94cca0cd57cb3ea3c2280}"
PG_CONTAINER="${PG_CONTAINER:-jlmirror-wave4-zabbix-validation-postgres}"
PG_PASSWORD="${PG_PASSWORD:-wave4-monitoring-password}"
PG_DATABASE="${PG_DATABASE:-jlmirror}"

cleanup() { docker rm -f "$PG_CONTAINER" >/dev/null 2>&1 || true; }
trap cleanup EXIT
cleanup

docker pull "$POSTGRES_IMAGE" >/dev/null
docker run -d --rm --name "$PG_CONTAINER" -e POSTGRES_PASSWORD="$PG_PASSWORD" -e POSTGRES_DB="$PG_DATABASE" "$POSTGRES_IMAGE" >/dev/null

stable=0
for _ in $(seq 1 90); do
  if docker exec "$PG_CONTAINER" pg_isready -U postgres -d "$PG_DATABASE" >/dev/null 2>&1; then
    stable=$((stable + 1))
    if [ "$stable" -ge 3 ]; then break; fi
  else
    stable=0
  fi
  sleep 1
done
test "$stable" -ge 3

for migration in sql/wave4/001_monitoring_source_foundation.sql sql/wave4/002_monitoring_source_audit_evidence.sql sql/wave4/003_zabbix_initial_validation_worker.sql; do
  docker exec -i "$PG_CONTAINER" psql -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" < "$migration" >/dev/null
done

fp="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
scope='{"host_group_refs":["10","20"]}'
docker exec "$PG_CONTAINER" psql -Atq -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c \
"SELECT * FROM monitoring.create_zabbix_source('tenant-a','create-a','$fp','source-a','generation-a','binding-a','sync-a','audit-a','principal-a','human_browser_session','cred-gen-a','authz-a','corr-a','Company A','provider-instance:central','https://zabbix.example.test/zabbix','credential-binding:central','$scope'::jsonb);" >/dev/null

claim="$(docker exec "$PG_CONTAINER" psql -Atq -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c \
"SELECT monitoring_source_id || '|' || provider_scope_tenant_binding_id || '|' || source_instance_generation || '|' || provider_instance_ref FROM monitoring.claim_zabbix_initial_validation('tenant-a','sync-a','claim-a');")"
test "$claim" = "source-a|binding-a|generation-a|provider-instance:central"

if docker exec "$PG_CONTAINER" psql -q -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c \
"SELECT * FROM monitoring.claim_zabbix_initial_validation('tenant-a','sync-a','claim-b');" >/tmp/wave4-double-claim.out 2>&1; then
  echo "second claim unexpectedly succeeded" >&2; exit 1
fi
grep -F "monitoring.initial_validation_not_claimable" /tmp/wave4-double-claim.out >/dev/null

docker exec "$PG_CONTAINER" psql -q -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c \
"SELECT monitoring.complete_zabbix_initial_validation('tenant-a','sync-a','claim-a','validation-a','binding-a','provider-instance:central','current','succeeded',NULL,'[\"10\",\"20\"]'::jsonb,'[]'::jsonb,'egress-decision:1','credential-generation:1');" >/dev/null

state="$(docker exec "$PG_CONTAINER" psql -Atq -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c \
"SELECT o.state || '|' || s.operational_evidence_state || '|' || (s.last_successful_sync_at IS NOT NULL)::text || '|' || e.operation_state FROM monitoring.monitoring_sync_operation o JOIN monitoring.monitoring_source s ON s.tenant_id=o.tenant_id AND s.monitoring_source_id=o.monitoring_source_id JOIN monitoring.monitoring_source_validation_evidence e ON e.tenant_id=o.tenant_id AND e.monitoring_sync_operation_id=o.monitoring_sync_operation_id WHERE o.tenant_id='tenant-a' AND o.monitoring_sync_operation_id='sync-a';")"
test "$state" = "succeeded|current|true|succeeded"

if docker exec "$PG_CONTAINER" psql -q -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c \
"UPDATE monitoring.monitoring_source_validation_evidence SET failure_class='changed' WHERE tenant_id='tenant-a' AND validation_evidence_id='validation-a';" >/tmp/wave4-evidence-mutation.out 2>&1; then
  echo "validation evidence mutation unexpectedly succeeded" >&2; exit 1
fi
grep -F "Monitoring source validation evidence is immutable" /tmp/wave4-evidence-mutation.out >/dev/null

fp2="bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
docker exec "$PG_CONTAINER" psql -Atq -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c \
"SELECT * FROM monitoring.create_zabbix_source('tenant-b','create-b','$fp2','source-b','generation-b','binding-b','sync-b','audit-b','principal-b','human_browser_session','cred-gen-b','authz-b','corr-b','Company B','provider-instance:central','https://zabbix.example.test/zabbix','credential-binding:central','{\"host_group_refs\":[\"30\"]}'::jsonb);" >/dev/null

docker exec "$PG_CONTAINER" psql -Atq -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c \
"SELECT monitoring_source_id FROM monitoring.claim_zabbix_initial_validation('tenant-b','sync-b','claim-b');" >/dev/null

docker exec "$PG_CONTAINER" psql -q -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c \
"UPDATE monitoring.monitoring_source SET configuration_revision=2, credential_binding_ref='credential-binding:rotated' WHERE tenant_id='tenant-b' AND monitoring_source_id='source-b';" >/dev/null

if docker exec "$PG_CONTAINER" psql -q -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c \
"SELECT monitoring.complete_zabbix_initial_validation('tenant-b','sync-b','claim-b','validation-b','binding-b','provider-instance:central','current','succeeded',NULL,'[\"30\"]'::jsonb,'[]'::jsonb,'egress-decision:2','credential-generation:2');" >/tmp/wave4-stale-complete.out 2>&1; then
  echo "stale validation completion unexpectedly succeeded" >&2; exit 1
fi
grep -F "monitoring.initial_validation_stale_authority" /tmp/wave4-stale-complete.out >/dev/null

stale_state="$(docker exec "$PG_CONTAINER" psql -Atq -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c \
"SELECT state || '|' || (validation_evidence_id IS NULL)::text FROM monitoring.monitoring_sync_operation WHERE tenant_id='tenant-b' AND monitoring_sync_operation_id='sync-b';")"
test "$stale_state" = "running|true"

printf '%s\n' "wave4_zabbix_initial_validation_postgres=PASS claim=single-winner completion=fenced evidence=immutable shared_provider=preserved retry_policy=not_selected"
