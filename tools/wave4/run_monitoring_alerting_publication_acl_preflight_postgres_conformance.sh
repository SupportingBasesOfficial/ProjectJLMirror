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

restore_err_trap() {
  trap 'status=$?; echo "wave4_monitoring_alerting_publication_acl_preflight_postgres=FAIL line=$LINENO status=$status" >&2; exit "$status"' ERR
}

run_expected_acl_rejection() {
  local expected="$1"
  local log status output
  log="$(mktemp)"
  trap - ERR
  set +e
  docker exec -i "$PG_CONTAINER" psql -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" < sql/integration/001_monitoring_alerting_publication.sql >"$log" 2>&1
  status=$?
  set -e
  restore_err_trap
  output="$(cat "$log")"
  rm -f "$log"
  if [[ "$status" -eq 0 ]]; then
    echo "unsafe function authority was unexpectedly accepted" >&2
    exit 1
  fi
  grep -Fq "$expected" <<<"$output"
}

# Case 0a: the publication executor is a dedicated owner. An unrelated routine
# already owned by it must block the migration before outbox grants land.
docker exec -i "$PG_CONTAINER" psql -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" <<'SQL' >/dev/null
CREATE ROLE jlmirror_wave4_monitoring_publication_executor
    NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS;
CREATE FUNCTION monitoring.jlmirror_executor_probe(text)
RETURNS text
LANGUAGE sql
SECURITY DEFINER
AS 'SELECT $1';
ALTER FUNCTION monitoring.jlmirror_executor_probe(text)
    OWNER TO jlmirror_wave4_monitoring_publication_executor;
SQL

run_expected_acl_rejection 'monitoring.publication_executor_unexpected_owned_object:'

executor_privs="$(docker exec "$PG_CONTAINER" psql -Atq -U postgres -d "$PG_DATABASE" -c "SELECT has_table_privilege('jlmirror_wave4_monitoring_publication_executor','system.async_outbox_message','SELECT')::int || ':' || has_table_privilege('jlmirror_wave4_monitoring_publication_executor','system.async_outbox_message','INSERT')::int;")"
test "$executor_privs" = "0:0"

docker exec -i "$PG_CONTAINER" psql -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" <<'SQL' >/dev/null
DROP FUNCTION monitoring.jlmirror_executor_probe(text);
SQL

# Case 0b: owner-mediated relations are closed too. A pre-existing view owned by
# the executor and granted to another role must not become a read-through into
# tenant-confidential outbox data after executor storage grants are applied.
docker exec -i "$PG_CONTAINER" psql -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" <<'SQL' >/dev/null
CREATE ROLE jlmirror_view_probe NOLOGIN;
CREATE VIEW monitoring.jlmirror_executor_view_probe AS
SELECT producer_message_scope,message_id FROM system.async_outbox_message;
ALTER VIEW monitoring.jlmirror_executor_view_probe
    OWNER TO jlmirror_wave4_monitoring_publication_executor;
GRANT SELECT ON monitoring.jlmirror_executor_view_probe TO jlmirror_view_probe;
SQL

run_expected_acl_rejection 'monitoring.publication_executor_unexpected_owned_object:'

executor_privs="$(docker exec "$PG_CONTAINER" psql -Atq -U postgres -d "$PG_DATABASE" -c "SELECT has_table_privilege('jlmirror_wave4_monitoring_publication_executor','system.async_outbox_message','SELECT')::int || ':' || has_table_privilege('jlmirror_wave4_monitoring_publication_executor','system.async_outbox_message','INSERT')::int;")"
test "$executor_privs" = "0:0"

trap - ERR
set +e
view_probe_output="$(docker exec "$PG_CONTAINER" psql -Atq -U postgres -d "$PG_DATABASE" -c "SET ROLE jlmirror_view_probe; SELECT count(*) FROM monitoring.jlmirror_executor_view_probe;" 2>&1)"
view_probe_status=$?
set -e
restore_err_trap
test "$view_probe_status" -ne 0
grep -Fq 'permission denied' <<<"$view_probe_output"

