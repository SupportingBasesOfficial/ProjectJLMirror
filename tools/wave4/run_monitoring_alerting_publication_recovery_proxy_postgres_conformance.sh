#!/usr/bin/env bash
set -euo pipefail
trap 'status=$?; echo "wave4_monitoring_alerting_publication_recovery_proxy_postgres=FAIL line=$LINENO status=$status" >&2; exit "$status"' ERR

POSTGRES_IMAGE="${POSTGRES_IMAGE:-postgres@sha256:4ef4dbc939d61acea57712655ddb4b4ab27419c913f94cca0cd57cb3ea3c2280}"
PG_CONTAINER="${PG_CONTAINER:-jlmirror-wave4-monitoring-alerting-publication-recovery-proxy-postgres}"
PG_PASSWORD="${PG_PASSWORD:-wave4-publication-recovery-proxy-password}"
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

docker exec -i "$PG_CONTAINER" psql -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" < sql/wave2/001_async_correctness.sql >/dev/null
while IFS= read -r migration; do
  docker exec -i "$PG_CONTAINER" psql -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" < "$migration" >/dev/null
done < <(find sql/wave4 -maxdepth 1 -type f -name '*.sql' | sort)

# Build the exact retained invocation path from the finding. The function becomes
# owner-only after its trigger is installed, so no non-owner EXECUTE ACL remains.
# Its call to the bridge recovery function is unresolved until runtime and creates
# no pg_depend edge to that not-yet-created bridge function.
docker exec -i "$PG_CONTAINER" psql -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" <<'SQL' >/dev/null
CREATE TABLE monitoring.jlmirror_recovery_trigger_proxy_probe(
    tenant_id text NOT NULL,
    transition_id text NOT NULL
);
CREATE FUNCTION monitoring.jlmirror_recovery_trigger_proxy()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path=pg_catalog,monitoring,system
AS $$
BEGIN
    PERFORM monitoring.recover_problem_state_publication(NEW.tenant_id,NEW.transition_id);
    RETURN NEW;
END;
$$;
CREATE TRIGGER jlmirror_recovery_trigger_proxy
BEFORE INSERT ON monitoring.jlmirror_recovery_trigger_proxy_probe
FOR EACH ROW EXECUTE FUNCTION monitoring.jlmirror_recovery_trigger_proxy();
ALTER FUNCTION monitoring.jlmirror_recovery_trigger_proxy()
    OWNER TO jlmirror_wave4_recovery_authority;
REVOKE ALL ON FUNCTION monitoring.jlmirror_recovery_trigger_proxy() FROM PUBLIC;
SQL

# Prove the wrapper itself is owner-only while its trigger is retained.
proxy_state="$(docker exec "$PG_CONTAINER" psql -Atq -U postgres -d "$PG_DATABASE" -c "SELECT pg_get_userbyid(p.proowner)||':'||p.prosecdef::int||':'||has_function_privilege('public','monitoring.jlmirror_recovery_trigger_proxy()','EXECUTE')::int||':'||count(t.oid) FROM pg_proc p JOIN pg_trigger t ON t.tgfoid=p.oid WHERE p.oid='monitoring.jlmirror_recovery_trigger_proxy()'::regprocedure AND t.tgname='jlmirror_recovery_trigger_proxy' GROUP BY p.proowner,p.prosecdef;")"
test "$proxy_state" = "jlmirror_wave4_recovery_authority:1:0:1"

# There must be no dependency from the wrapper to the bridge recovery signature;
# the dangerous bridge call is PL/pgSQL runtime resolution, exactly as reviewed.
bridge_dependency_count="$(docker exec "$PG_CONTAINER" psql -Atq -U postgres -d "$PG_DATABASE" -c "SELECT count(*) FROM pg_depend d JOIN pg_proc p ON p.oid=d.objid WHERE d.classid='pg_proc'::regclass AND p.oid='monitoring.jlmirror_recovery_trigger_proxy()'::regprocedure AND d.refobjid=to_regprocedure('monitoring.recover_problem_state_publication(text,text)');")"
test "$bridge_dependency_count" = "0"

log="$(mktemp)"
trap - ERR
set +e
docker exec -i "$PG_CONTAINER" psql -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" < sql/integration/001_monitoring_alerting_publication.sql >"$log" 2>&1
status=$?
set -e
trap 'status=$?; echo "wave4_monitoring_alerting_publication_recovery_proxy_postgres=FAIL line=$LINENO status=$status" >&2; exit "$status"' ERR
output="$(cat "$log")"
rm -f "$log"
test "$status" -ne 0
grep -Fq 'monitoring.publication_recovery_authority_dependency_proxy_unsafe:' <<<"$output"
grep -Fq 'class=pg_trigger' <<<"$output"

# The rejection must happen before publication storage authority can persist.
executor_exists="$(docker exec "$PG_CONTAINER" psql -Atq -U postgres -d "$PG_DATABASE" -c "SELECT count(*) FROM pg_roles WHERE rolname='jlmirror_wave4_monitoring_publication_executor';")"
if [[ "$executor_exists" = "1" ]]; then
  executor_privs="$(docker exec "$PG_CONTAINER" psql -Atq -U postgres -d "$PG_DATABASE" -c "SELECT has_table_privilege('jlmirror_wave4_monitoring_publication_executor','system.async_outbox_message','SELECT')::int||':'||has_table_privilege('jlmirror_wave4_monitoring_publication_executor','system.async_outbox_message','INSERT')::int;")"
  test "$executor_privs" = "0:0"
fi

# Failed installation must not disturb the retained pre-existing proxy/trigger.
retained_state="$(docker exec "$PG_CONTAINER" psql -Atq -U postgres -d "$PG_DATABASE" -c "SELECT pg_get_userbyid(p.proowner)||':'||p.prosecdef::int||':'||count(t.oid) FROM pg_proc p JOIN pg_trigger t ON t.tgfoid=p.oid WHERE p.oid='monitoring.jlmirror_recovery_trigger_proxy()'::regprocedure AND t.tgname='jlmirror_recovery_trigger_proxy' GROUP BY p.proowner,p.prosecdef;")"
test "$retained_state" = "jlmirror_wave4_recovery_authority:1:1"

echo "wave4_monitoring_alerting_publication_recovery_proxy_postgres=PASS trigger_callable_owner_only_proxy=blocked runtime_resolved_recovery_call=no-pg-depend publication_authority=not-persisted"