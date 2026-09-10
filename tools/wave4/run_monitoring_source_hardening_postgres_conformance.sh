#!/usr/bin/env bash
set -euo pipefail

POSTGRES_IMAGE="${POSTGRES_IMAGE:-postgres@sha256:4ef4dbc939d61acea57712655ddb4b4ab27419c913f94cca0cd57cb3ea3c2280}"
PG_CONTAINER="${PG_CONTAINER:-jlmirror-wave4-monitoring-hardening-postgres}"
PG_PASSWORD="${PG_PASSWORD:-wave4-monitoring-password}"
PG_DATABASE="${PG_DATABASE:-jlmirror}"

cleanup() {
  docker rm -f "$PG_CONTAINER" >/dev/null 2>&1 || true
}
trap cleanup EXIT
cleanup

docker pull "$POSTGRES_IMAGE" >/dev/null
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
  sql/wave4/002_monitoring_source_audit_evidence.sql \
  sql/wave4/003_monitoring_source_tenant_and_canonical_hardening.sql; do
  docker exec -i "$PG_CONTAINER" psql -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" < "$migration" >/dev/null
done

docker exec "$PG_CONTAINER" psql -q -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" <<'SQL'
CREATE ROLE wave4_runtime NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS;
GRANT USAGE ON SCHEMA monitoring TO wave4_runtime;
GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA monitoring TO wave4_runtime;
GRANT EXECUTE ON FUNCTION monitoring.create_zabbix_source(
    TEXT, TEXT, TEXT, TEXT, TEXT, TEXT, TEXT, TEXT,
    TEXT, TEXT, TEXT, TEXT, TEXT, TEXT, TEXT, JSONB
) TO wave4_runtime;
SQL

rls_flags="$(docker exec "$PG_CONTAINER" psql -Atq -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c \
  "SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='monitoring' AND c.relname IN ('monitoring_source','monitoring_source_generation','monitoring_sync_operation','monitoring_source_create_idempotency','monitoring_source_audit_evidence') AND c.relrowsecurity AND c.relforcerowsecurity;")"
test "$rls_flags" = "5"

missing_context="$(docker exec "$PG_CONTAINER" psql -Atq -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c \
  "BEGIN; SET LOCAL ROLE wave4_runtime; SELECT count(*) FROM monitoring.monitoring_source; COMMIT;" | tail -n1)"
test "$missing_context" = "0"

fp="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
scope='{"host_group_refs":["group-linux","group-network"]}'

create_a="$(docker exec "$PG_CONTAINER" psql -Atq -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c \
  "BEGIN; SET LOCAL ROLE wave4_runtime; SET LOCAL jlmirror.tenant_id = 'tenant-a'; SELECT * FROM monitoring.create_zabbix_source('tenant-a','create-a','$fp','source-a','generation-a','sync-a','audit-a','principal-a','human_browser_session','credential-generation-a','authz-a','correlation-a','Primary Zabbix','https://zabbix.example.test/zabbix','secret-binding:a','$scope'::jsonb); COMMIT;" | tail -n1)"
test "$create_a" = "source-a|sync-a|completed|f"

create_b="$(docker exec "$PG_CONTAINER" psql -Atq -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c \
  "BEGIN; SET LOCAL ROLE wave4_runtime; SET LOCAL jlmirror.tenant_id = 'tenant-b'; SELECT * FROM monitoring.create_zabbix_source('tenant-b','create-b','$fp','source-b','generation-b','sync-b','audit-b','principal-b','machine_api_principal','credential-generation-b','authz-b','correlation-b','Secondary Zabbix','https://zabbix.example.test:8443/zabbix','secret-binding:b','$scope'::jsonb); COMMIT;" | tail -n1)"
test "$create_b" = "source-b|sync-b|completed|f"

visible_a="$(docker exec "$PG_CONTAINER" psql -Atq -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c \
  "BEGIN; SET LOCAL ROLE wave4_runtime; SET LOCAL jlmirror.tenant_id = 'tenant-a'; SELECT string_agg(tenant_id || ':' || monitoring_source_id, ',' ORDER BY monitoring_source_id) FROM monitoring.monitoring_source; COMMIT;" | tail -n1)"
test "$visible_a" = "tenant-a:source-a"