docker exec -i "$PG_CONTAINER" psql -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" <<'SQL' >/dev/null
DROP VIEW monitoring.jlmirror_executor_view_probe;
DROP ROLE jlmirror_view_probe;
DROP ROLE jlmirror_wave4_monitoring_publication_executor;
SQL

# Case 0c: CREATE OR REPLACE preserves a function OID and an already-installed
# trigger keeps its tgfoid. A same-signature publication trigger function that
# is attached to any pre-existing table must therefore be rejected before the
# function can be replaced/elevated and before the executor receives outbox ACLs.
docker exec -i "$PG_CONTAINER" psql -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" <<'SQL' >/dev/null
CREATE ROLE jlmirror_wave4_monitoring_publication_executor
    NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS;
CREATE TABLE monitoring.jlmirror_retained_trigger_probe(id bigint);
CREATE FUNCTION monitoring.wave4_publish_problem_transition()
RETURNS trigger
LANGUAGE plpgsql
AS $$ BEGIN RETURN NEW; END $$;
REVOKE ALL ON FUNCTION monitoring.wave4_publish_problem_transition() FROM PUBLIC;
CREATE TRIGGER jlmirror_retained_trigger_probe
BEFORE INSERT ON monitoring.jlmirror_retained_trigger_probe
FOR EACH ROW EXECUTE FUNCTION monitoring.wave4_publish_problem_transition();
SQL

run_expected_acl_rejection 'monitoring.publication_existing_function_dependency_unsafe:monitoring.wave4_publish_problem_transition():class=pg_trigger'

executor_privs="$(docker exec "$PG_CONTAINER" psql -Atq -U postgres -d "$PG_DATABASE" -c "SELECT has_table_privilege('jlmirror_wave4_monitoring_publication_executor','system.async_outbox_message','SELECT')::int || ':' || has_table_privilege('jlmirror_wave4_monitoring_publication_executor','system.async_outbox_message','INSERT')::int;")"
test "$executor_privs" = "0:0"

retained_trigger_state="$(docker exec "$PG_CONTAINER" psql -Atq -U postgres -d "$PG_DATABASE" -c "SELECT pg_get_userbyid(p.proowner) || ':' || p.prosecdef::int || ':' || count(t.oid) FROM pg_proc p JOIN pg_trigger t ON t.tgfoid=p.oid WHERE p.oid='monitoring.wave4_publish_problem_transition()'::regprocedure AND t.tgname='jlmirror_retained_trigger_probe' GROUP BY p.proowner,p.prosecdef;")"
test "$retained_trigger_state" = "postgres:0:1"

docker exec -i "$PG_CONTAINER" psql -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" <<'SQL' >/dev/null
DROP TABLE monitoring.jlmirror_retained_trigger_probe;
DROP FUNCTION monitoring.wave4_publish_problem_transition();
DROP ROLE jlmirror_wave4_monitoring_publication_executor;
SQL

# Case 0d: the same OID-retention hazard applies to every function that becomes
# SECURITY DEFINER, not only trigger functions. Prove an expression index bound
# to the helper's old OID blocks migration before the helper can gain outbox power.
docker exec -i "$PG_CONTAINER" psql -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" <<'SQL' >/dev/null
CREATE ROLE jlmirror_wave4_monitoring_publication_executor
    NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS;
CREATE TABLE monitoring.jlmirror_retained_helper_probe(
    tenant_id text NOT NULL,
    contract_name text NOT NULL,
    subject_type text NOT NULL,
    subject_id text NOT NULL,
    transition_id text NOT NULL,
    occurred_at timestamptz NOT NULL,
    payload jsonb NOT NULL
);
CREATE FUNCTION monitoring.wave4_ensure_monitoring_invalidation(
    text,text,text,text,text,timestamptz,jsonb
) RETURNS bigint
LANGUAGE sql
IMMUTABLE
AS 'SELECT 1::bigint';
REVOKE ALL ON FUNCTION monitoring.wave4_ensure_monitoring_invalidation(text,text,text,text,text,timestamptz,jsonb) FROM PUBLIC;
CREATE INDEX jlmirror_retained_helper_probe_idx
ON monitoring.jlmirror_retained_helper_probe ((monitoring.wave4_ensure_monitoring_invalidation(
    tenant_id,contract_name,subject_type,subject_id,transition_id,occurred_at,payload
)));
SQL

