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

# Scenario A: a principal that inherits the canonical recovery role owns a public
# SECURITY DEFINER wrapper with a PL/pgSQL runtime-resolved recovery call. The
# wrapper is not owned by the recovery role itself, so the inherited-principal
# closure must still reject it before publication authority is granted.
docker exec -i "$PG_CONTAINER" psql -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" <<'SQL' >/dev/null
CREATE ROLE jlmirror_recovery_inheriting_member NOLOGIN INHERIT;
GRANT jlmirror_wave4_recovery_authority TO jlmirror_recovery_inheriting_member;
CREATE FUNCTION monitoring.jlmirror_recovery_member_callable_proxy(tenant_id text, transition_id text)
RETURNS bigint
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path=pg_catalog,monitoring,system
AS $$
BEGIN
    RETURN monitoring.recover_problem_state_publication(tenant_id,transition_id);
END;
$$;
ALTER FUNCTION monitoring.jlmirror_recovery_member_callable_proxy(text,text)
    OWNER TO jlmirror_recovery_inheriting_member;
SQL

member_usage="$(docker exec "$PG_CONTAINER" psql -Atq -U postgres -d "$PG_DATABASE" -c "SELECT pg_has_role('jlmirror_recovery_inheriting_member','jlmirror_wave4_recovery_authority','USAGE')::int;")"
test "$member_usage" = "1"

member_bridge_dependency_count="$(docker exec "$PG_CONTAINER" psql -Atq -U postgres -d "$PG_DATABASE" -c "SELECT count(*) FROM pg_depend d JOIN pg_proc p ON p.oid=d.objid WHERE d.classid='pg_proc'::regclass AND p.oid='monitoring.jlmirror_recovery_member_callable_proxy(text,text)'::regprocedure AND d.refobjid=to_regprocedure('monitoring.recover_problem_state_publication(text,text)');")"
test "$member_bridge_dependency_count" = "0"

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
grep -Fq 'monitoring.publication_recovery_authority_callable_proxy_unsafe:' <<<"$output"
grep -Fq 'owner=jlmirror_recovery_inheriting_member' <<<"$output"
grep -Fq 'routine=monitoring.jlmirror_recovery_member_callable_proxy(text,text)' <<<"$output"

docker exec -i "$PG_CONTAINER" psql -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" <<'SQL' >/dev/null
DROP FUNCTION monitoring.jlmirror_recovery_member_callable_proxy(text,text);
SQL

# Scenario B: the inheriting member owns an owner-only SECURITY DEFINER trigger
# function already attached to a table. Trigger execution no longer needs a
# runtime EXECUTE check, so the dependency closure must include member-owned OIDs.
docker exec -i "$PG_CONTAINER" psql -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" <<'SQL' >/dev/null
CREATE TABLE monitoring.jlmirror_recovery_member_trigger_probe(
    tenant_id text NOT NULL,
    transition_id text NOT NULL
);
CREATE FUNCTION monitoring.jlmirror_recovery_member_trigger_proxy()
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
CREATE TRIGGER jlmirror_recovery_member_trigger_proxy
BEFORE INSERT ON monitoring.jlmirror_recovery_member_trigger_probe
FOR EACH ROW EXECUTE FUNCTION monitoring.jlmirror_recovery_member_trigger_proxy();
ALTER FUNCTION monitoring.jlmirror_recovery_member_trigger_proxy()
    OWNER TO jlmirror_recovery_inheriting_member;
REVOKE ALL ON FUNCTION monitoring.jlmirror_recovery_member_trigger_proxy() FROM PUBLIC;
SQL

member_trigger_state="$(docker exec "$PG_CONTAINER" psql -Atq -U postgres -d "$PG_DATABASE" -c "SELECT pg_get_userbyid(p.proowner)||':'||p.prosecdef::int||':'||has_function_privilege('public','monitoring.jlmirror_recovery_member_trigger_proxy()','EXECUTE')::int||':'||count(t.oid) FROM pg_proc p JOIN pg_trigger t ON t.tgfoid=p.oid WHERE p.oid='monitoring.jlmirror_recovery_member_trigger_proxy()'::regprocedure AND t.tgname='jlmirror_recovery_member_trigger_proxy' GROUP BY p.proowner,p.prosecdef;")"
test "$member_trigger_state" = "jlmirror_recovery_inheriting_member:1:0:1"

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
grep -Fq 'owner=jlmirror_recovery_inheriting_member' <<<"$output"
grep -Fq 'routine=monitoring.jlmirror_recovery_member_trigger_proxy()' <<<"$output"
grep -Fq 'class=pg_trigger' <<<"$output"

