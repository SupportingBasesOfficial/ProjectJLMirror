#!/usr/bin/env bash
set -euo pipefail

POSTGRES_IMAGE="${POSTGRES_IMAGE:-postgres@sha256:4ef4dbc939d61acea57712655ddb4b4ab27419c913f94cca0cd57cb3ea3c2280}"
PG_CONTAINER="${PG_CONTAINER:-jlmirror-wave4-monitoring-postgres}"
PG_PASSWORD="${PG_PASSWORD:-wave4-monitoring-password}"
PG_DATABASE="${PG_DATABASE:-jlmirror}"

cleanup() {
  docker rm -f "$PG_CONTAINER" >/dev/null 2>&1 || true
}
trap cleanup EXIT
cleanup

docker pull "$POSTGRES_IMAGE" >/dev/null
docker image inspect "$POSTGRES_IMAGE" --format '{{range .RepoDigests}}{{println .}}{{end}}' | grep -Fx "$POSTGRES_IMAGE" >/dev/null

docker run -d --rm \
  --name "$PG_CONTAINER" \
  -e POSTGRES_PASSWORD="$PG_PASSWORD" \
  -e POSTGRES_DB="$PG_DATABASE" \
  "$POSTGRES_IMAGE" >/dev/null

for _ in $(seq 1 60); do
  if docker exec "$PG_CONTAINER" pg_isready -U postgres -d "$PG_DATABASE" >/dev/null 2>&1; then
    break
  fi
  sleep 1
done
docker exec "$PG_CONTAINER" pg_isready -U postgres -d "$PG_DATABASE" >/dev/null

for migration in \
  sql/wave4/001_monitoring_source_foundation.sql \
  sql/wave4/002_monitoring_source_audit_evidence.sql; do
  docker exec -i "$PG_CONTAINER" psql -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" < "$migration" >/dev/null
done

old_signature="$(docker exec "$PG_CONTAINER" psql -Atq -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c \
  "SELECT to_regprocedure('monitoring.create_zabbix_source(text,text,text,text,text,text,text,text,text,text,text,jsonb)') IS NULL;")"
test "$old_signature" = "t"

fp_a="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
fp_b="bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
provider="provider-instance:central-zabbix"
scope_a='{"host_group_refs":["company-a-linux","company-a-network"]}'
scope_b='{"host_group_refs":["company-b-linux"]}'

create_a="$(docker exec "$PG_CONTAINER" psql -Atq -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c \
  "SELECT * FROM monitoring.create_zabbix_source('tenant-a','create-1','$fp_a','source-a','generation-a','binding-a','sync-a','audit-a','principal-a','human_browser_session','credential-generation-a','authz-a','correlation-a','Company A Zabbix','$provider','https://zabbix.example.test/zabbix','provider-access-binding:central','$scope_a'::jsonb);")"
test "$create_a" = "source-a|sync-a|completed|f"

replay_a="$(docker exec "$PG_CONTAINER" psql -Atq -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c \
  "SELECT * FROM monitoring.create_zabbix_source('tenant-a','create-1','$fp_a','ignored-source','ignored-generation','ignored-binding','ignored-sync','ignored-audit','principal-b','machine_api_principal','credential-generation-b','authz-b','correlation-b','Company A Zabbix','$provider','https://zabbix.example.test/zabbix','provider-access-binding:central','$scope_a'::jsonb);")"
test "$replay_a" = "source-a|sync-a|completed|t"

if docker exec "$PG_CONTAINER" psql -q -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c \
  "SELECT * FROM monitoring.create_zabbix_source('tenant-a','create-1','$fp_b','other-source','other-generation','other-binding','other-sync','other-audit','principal-a','human_browser_session','credential-generation-a','authz-a','correlation-a','Different intent','$provider','https://zabbix.example.test/zabbix','provider-access-binding:other','$scope_a'::jsonb);" >/tmp/wave4-mismatch.out 2>&1; then
  echo "same-key/different-fingerprint unexpectedly succeeded" >&2
  exit 1
fi
grep -F "idempotency.key_reused" /tmp/wave4-mismatch.out >/dev/null

create_b="$(docker exec "$PG_CONTAINER" psql -Atq -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c \
  "SELECT * FROM monitoring.create_zabbix_source('tenant-b','create-1','$fp_b','source-b','generation-b','binding-b','sync-b','audit-b','principal-b','machine_api_principal','credential-generation-b','authz-b','correlation-b','Company B Zabbix','$provider','https://zabbix.example.test/zabbix','provider-access-binding:central','$scope_b'::jsonb);")"
test "$create_b" = "source-b|sync-b|completed|f"

shared_provider_instance="$(docker exec "$PG_CONTAINER" psql -Atq -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c \
  "SELECT count(*) || '|' || count(DISTINCT provider_instance_ref) FROM monitoring.monitoring_source_generation WHERE provider_instance_ref='$provider';")"
test "$shared_provider_instance" = "2|1"

binding_isolation="$(docker exec "$PG_CONTAINER" psql -Atq -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c \
  "SELECT string_agg(tenant_id || ':' || provider_scope_tenant_binding_id, ',' ORDER BY tenant_id) FROM monitoring.monitoring_source;")"
test "$binding_isolation" = "tenant-a:binding-a,tenant-b:binding-b"

