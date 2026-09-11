#!/usr/bin/env bash
set -euo pipefail
trap 'status=$?; echo "wave4_zabbix_problem_state_postgres=FAIL line=$LINENO status=$status" >&2; exit "$status"' ERR

POSTGRES_IMAGE="${POSTGRES_IMAGE:-postgres@sha256:4ef4dbc939d61acea57712655ddb4b4ab27419c913f94cca0cd57cb3ea3c2280}"
PG_CONTAINER="${PG_CONTAINER:-jlmirror-wave4-problem-state-postgres}"
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

while IFS= read -r migration; do
  docker exec -i "$PG_CONTAINER" psql -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" < "$migration" >/dev/null
done < <(find sql/wave4 -maxdepth 1 -type f -name '*.sql' | sort)

state="$(docker exec "$PG_CONTAINER" psql -Atq -U postgres -d "$PG_DATABASE" -c "
SELECT
  (to_regclass('monitoring.monitoring_problem') IS NOT NULL)::int || ':' ||
  (to_regclass('monitoring.monitoring_problem_provider_binding') IS NOT NULL)::int || ':' ||
  (to_regclass('monitoring.monitoring_problem_transition') IS NOT NULL)::int || ':' ||
  (to_regclass('monitoring.monitoring_problem_state_runtime_admission') IS NOT NULL)::int || ':' ||
  (SELECT relforcerowsecurity::int FROM pg_class WHERE oid='monitoring.monitoring_problem'::regclass) || ':' ||
  (SELECT relforcerowsecurity::int FROM pg_class WHERE oid='monitoring.monitoring_problem_provider_binding'::regclass) || ':' ||
  (SELECT relforcerowsecurity::int FROM pg_class WHERE oid='monitoring.monitoring_problem_transition'::regclass) || ':' ||
  (SELECT relforcerowsecurity::int FROM pg_class WHERE oid='monitoring.monitoring_problem_state_runtime_admission'::regclass);")"
test "$state" = "1:1:1:1:1:1:1:1"

columns="$(docker exec "$PG_CONTAINER" psql -Atq -U postgres -d "$PG_DATABASE" -c "
SELECT
  (EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='monitoring' AND table_name='monitoring_source' AND column_name='problem_poll_epoch'))::int || ':' ||
  (EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='monitoring' AND table_name='monitoring_source' AND column_name='problem_poll_generation'))::int || ':' ||
  (EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='monitoring' AND table_name='monitoring_sync_operation' AND column_name='problem_poll_epoch'))::int || ':' ||
  (EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='monitoring' AND table_name='monitoring_sync_operation' AND column_name='problem_poll_generation'))::int;")"
test "$columns" = "1:1:1:1"

roles="$(docker exec "$PG_CONTAINER" psql -Atq -U postgres -d "$PG_DATABASE" -c "
SELECT string_agg(rolname || ':' || rolsuper::int || ':' || rolbypassrls::int, ',' ORDER BY rolname)
FROM pg_roles
WHERE rolname IN ('jlmirror_wave4_problem_state_executor','jlmirror_wave4_problem_state_invoker');")"
test "$roles" = "jlmirror_wave4_problem_state_executor:0:0,jlmirror_wave4_problem_state_invoker:0:0"

unique_binding="$(docker exec "$PG_CONTAINER" psql -Atq -U postgres -d "$PG_DATABASE" -c "
SELECT count(*)
FROM pg_constraint c
WHERE c.conrelid='monitoring.monitoring_problem_provider_binding'::regclass
  AND c.contype='u';")"
test "$unique_binding" -ge 1

acl="$(docker exec "$PG_CONTAINER" psql -Atq -U postgres -d "$PG_DATABASE" -c "
SELECT
  has_table_privilege('jlmirror_wave4_problem_state_executor','monitoring.monitoring_problem','INSERT')::int || ':' ||
  has_table_privilege('jlmirror_wave4_problem_state_executor','monitoring.monitoring_problem','UPDATE')::int || ':' ||
  has_table_privilege('jlmirror_wave4_problem_state_invoker','monitoring.monitoring_problem','INSERT')::int || ':' ||
  has_table_privilege('jlmirror_wave4_problem_state_invoker','monitoring.monitoring_problem','UPDATE')::int;")"
test "$acl" = "1:1:0:0"

echo "wave4_zabbix_problem_state_postgres=PASS"