# Both failures must occur before publication storage authority can persist.
executor_exists="$(docker exec "$PG_CONTAINER" psql -Atq -U postgres -d "$PG_DATABASE" -c "SELECT count(*) FROM pg_roles WHERE rolname='jlmirror_wave4_monitoring_publication_executor';")"
if [[ "$executor_exists" = "1" ]]; then
  executor_privs="$(docker exec "$PG_CONTAINER" psql -Atq -U postgres -d "$PG_DATABASE" -c "SELECT has_table_privilege('jlmirror_wave4_monitoring_publication_executor','system.async_outbox_message','SELECT')::int||':'||has_table_privilege('jlmirror_wave4_monitoring_publication_executor','system.async_outbox_message','INSERT')::int;")"
  test "$executor_privs" = "0:0"
fi

docker exec -i "$PG_CONTAINER" psql -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" <<'SQL' >/dev/null
DROP TABLE monitoring.jlmirror_recovery_member_trigger_probe CASCADE;
REVOKE jlmirror_wave4_recovery_authority FROM jlmirror_recovery_inheriting_member;
DROP ROLE jlmirror_recovery_inheriting_member;
SQL

# Scenario C: a NOINHERIT member is not an implicit proxy principal. Its public
# wrapper may exist, but pg_has_role(...,'USAGE') is false and the wrapper owner
# cannot exercise the recovery grant without an explicit SET ROLE. Preserve that
# distinction instead of rejecting every membership indiscriminately.
docker exec -i "$PG_CONTAINER" psql -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" <<'SQL' >/dev/null
CREATE ROLE jlmirror_recovery_noninheriting_member NOLOGIN NOINHERIT;
GRANT jlmirror_wave4_recovery_authority TO jlmirror_recovery_noninheriting_member;
CREATE FUNCTION monitoring.jlmirror_recovery_noninheriting_proxy(tenant_id text, transition_id text)
RETURNS bigint
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path=pg_catalog,monitoring,system
AS $$
BEGIN
    RETURN monitoring.recover_problem_state_publication(tenant_id,transition_id);
END;
$$;
ALTER FUNCTION monitoring.jlmirror_recovery_noninheriting_proxy(text,text)
    OWNER TO jlmirror_recovery_noninheriting_member;
SQL

noninherit_usage="$(docker exec "$PG_CONTAINER" psql -Atq -U postgres -d "$PG_DATABASE" -c "SELECT pg_has_role('jlmirror_recovery_noninheriting_member','jlmirror_wave4_recovery_authority','USAGE')::int;")"
test "$noninherit_usage" = "0"

docker exec -i "$PG_CONTAINER" psql -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" < sql/integration/001_monitoring_alerting_publication.sql >/dev/null

# The non-inheriting wrapper still cannot exercise the new recovery entry point as
# its SECURITY DEFINER owner. The migration succeeds because no implicit authority
# path exists; invocation itself must fail closed.
log="$(mktemp)"
trap - ERR
set +e
docker exec "$PG_CONTAINER" psql -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" -c "SELECT monitoring.jlmirror_recovery_noninheriting_proxy('tenant-x','transition-x');" >"$log" 2>&1
status=$?
set -e
trap 'status=$?; echo "wave4_monitoring_alerting_publication_recovery_proxy_postgres=FAIL line=$LINENO status=$status" >&2; exit "$status"' ERR
test "$status" -ne 0
grep -Eq 'permission denied|not permitted' "$log"
rm -f "$log"

echo "wave4_monitoring_alerting_publication_recovery_proxy_postgres=PASS inherited_callable_proxy=blocked inherited_trigger_proxy=blocked noninheriting_membership=preserved runtime_resolved_recovery_call=no-pg-depend publication_authority=guarded"