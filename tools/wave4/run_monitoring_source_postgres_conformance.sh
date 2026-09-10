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

docker exec -i "$PG_CONTAINER" psql -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" \
  < sql/wave4/001_monitoring_source_foundation.sql >/dev/null

fp_a="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
fp_b="bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
scope='{"host_group_refs":["group-linux","group-network"]}'

create_result="$(docker exec "$PG_CONTAINER" psql -Atq -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c \
  "SELECT * FROM monitoring.create_zabbix_source('tenant-a','create-1','$fp_a','source-a','generation-a','sync-a','Primary Zabbix','https://zabbix.example.test/zabbix','secret-binding:zabbix-primary','$scope'::jsonb);")"
test "$create_result" = "source-a|sync-a|completed|f"

replay_result="$(docker exec "$PG_CONTAINER" psql -Atq -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c \
  "SELECT * FROM monitoring.create_zabbix_source('tenant-a','create-1','$fp_a','ignored-source','ignored-generation','ignored-sync','Primary Zabbix','https://zabbix.example.test/zabbix','secret-binding:zabbix-primary','$scope'::jsonb);")"
test "$replay_result" = "source-a|sync-a|completed|t"

if docker exec "$PG_CONTAINER" psql -q -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c \
  "SELECT * FROM monitoring.create_zabbix_source('tenant-a','create-1','$fp_b','other-source','other-generation','other-sync','Different intent','https://zabbix.example.test/zabbix','secret-binding:other','$scope'::jsonb);" >/tmp/wave4-mismatch.out 2>&1; then
  echo "same-key/different-fingerprint unexpectedly succeeded" >&2
  exit 1
fi
grep -F "idempotency.key_reused" /tmp/wave4-mismatch.out >/dev/null

other_tenant_result="$(docker exec "$PG_CONTAINER" psql -Atq -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c \
  "SELECT * FROM monitoring.create_zabbix_source('tenant-b','create-1','$fp_a','source-a','generation-a','sync-a','Primary Zabbix','https://zabbix.example.test/zabbix','secret-binding:zabbix-primary','$scope'::jsonb);")"
test "$other_tenant_result" = "source-a|sync-a|completed|f"

state_result="$(docker exec "$PG_CONTAINER" psql -Atq -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c \
  "SELECT s.operational_evidence_state || '|' || o.state || '|' || s.configuration_revision || '|' || s.scope_revision FROM monitoring.monitoring_source s JOIN monitoring.monitoring_sync_operation o ON o.tenant_id=s.tenant_id AND o.monitoring_sync_operation_id=s.last_sync_operation_id WHERE s.tenant_id='tenant-a' AND s.monitoring_source_id='source-a';")"
test "$state_result" = "reconciliation_required|pending|1|1"

counts="$(docker exec "$PG_CONTAINER" psql -Atq -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c \
  "SELECT (SELECT count(*) FROM monitoring.monitoring_source) || '|' || (SELECT count(*) FROM monitoring.monitoring_source_generation) || '|' || (SELECT count(*) FROM monitoring.monitoring_sync_operation) || '|' || (SELECT count(*) FROM monitoring.monitoring_source_create_idempotency);")"
test "$counts" = "2|2|2|2"

docker exec "$PG_CONTAINER" psql -q -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c \
  "UPDATE monitoring.monitoring_source SET credential_binding_ref='secret-binding:zabbix-rotated', configuration_revision=2 WHERE tenant_id='tenant-a' AND monitoring_source_id='source-a';" >/dev/null
mutable_result="$(docker exec "$PG_CONTAINER" psql -Atq -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c \
  "SELECT credential_binding_ref || '|' || configuration_revision FROM monitoring.monitoring_source WHERE tenant_id='tenant-a' AND monitoring_source_id='source-a';")"
test "$mutable_result" = "secret-binding:zabbix-rotated|2"

generation_count="$(docker exec "$PG_CONTAINER" psql -Atq -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c \
  "SELECT count(*) FROM monitoring.monitoring_source_generation WHERE tenant_id='tenant-a' AND monitoring_source_id='source-a';")"
test "$generation_count" = "1"

if docker exec "$PG_CONTAINER" psql -q -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c \
  "UPDATE monitoring.monitoring_source_generation SET provider_base_url='https://replacement.example.test' WHERE tenant_id='tenant-a' AND monitoring_source_id='source-a';" >/tmp/wave4-generation.out 2>&1; then
  echo "immutable source generation unexpectedly updated" >&2
  exit 1
fi
grep -F "Monitoring source generation records are immutable" /tmp/wave4-generation.out >/dev/null

if docker exec "$PG_CONTAINER" psql -q -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c \
  "UPDATE monitoring.monitoring_source SET configuration_revision=1 WHERE tenant_id='tenant-a' AND monitoring_source_id='source-a';" >/tmp/wave4-regression.out 2>&1; then
  echo "source revision regression unexpectedly succeeded" >&2
  exit 1
fi
grep -F "Monitoring source revisions cannot regress" /tmp/wave4-regression.out >/dev/null

if docker exec "$PG_CONTAINER" psql -q -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c \
  "SELECT * FROM monitoring.create_zabbix_source('tenant-c','bad-url','$fp_a','source-c','generation-c','sync-c','Bad URL','https://user@zabbix.example.test','secret-binding:x','$scope'::jsonb);" >/tmp/wave4-bad-url.out 2>&1; then
  echo "forbidden userinfo URL unexpectedly succeeded" >&2
  exit 1
fi
grep -F "invalid bounded create-source input" /tmp/wave4-bad-url.out >/dev/null

if docker exec "$PG_CONTAINER" psql -q -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c \
  "SELECT * FROM monitoring.create_zabbix_source('tenant-c','bad-scope','$fp_a','source-c','generation-c','sync-c','Bad Scope','https://zabbix.example.test','secret-binding:x','{\"host_group_refs\":[\"same\",\"same\"]}'::jsonb);" >/tmp/wave4-bad-scope.out 2>&1; then
  echo "duplicate configured scope unexpectedly succeeded" >&2
  exit 1
fi
grep -F "invalid configured provider scope" /tmp/wave4-bad-scope.out >/dev/null

printf '%s\n' "wave4_monitoring_postgres_conformance=PASS create=atomic replay=same-result tenant_scope=isolated generation=immutable mutable_config=allowed network=absent"
