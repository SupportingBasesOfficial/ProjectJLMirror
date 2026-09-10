#!/usr/bin/env bash
set -euo pipefail
trap 'status=$?; echo "wave4_monitoring_boundary_hardening=FAIL line=$LINENO status=$status" >&2; exit "$status"' ERR

POSTGRES_IMAGE="${POSTGRES_IMAGE:-postgres@sha256:4ef4dbc939d61acea57712655ddb4b4ab27419c913f94cca0cd57cb3ea3c2280}"
PG_CONTAINER="${PG_CONTAINER:-jlmirror-wave4-monitoring-boundary-postgres}"
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

stable_ready=0
for _ in $(seq 1 90); do
  if docker inspect -f '{{.State.Running}}' "$PG_CONTAINER" 2>/dev/null | grep -qx 'true' \
     && docker exec "$PG_CONTAINER" psql -Atq -U postgres -d "$PG_DATABASE" -c 'SELECT 1' 2>/dev/null | grep -qx '1'; then
    stable_ready=$((stable_ready + 1))
    if [[ "$stable_ready" -ge 3 ]]; then
      break
    fi
  else
    stable_ready=0
  fi
  sleep 1
done
test "$stable_ready" -ge 3

for migration in \
  sql/wave4/001_monitoring_source_foundation.sql \
  sql/wave4/002_monitoring_source_audit_evidence.sql \
  sql/wave4/003_zabbix_initial_validation_worker.sql \
  sql/wave4/004_monitoring_boundary_hardening.sql; do
  docker exec -i "$PG_CONTAINER" psql -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" < "$migration" >/dev/null
done

docker exec -i "$PG_CONTAINER" psql -q -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" <<'SQL'
CREATE ROLE wave4_runtime NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS;
GRANT USAGE ON SCHEMA monitoring TO wave4_runtime;
GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA monitoring TO wave4_runtime;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA monitoring TO wave4_runtime;
SQL

rls_flags="$(docker exec "$PG_CONTAINER" psql -Atq -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c \
  "SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='monitoring' AND c.relname IN ('monitoring_source','monitoring_source_generation','monitoring_sync_operation','monitoring_source_create_idempotency','monitoring_source_audit_evidence','monitoring_source_validation_evidence') AND c.relrowsecurity AND c.relforcerowsecurity;")"
test "$rls_flags" = "6"

missing_context="$(docker exec "$PG_CONTAINER" psql -Atq -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c \
  "BEGIN; SET LOCAL ROLE wave4_runtime; SELECT count(*) FROM monitoring.monitoring_source; COMMIT;" | tail -n1)"
test "$missing_context" = "0"

fp_a="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
fp_b="bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
provider="provider-instance:central-zabbix"
scope_a='{"host_group_refs":["company-a-linux","company-a-network"]}'
scope_b='{"host_group_refs":["company-b-linux"]}'

create_a="$(docker exec "$PG_CONTAINER" psql -Atq -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c \
  "BEGIN; SET LOCAL ROLE wave4_runtime; SET LOCAL jlmirror.tenant_id = 'tenant-a'; SELECT * FROM monitoring.create_zabbix_source('tenant-a','create-a','$fp_a','source-a','generation-a','binding-a','sync-a','audit-a','principal-a','human_browser_session','credential-generation-a','authz-a','correlation-a','Company A Zabbix','$provider','https://zabbix.example.test/zabbix','provider-access-binding:central','$scope_a'::jsonb); COMMIT;" | tail -n1)"
test "$create_a" = "source-a|sync-a|completed|f"

create_b="$(docker exec "$PG_CONTAINER" psql -Atq -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c \
  "BEGIN; SET LOCAL ROLE wave4_runtime; SET LOCAL jlmirror.tenant_id = 'tenant-b'; SELECT * FROM monitoring.create_zabbix_source('tenant-b','create-b','$fp_b','source-b','generation-b','binding-b','sync-b','audit-b','principal-b','machine_api_principal','credential-generation-b','authz-b','correlation-b','Company B Zabbix','$provider','https://zabbix.example.test:8443/zabbix','provider-access-binding:central','$scope_b'::jsonb); COMMIT;" | tail -n1)"
test "$create_b" = "source-b|sync-b|completed|f"

docker exec -i "$PG_CONTAINER" psql -q -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" <<'SQL'
INSERT INTO monitoring.monitoring_source_validation_evidence(
    tenant_id, validation_evidence_id, monitoring_sync_operation_id, monitoring_source_id,
    provider_scope_tenant_binding_id, source_instance_generation, configuration_revision,
    scope_revision, provider_instance_ref, operational_evidence_state, operation_state,
    failure_class, visible_host_group_refs, missing_host_group_refs
) VALUES
('tenant-a','evidence-a','sync-a','source-a','binding-a','generation-a',1,1,'provider-instance:central-zabbix','current','succeeded',NULL,'[]'::jsonb,'[]'::jsonb),
('tenant-b','evidence-b','sync-b','source-b','binding-b','generation-b',1,1,'provider-instance:central-zabbix','incomplete','reconciliation_required','scope.missing','[]'::jsonb,'["company-b-linux"]'::jsonb);
SQL