state_result="$(docker exec "$PG_CONTAINER" psql -Atq -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c \
  "SELECT s.operational_evidence_state || '|' || o.state || '|' || s.configuration_revision || '|' || s.scope_revision FROM monitoring.monitoring_source s JOIN monitoring.monitoring_sync_operation o ON o.tenant_id=s.tenant_id AND o.monitoring_sync_operation_id=s.last_sync_operation_id WHERE s.tenant_id='tenant-a' AND s.monitoring_source_id='source-a';")"
test "$state_result" = "reconciliation_required|pending|1|1"

counts="$(docker exec "$PG_CONTAINER" psql -Atq -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c \
  "SELECT (SELECT count(*) FROM monitoring.monitoring_source) || '|' || (SELECT count(*) FROM monitoring.monitoring_source_generation) || '|' || (SELECT count(*) FROM monitoring.monitoring_sync_operation) || '|' || (SELECT count(*) FROM monitoring.monitoring_source_create_idempotency) || '|' || (SELECT count(*) FROM monitoring.monitoring_source_audit_evidence);")"
test "$counts" = "2|2|2|2|2"

replay_audit_count="$(docker exec "$PG_CONTAINER" psql -Atq -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c \
  "SELECT count(*) FROM monitoring.monitoring_source_audit_evidence WHERE tenant_id='tenant-a';")"
test "$replay_audit_count" = "1"

docker exec "$PG_CONTAINER" psql -q -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c \
  "UPDATE monitoring.monitoring_source SET credential_binding_ref='provider-access-binding:rotated', configuration_revision=2 WHERE tenant_id='tenant-a' AND monitoring_source_id='source-a';" >/dev/null
mutable_result="$(docker exec "$PG_CONTAINER" psql -Atq -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c \
  "SELECT credential_binding_ref || '|' || configuration_revision FROM monitoring.monitoring_source WHERE tenant_id='tenant-a' AND monitoring_source_id='source-a';")"
test "$mutable_result" = "provider-access-binding:rotated|2"

if docker exec "$PG_CONTAINER" psql -q -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c \
  "UPDATE monitoring.monitoring_source_generation SET provider_instance_ref='provider-instance:other' WHERE tenant_id='tenant-a' AND monitoring_source_id='source-a';" >/tmp/wave4-generation.out 2>&1; then
  echo "immutable source generation unexpectedly updated" >&2
  exit 1
fi
grep -F "Monitoring source generation records are immutable" /tmp/wave4-generation.out >/dev/null

if docker exec "$PG_CONTAINER" psql -q -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c \
  "UPDATE monitoring.monitoring_source SET provider_scope_tenant_binding_id='binding-mutated' WHERE tenant_id='tenant-a' AND monitoring_source_id='source-a';" >/tmp/wave4-binding.out 2>&1; then
  echo "immutable provider_scope_tenant_binding_id unexpectedly updated" >&2
  exit 1
fi
grep -F "tenant/logical/binding identity/provider profile is immutable" /tmp/wave4-binding.out >/dev/null

if docker exec "$PG_CONTAINER" psql -q -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c \
  "UPDATE monitoring.monitoring_source_audit_evidence SET outcome='changed' WHERE tenant_id='tenant-a' AND audit_evidence_id='audit-a';" >/tmp/wave4-audit.out 2>&1; then
  echo "immutable audit evidence unexpectedly updated" >&2
  exit 1
fi
grep -F "Monitoring source audit evidence is immutable" /tmp/wave4-audit.out >/dev/null

if docker exec "$PG_CONTAINER" psql -q -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c \
  "UPDATE monitoring.monitoring_source SET configuration_revision=1 WHERE tenant_id='tenant-a' AND monitoring_source_id='source-a';" >/tmp/wave4-regression.out 2>&1; then
  echo "source revision regression unexpectedly succeeded" >&2
  exit 1
fi
grep -F "Monitoring source revisions cannot regress" /tmp/wave4-regression.out >/dev/null

if docker exec "$PG_CONTAINER" psql -q -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c \
  "SELECT * FROM monitoring.create_zabbix_source('tenant-c','bad-provider','$fp_a','source-c','generation-c','binding-c','sync-c','audit-c','principal-c','human_browser_session','credential-generation-c','authz-c','correlation-c','Bad provider',' provider-instance:bad','https://zabbix.example.test','provider-access-binding:x','$scope_a'::jsonb);" >/tmp/wave4-bad-provider.out 2>&1; then
  echo "noncanonical provider_instance_ref unexpectedly succeeded" >&2
  exit 1
fi
grep -F "invalid bounded create-source input" /tmp/wave4-bad-provider.out >/dev/null

if docker exec "$PG_CONTAINER" psql -q -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c \
  "SELECT * FROM monitoring.create_zabbix_source('tenant-c','bad-scope','$fp_a','source-c','generation-c','binding-c','sync-c','audit-c','principal-c','human_browser_session','credential-generation-c','authz-c','correlation-c','Bad Scope','$provider','https://zabbix.example.test','provider-access-binding:x','{\"host_group_refs\":[\"same\",\"same\"]}'::jsonb);" >/tmp/wave4-bad-scope.out 2>&1; then
  echo "duplicate configured scope unexpectedly succeeded" >&2
  exit 1
fi
grep -F "invalid configured provider scope" /tmp/wave4-bad-scope.out >/dev/null

printf '%s\n' "wave4_monitoring_postgres_conformance=PASS shared_provider_instance=2_sources_1_provider tenant_scope=isolated provider_scope_tenant_binding_id=immutable generation=immutable audit=atomic+immutable create=idempotent network=absent"
