#!/usr/bin/env bash
set -euo pipefail
trap 'status=$?; echo "wave4_monitoring_alerting_publication_acl_preflight_postgres=FAIL line=$LINENO status=$status" >&2; exit "$status"' ERR

POSTGRES_IMAGE="${POSTGRES_IMAGE:-postgres@sha256:4ef4dbc939d61acea57712655ddb4b4ab27419c913f94cca0cd57cb3ea3c2280}"
PG_CONTAINER="${PG_CONTAINER:-jlmirror-wave4-monitoring-alerting-publication-acl-postgres}"
PG_PASSWORD="${PG_PASSWORD:-wave4-publication-acl-password}"
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

run_expected_acl_rejection() {
  local expected="$1"
  local log status output
  log="$(mktemp)"
  trap - ERR
  set +e
  docker exec -i "$PG_CONTAINER" psql -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" < sql/integration/001_monitoring_alerting_publication.sql >"$log" 2>&1
  status=$?
  set -e
  trap 'status=$?; echo "wave4_monitoring_alerting_publication_acl_preflight_postgres=FAIL line=$LINENO status=$status" >&2; exit "$status"' ERR
  output="$(cat "$log")"
  rm -f "$log"
  if [[ "$status" -eq 0 ]]; then
    echo "unsafe retained function ACL was unexpectedly accepted" >&2
    exit 1
  fi
  grep -Fq "$expected" <<<"$output"
}

# Case 1: unrelated named EXECUTE grant on an internal helper must be rejected
# before the function can become SECURITY DEFINER.
docker exec -i "$PG_CONTAINER" psql -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" <<'SQL' >/dev/null
CREATE ROLE jlmirror_acl_probe NOLOGIN;
CREATE FUNCTION monitoring.wave4_ensure_monitoring_invalidation(
    text,text,text,text,text,timestamptz,jsonb
) RETURNS bigint
LANGUAGE sql
AS 'SELECT 1::bigint';
REVOKE ALL ON FUNCTION monitoring.wave4_ensure_monitoring_invalidation(text,text,text,text,text,timestamptz,jsonb) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION monitoring.wave4_ensure_monitoring_invalidation(text,text,text,text,text,timestamptz,jsonb) TO jlmirror_acl_probe;
SQL

run_expected_acl_rejection 'monitoring.publication_existing_function_acl_unsafe:monitoring.wave4_ensure_monitoring_invalidation(text,text,text,text,text,timestamptz,jsonb)'

probe_state="$(docker exec "$PG_CONTAINER" psql -Atq -U postgres -d "$PG_DATABASE" -c "SELECT pg_get_userbyid(proowner) || ':' || prosecdef::int || ':' || has_function_privilege('jlmirror_acl_probe','monitoring.wave4_ensure_monitoring_invalidation(text,text,text,text,text,timestamptz,jsonb)','EXECUTE')::int FROM pg_proc WHERE oid='monitoring.wave4_ensure_monitoring_invalidation(text,text,text,text,text,timestamptz,jsonb)'::regprocedure;")"
test "$probe_state" = "postgres:0:1"

# Remove the first intentionally unsafe ACL so the next rejection proves the
# recovery-authority grant-option rule rather than re-hitting the first case.
docker exec -i "$PG_CONTAINER" psql -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" <<'SQL' >/dev/null
REVOKE EXECUTE ON FUNCTION monitoring.wave4_ensure_monitoring_invalidation(text,text,text,text,text,timestamptz,jsonb) FROM jlmirror_acl_probe;
CREATE FUNCTION monitoring.recover_problem_state_publication(text,text)
RETURNS bigint
LANGUAGE sql
AS 'SELECT 1::bigint';
REVOKE ALL ON FUNCTION monitoring.recover_problem_state_publication(text,text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION monitoring.recover_problem_state_publication(text,text) TO jlmirror_wave4_recovery_authority WITH GRANT OPTION;
SQL

run_expected_acl_rejection 'monitoring.publication_existing_function_acl_unsafe:monitoring.recover_problem_state_publication(text,text)'

grantable_state="$(docker exec "$PG_CONTAINER" psql -Atq -U postgres -d "$PG_DATABASE" -c "SELECT pg_get_userbyid(p.proowner) || ':' || p.prosecdef::int || ':' || a.is_grantable::int FROM pg_proc p CROSS JOIN LATERAL aclexplode(COALESCE(p.proacl, ARRAY[]::aclitem[])) a JOIN pg_roles r ON r.oid=a.grantee WHERE p.oid='monitoring.recover_problem_state_publication(text,text)'::regprocedure AND r.rolname='jlmirror_wave4_recovery_authority' AND a.privilege_type='EXECUTE';")"
test "$grantable_state" = "postgres:0:1"

echo "wave4_monitoring_alerting_publication_acl_preflight_postgres=PASS retained_named_execute=blocked recovery_grant_option=blocked pre_elevation=proven"
