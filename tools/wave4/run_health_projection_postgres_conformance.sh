#!/usr/bin/env bash
set -euo pipefail
trap 'status=$?; echo "wave4_health_projection_postgres=FAIL line=$LINENO status=$status" >&2; exit "$status"' ERR

POSTGRES_IMAGE="${POSTGRES_IMAGE:-postgres@sha256:4ef4dbc939d61acea57712655ddb4b4ab27419c913f94cca0cd57cb3ea3c2280}"
PG_CONTAINER="${PG_CONTAINER:-jlmirror-wave4-health-postgres}"
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
  (to_regclass('monitoring.health_projection') IS NOT NULL)::int || ':' ||
  (to_regclass('monitoring.health_projection_transition') IS NOT NULL)::int || ':' ||
  (SELECT relforcerowsecurity::int FROM pg_class WHERE oid='monitoring.health_projection'::regclass) || ':' ||
  (SELECT relforcerowsecurity::int FROM pg_class WHERE oid='monitoring.health_projection_transition'::regclass);")"
test "$state" = "1:1:1:1"

roles="$(docker exec "$PG_CONTAINER" psql -Atq -U postgres -d "$PG_DATABASE" -c "
SELECT string_agg(rolname || ':' || rolsuper::int || ':' || rolbypassrls::int, ',' ORDER BY rolname)
FROM pg_roles
WHERE rolname IN ('jlmirror_wave4_health_projection_executor','jlmirror_wave4_health_projection_invoker');")"
test "$roles" = "jlmirror_wave4_health_projection_executor:0:0,jlmirror_wave4_health_projection_invoker:0:0"

acl="$(docker exec "$PG_CONTAINER" psql -Atq -U postgres -d "$PG_DATABASE" -c "
SELECT
  has_table_privilege('jlmirror_wave4_health_projection_executor','monitoring.health_projection','INSERT')::int || ':' ||
  has_table_privilege('jlmirror_wave4_health_projection_executor','monitoring.health_projection','UPDATE')::int || ':' ||
  has_table_privilege('jlmirror_wave4_health_projection_invoker','monitoring.health_projection','INSERT')::int || ':' ||
  has_table_privilege('jlmirror_wave4_health_projection_invoker','monitoring.health_projection','UPDATE')::int;")"
test "$acl" = "1:1:0:0"

function_acl="$(docker exec "$PG_CONTAINER" psql -Atq -U postgres -d "$PG_DATABASE" -c "
SELECT
  has_function_privilege('jlmirror_wave4_health_projection_invoker','monitoring.recompute_health_projection(text,text,text)','EXECUTE')::int || ':' ||
  has_function_privilege('PUBLIC','monitoring.recompute_health_projection(text,text,text)','EXECUTE')::int;")"
test "$function_acl" = "1:0"

constraints="$(docker exec "$PG_CONTAINER" psql -Atq -U postgres -d "$PG_DATABASE" -c "
SELECT
  (EXISTS (SELECT 1 FROM pg_trigger WHERE tgrelid='monitoring.health_projection'::regclass AND tgname='health_projection_guard' AND NOT tgisinternal))::int || ':' ||
  (EXISTS (SELECT 1 FROM pg_trigger WHERE tgrelid='monitoring.health_projection_transition'::regclass AND tgname='health_projection_transition_immutable_guard' AND NOT tgisinternal))::int || ':' ||
  (EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid='monitoring.health_projection_transition'::regclass AND contype='u'))::int;")"
test "$constraints" = "1:1:1"

guard_body="$(docker exec "$PG_CONTAINER" psql -Atq -U postgres -d "$PG_DATABASE" -c "SELECT pg_get_functiondef('monitoring.wave4_guard_health_projection_mutation()'::regprocedure);")"
grep -q "snapshot_complete" <<<"$guard_body"
grep -q "active_source_instance_generation" <<<"$guard_body"
grep -q "presence_state='present'" <<<"$guard_body"
grep -q "scope_state='in_scope'" <<<"$guard_body"
grep -q "Healthy cannot coexist with an active health-affecting canonical problem" <<<"$guard_body"

apply_body="$(docker exec "$PG_CONTAINER" psql -Atq -U postgres -d "$PG_DATABASE" -c "SELECT pg_get_functiondef('monitoring.recompute_health_projection(text,text,text)'::regprocedure);")"
grep -q "FROM monitoring.monitoring_source AS s" <<<"$apply_body"
grep -q "FOR UPDATE" <<<"$apply_body"
grep -q "problem_poll_generation" <<<"$apply_body"
grep -q "v_snapshot_operation_state='succeeded'" <<<"$apply_body"
grep -q "v_existing.health_class=v_health" <<<"$apply_body"
grep -q "last_changed_at=CASE WHEN v_existing.health_class IS DISTINCT FROM v_health" <<<"$apply_body"
! grep -q "p_health_class" <<<"$apply_body"

echo "wave4_health_projection_postgres=PASS"