if docker exec "$PG_CONTAINER" psql -q -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c \
  "BEGIN; SET LOCAL ROLE wave4_runtime; SET LOCAL jlmirror.tenant_id = 'tenant-a'; SELECT * FROM monitoring.create_zabbix_source('tenant-b','cross-tenant','$fp','source-x','generation-x','sync-x','audit-x','principal-a','human_browser_session','credential-generation-a','authz-x','correlation-x','Cross tenant','https://zabbix.example.test','secret-binding:x','$scope'::jsonb); COMMIT;" >/tmp/wave4-rls-cross-tenant.out 2>&1; then
  echo "cross-tenant create unexpectedly succeeded" >&2
  exit 1
fi
grep -Ei "row-level security|policy" /tmp/wave4-rls-cross-tenant.out >/dev/null

if docker exec "$PG_CONTAINER" psql -q -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c \
  "BEGIN; SET LOCAL ROLE wave4_runtime; SET LOCAL jlmirror.tenant_id = 'tenant-a'; UPDATE monitoring.monitoring_source SET configured_provider_scope='{\"host_group_refs\":[\"group-linux\"]}'::jsonb WHERE tenant_id='tenant-a' AND monitoring_source_id='source-a'; COMMIT;" >/tmp/wave4-scope-revision.out 2>&1; then
  echo "scope change without revision advance unexpectedly succeeded" >&2
  exit 1
fi
grep -F "Monitoring source scope change requires scope revision advance" /tmp/wave4-scope-revision.out >/dev/null

docker exec "$PG_CONTAINER" psql -q -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c \
  "BEGIN; SET LOCAL ROLE wave4_runtime; SET LOCAL jlmirror.tenant_id = 'tenant-a'; UPDATE monitoring.monitoring_source SET configured_provider_scope='{\"host_group_refs\":[\"group-linux\"]}'::jsonb, scope_revision=2 WHERE tenant_id='tenant-a' AND monitoring_source_id='source-a'; COMMIT;" >/dev/null

scope_revision="$(docker exec "$PG_CONTAINER" psql -Atq -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c \
  "BEGIN; SET LOCAL ROLE wave4_runtime; SET LOCAL jlmirror.tenant_id = 'tenant-a'; SELECT scope_revision FROM monitoring.monitoring_source WHERE tenant_id='tenant-a' AND monitoring_source_id='source-a'; COMMIT;" | tail -n1)"
test "$scope_revision" = "2"

canonical_matrix="$(docker exec "$PG_CONTAINER" psql -Atq -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c \
  "SELECT monitoring.wave4_is_canonical_zabbix_base_url('https://zabbix.example.test/zabbix') || '|' || monitoring.wave4_is_canonical_zabbix_base_url('https://[2001:db8::1]:8443/zabbix') || '|' || monitoring.wave4_is_canonical_zabbix_base_url('https://zabbix.example.test/a/../admin') || '|' || monitoring.wave4_is_canonical_zabbix_base_url('https://ZABBIX.example.test') || '|' || monitoring.wave4_is_canonical_zabbix_base_url('https://zabbix.example.test:0443');")"
test "$canonical_matrix" = "t|t|f|f|f"

if docker exec "$PG_CONTAINER" psql -q -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c \
  "BEGIN; SET LOCAL ROLE wave4_runtime; SET LOCAL jlmirror.tenant_id = 'tenant-c'; SELECT * FROM monitoring.create_zabbix_source('tenant-c','bad-url','$fp','source-c','generation-c','sync-c','audit-c','principal-c','human_browser_session','credential-generation-c','authz-c','correlation-c','Bad URL','https://zabbix.example.test/a/../admin','secret-binding:c','$scope'::jsonb); COMMIT;" >/tmp/wave4-canonical-url.out 2>&1; then
  echo "noncanonical dot-segment URL unexpectedly persisted" >&2
  exit 1
fi
grep -F "monitoring_source_generation_canonical_base_url" /tmp/wave4-canonical-url.out >/dev/null

printf '%s\n' "wave4_monitoring_hardening_postgres_conformance=PASS rls=fail-closed tenant_context=isolated scope_revision=atomic canonical_url=sql-enforced runtime_role=non-superuser"
