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

# Simulate a pre-existing same-signature helper that was granted to an unrelated
# role before this migration. CREATE OR REPLACE would preserve that named ACL,
# so the migration must reject the state before installing the SECURITY DEFINER body.
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

set +e
acl_output="$(docker exec -i "$PG_CONTAINER" psql -v ON_ERROR_STOP=1 -U postgres -d "$PG_DATABASE" < sql/integration/001_monitoring_alerting_publication.sql 2>&1)"
acl_status=$?
set -e
if [[ "$acl_status" -eq 0 ]]; then
  echo "unsafe retained EXECUTE ACL was unexpectedly accepted" >&2
  exit 1
fi
grep -Fq 'monitoring.publication_existing_function_acl_unsafe:monitoring.wave4_ensure_monitoring_invalidation(text,text,text,text,text,timestamptz,jsonb)' <<<"$acl_output"

# The failed transaction must not have replaced the probe body or changed owner.
probe_state="$(docker exec "$PG_CONTAINER" psql -Atq -U postgres -d "$PG_DATABASE" -c "SELECT pg_get_userbyid(proowner) || ':' || prosecdef::int || ':' || has_function_privilege('jlmirror_acl_probe','monitoring.wave4_ensure_monitoring_invalidation(text,text,text,text,text,timestamptz,jsonb)','EXECUTE')::int FROM pg_proc WHERE oid='monitoring.wave4_ensure_monitoring_invalidation(text,text,text,text,text,timestamptz,jsonb)'::regprocedure;")"
test "$probe_state" = "postgres:0:1"

echo "wave4_monitoring_alerting_publication_acl_preflight_postgres=PASS retained_named_execute=blocked pre_elevation=proven"
