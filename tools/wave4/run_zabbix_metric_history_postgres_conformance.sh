#!/usr/bin/env bash
set -euo pipefail
trap 'status=$?; echo "wave4_zabbix_metric_history_postgres=FAIL line=$LINENO status=$status" >&2; exit "$status"' ERR

POSTGRES_IMAGE="${POSTGRES_IMAGE:-postgres@sha256:4ef4dbc939d61acea57712655ddb4b4ab27419c913f94cca0cd57cb3ea3c2280}"
PG_CONTAINER="${PG_CONTAINER:-jlmirror-wave4-metric-history-postgres}"
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

# Exact History schema surfaces exist and retain FORCE RLS.
state="$(docker exec "$PG_CONTAINER" psql -Atq -U postgres -d "$PG_DATABASE" -c "
SELECT
  (to_regclass('monitoring.metric_observation') IS NOT NULL)::int || ':' ||
  (to_regclass('monitoring.metric_history_stream_state') IS NOT NULL)::int || ':' ||
  (to_regclass('monitoring.metric_history_gap_evidence') IS NOT NULL)::int || ':' ||
  (to_regclass('monitoring.monitoring_metric_history_runtime_admission') IS NOT NULL)::int || ':' ||
  (SELECT relforcerowsecurity::int FROM pg_class WHERE oid='monitoring.metric_observation'::regclass) || ':' ||
  (SELECT relforcerowsecurity::int FROM pg_class WHERE oid='monitoring.metric_history_stream_state'::regclass) || ':' ||
  (SELECT relforcerowsecurity::int FROM pg_class WHERE oid='monitoring.metric_history_gap_evidence'::regclass) || ':' ||
  (SELECT relforcerowsecurity::int FROM pg_class WHERE oid='monitoring.monitoring_metric_history_runtime_admission'::regclass);")"
test "$state" = "1:1:1:1:1:1:1:1"

# History owns its own source authority columns and does not alias Current/Definitions/Host state.
columns="$(docker exec "$PG_CONTAINER" psql -Atq -U postgres -d "$PG_DATABASE" -c "
SELECT
  (EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='monitoring' AND table_name='monitoring_source' AND column_name='history_poll_epoch'))::int || ':' ||
  (EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='monitoring' AND table_name='monitoring_source' AND column_name='history_poll_generation'))::int || ':' ||
  (EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='monitoring' AND table_name='monitoring_sync_operation' AND column_name='history_poll_epoch'))::int || ':' ||
  (EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='monitoring' AND table_name='monitoring_sync_operation' AND column_name='history_poll_generation'))::int;")"
test "$columns" = "1:1:1:1"

# Runtime roles remain non-superuser/non-bypass-RLS.
roles="$(docker exec "$PG_CONTAINER" psql -Atq -U postgres -d "$PG_DATABASE" -c "
SELECT string_agg(rolname || ':' || rolsuper::int || ':' || rolbypassrls::int, ',' ORDER BY rolname)
FROM pg_roles
WHERE rolname IN ('jlmirror_wave4_metric_history_executor','jlmirror_wave4_metric_history_invoker');")"
test "$roles" = "jlmirror_wave4_metric_history_executor:0:0,jlmirror_wave4_metric_history_invoker:0:0"

# Canonical history identity is storage-bound to durable acceptance.
fk="$(docker exec "$PG_CONTAINER" psql -Atq -U postgres -d "$PG_DATABASE" -c "
SELECT count(*)
FROM pg_constraint c
WHERE c.conrelid='monitoring.metric_observation'::regclass
  AND c.contype='f'
  AND c.confrelid='monitoring.monitoring_metric_observation_acceptance'::regclass;")"
test "$fk" = "1"

# History executor alone can write History projections/checkpoints; invoker cannot fabricate them.
acl="$(docker exec "$PG_CONTAINER" psql -Atq -U postgres -d "$PG_DATABASE" -c "
SELECT
  has_table_privilege('jlmirror_wave4_metric_history_executor','monitoring.metric_observation','INSERT')::int || ':' ||
  has_table_privilege('jlmirror_wave4_metric_history_executor','monitoring.metric_history_stream_state','UPDATE')::int || ':' ||
  has_table_privilege('jlmirror_wave4_metric_history_invoker','monitoring.metric_observation','INSERT')::int || ':' ||
  has_table_privilege('jlmirror_wave4_metric_history_invoker','monitoring.metric_history_stream_state','UPDATE')::int;")"
test "$acl" = "1:1:0:0"

echo "wave4_zabbix_metric_history_postgres=PASS"