run_expected_acl_rejection 'monitoring.publication_existing_function_dependency_unsafe:monitoring.wave4_ensure_monitoring_invalidation(text,text,text,text,text,timestamptz,jsonb):'

executor_privs="$(docker exec "$PG_CONTAINER" psql -Atq -U postgres -d "$PG_DATABASE" -c "SELECT has_table_privilege('jlmirror_wave4_monitoring_publication_executor','system.async_outbox_message','SELECT')::int || ':' || has_table_privilege('jlmirror_wave4_monitoring_publication_executor','system.async_outbox_message','INSERT')::int;")"
test "$executor_privs" = "0:0"

retained_helper_state="$(docker exec "$PG_CONTAINER" psql -Atq -U postgres -d "$PG_DATABASE" -c "SELECT pg_get_userbyid(p.proowner) || ':' || p.prosecdef::int || ':' || count(d.objid) FROM pg_proc p JOIN pg_depend d ON d.refclassid='pg_proc'::regclass AND d.refobjid=p.oid WHERE p.oid='monitoring.wave4_ensure_monitoring_invalidation(text,text,text,text,text,timestamptz,jsonb)'::regprocedure GROUP BY p.proowner,p.prosecdef;")"
test "$retained_helper_state" = "postgres:0:1"

docker exec -i "$PG_CONTAINER" psql -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" <<'SQL' >/dev/null
DROP TABLE monitoring.jlmirror_retained_helper_probe;
DROP FUNCTION monitoring.wave4_ensure_monitoring_invalidation(text,text,text,text,text,timestamptz,jsonb);
DROP ROLE jlmirror_wave4_monitoring_publication_executor;
SQL

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

# Case 2: even the canonical recovery authority must not retain WITH GRANT OPTION.
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

# Case 3: first-time CREATE FUNCTION can inherit a named EXECUTE from the
# installer's ALTER DEFAULT PRIVILEGES. The post-install fence must catch this
# before COMMIT even though preflight had no existing function to inspect.
docker exec -i "$PG_CONTAINER" psql -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" <<'SQL' >/dev/null
DROP FUNCTION monitoring.recover_problem_state_publication(text,text);
DROP FUNCTION monitoring.wave4_ensure_monitoring_invalidation(text,text,text,text,text,timestamptz,jsonb);
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA monitoring
    GRANT EXECUTE ON FUNCTIONS TO jlmirror_acl_probe;
SQL

run_expected_acl_rejection 'monitoring.publication_installed_function_acl_unsafe:monitoring.wave4_ensure_monitoring_invalidation(text,text,text,text,text,timestamptz,jsonb)'

rolled_back_functions="$(docker exec "$PG_CONTAINER" psql -Atq -U postgres -d "$PG_DATABASE" -c "SELECT count(*) FROM pg_proc WHERE oid IN (to_regprocedure('monitoring.wave4_ensure_monitoring_invalidation(text,text,text,text,text,timestamptz,jsonb)'),to_regprocedure('monitoring.wave4_publish_problem_transition()'),to_regprocedure('monitoring.wave4_publish_health_transition()'),to_regprocedure('monitoring.recover_problem_state_publication(text,text)'),to_regprocedure('monitoring.recover_health_projection_publication(text,text)'));" )"
test "$rolled_back_functions" = "0"

docker exec -i "$PG_CONTAINER" psql -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" <<'SQL' >/dev/null
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA monitoring
    REVOKE EXECUTE ON FUNCTIONS FROM jlmirror_acl_probe;
DROP ROLE jlmirror_acl_probe;
SQL

echo "wave4_monitoring_alerting_publication_acl_preflight_postgres=PASS executor_owned_routine=blocked executor_owned_view=blocked retained_trigger_dependency=blocked retained_helper_expression_dependency=blocked retained_named_execute=blocked recovery_grant_option=blocked default_execute_grant=blocked transactional_acl_fence=proven"