visible_counts="$(docker exec "$PG_CONTAINER" psql -Atq -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c \
  "BEGIN; SET LOCAL ROLE wave4_runtime; SET LOCAL jlmirror.tenant_id = 'tenant-a'; SELECT (SELECT count(*) FROM monitoring.monitoring_source) || '|' || (SELECT count(*) FROM monitoring.monitoring_source_generation) || '|' || (SELECT count(*) FROM monitoring.monitoring_sync_operation) || '|' || (SELECT count(*) FROM monitoring.monitoring_source_create_idempotency) || '|' || (SELECT count(*) FROM monitoring.monitoring_source_audit_evidence) || '|' || (SELECT count(*) FROM monitoring.monitoring_source_validation_evidence); COMMIT;" | tail -n1)"
test "$visible_counts" = "1|1|1|1|1|1"

if docker exec "$PG_CONTAINER" psql -q -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c \
  "BEGIN; SET LOCAL ROLE wave4_runtime; SET LOCAL jlmirror.tenant_id = 'tenant-a'; SELECT * FROM monitoring.create_zabbix_source('tenant-b','cross-tenant','$fp_b','source-x','generation-x','binding-x','sync-x','audit-x','principal-a','human_browser_session','credential-generation-a','authz-x','correlation-x','Cross tenant','$provider','https://zabbix.example.test','provider-access-binding:x','$scope_b'::jsonb); COMMIT;" >/tmp/wave4-boundary-cross-tenant.out 2>&1; then
  echo "cross-tenant create unexpectedly succeeded" >&2
  exit 1
fi
grep -Ei "row-level security|policy" /tmp/wave4-boundary-cross-tenant.out >/dev/null

if docker exec "$PG_CONTAINER" psql -q -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c \
  "BEGIN; SET LOCAL ROLE wave4_runtime; SET LOCAL jlmirror.tenant_id = 'tenant-a'; UPDATE monitoring.monitoring_source SET configured_provider_scope='{\"host_group_refs\":[\"company-a-linux\"]}'::jsonb WHERE tenant_id='tenant-a' AND monitoring_source_id='source-a'; COMMIT;" >/tmp/wave4-boundary-scope.out 2>&1; then
  echo "scope change without revision advance unexpectedly succeeded" >&2
  exit 1
fi
grep -F "Monitoring source scope change requires scope revision advance" /tmp/wave4-boundary-scope.out >/dev/null

docker exec "$PG_CONTAINER" psql -q -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c \
  "BEGIN; SET LOCAL ROLE wave4_runtime; SET LOCAL jlmirror.tenant_id = 'tenant-a'; UPDATE monitoring.monitoring_source SET configured_provider_scope='{\"host_group_refs\":[\"company-a-linux\"]}'::jsonb, scope_revision=2 WHERE tenant_id='tenant-a' AND monitoring_source_id='source-a'; COMMIT;" >/dev/null

scope_revision="$(docker exec "$PG_CONTAINER" psql -Atq -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c \
  "BEGIN; SET LOCAL ROLE wave4_runtime; SET LOCAL jlmirror.tenant_id = 'tenant-a'; SELECT scope_revision FROM monitoring.monitoring_source WHERE monitoring_source_id='source-a'; COMMIT;" | tail -n1)"
test "$scope_revision" = "2"

canonical_matrix="$(docker exec "$PG_CONTAINER" psql -Atq -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c \
  "SELECT (CASE WHEN monitoring.wave4_is_canonical_zabbix_base_url('https://zabbix.example.test/zabbix') THEN '1' ELSE '0' END) || '|' || (CASE WHEN monitoring.wave4_is_canonical_zabbix_base_url('https://[2001:db8::1]:8443/zabbix') THEN '1' ELSE '0' END) || '|' || (CASE WHEN monitoring.wave4_is_canonical_zabbix_base_url('https://zabbix.example.test/a/../admin') THEN '1' ELSE '0' END) || '|' || (CASE WHEN monitoring.wave4_is_canonical_zabbix_base_url('https://ZABBIX.example.test') THEN '1' ELSE '0' END) || '|' || (CASE WHEN monitoring.wave4_is_canonical_zabbix_base_url('https://zabbix.example.test:0443') THEN '1' ELSE '0' END);")"
test "$canonical_matrix" = "1|1|0|0|0"

if docker exec "$PG_CONTAINER" psql -q -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c \
  "BEGIN; SET LOCAL ROLE wave4_runtime; SET LOCAL jlmirror.tenant_id = 'tenant-c'; SELECT * FROM monitoring.create_zabbix_source('tenant-c','bad-url','$fp_a','source-c','generation-c','binding-c','sync-c','audit-c','principal-c','human_browser_session','credential-generation-c','authz-c','correlation-c','Bad URL','$provider','https://zabbix.example.test/a/../admin','provider-access-binding:c','$scope_a'::jsonb); COMMIT;" >/tmp/wave4-boundary-url.out 2>&1; then
  echo "noncanonical dot-segment URL unexpectedly persisted" >&2
  exit 1
fi
grep -F "monitoring_source_generation_canonical_base_url" /tmp/wave4-boundary-url.out >/dev/null

printf '%s\n' "wave4_monitoring_boundary_hardening=PASS rls=6_fail_closed tenant_context=isolated scope_revision=atomic canonical_url=sql_enforced runtime_role=non_superuser"
