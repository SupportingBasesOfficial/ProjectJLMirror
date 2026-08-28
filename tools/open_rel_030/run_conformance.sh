#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

PG_CONTAINER="jlmirror-open-rel-030-pg"
TS_CONTAINER="jlmirror-open-rel-030-ts"
DB_PASSWORD="evidence"

mapfile -t EVIDENCE_IMAGES < <(
  python3 - <<'PY'
import json
from pathlib import Path
manifest = json.loads(Path('implementation/d2-open-rel-030/EVIDENCE_MANIFEST.json').read_text())
print(manifest['database_images']['tier1_postgresql']['image'])
print(manifest['database_images']['tier2_timescale']['image'])
PY
)
PG_IMAGE="${EVIDENCE_IMAGES[0]}"
TS_IMAGE="${EVIDENCE_IMAGES[1]}"

cleanup() {
  docker rm -f "$PG_CONTAINER" "$TS_CONTAINER" >/dev/null 2>&1 || true
}
trap cleanup EXIT
cleanup

wait_for_postgres() {
  local container="$1"
  for _ in $(seq 1 60); do
    if docker exec -e PGPASSWORD="$DB_PASSWORD" "$container" \
      pg_isready -U postgres -d jlmirror >/dev/null 2>&1; then
      return 0
    fi
    sleep 1
  done
  echo "database did not become ready: $container" >&2
  docker logs "$container" >&2 || true
  return 1
}

admin_psql() {
  local container="$1"
  shift
  docker exec -e PGPASSWORD="$DB_PASSWORD" "$container" \
    psql -X -v ON_ERROR_STOP=1 -U postgres -d jlmirror "$@"
}

login_psql() {
  local container="$1"
  local user="$2"
  local password="$3"
  local sql="$4"
  docker exec -e PGPASSWORD="$password" "$container" \
    psql -X -v ON_ERROR_STOP=1 -h 127.0.0.1 -U "$user" -d jlmirror -Atq -c "$sql"
}

expect_login_failure() {
  local label="$1"
  local container="$2"
  local user="$3"
  local password="$4"
  local sql="$5"
  local output
  if output="$(login_psql "$container" "$user" "$password" "$sql" 2>&1)"; then
    echo "$label unexpectedly succeeded: $output" >&2
    return 1
  fi
  printf '%s=PASS rejected=%q\n' "$label" "$output"
}

assert_exact() {
  local label="$1"
  local expected="$2"
  local actual="$3"
  if [[ "$actual" != "$expected" ]]; then
    printf '%s expected=%q actual=%q\n' "$label" "$expected" "$actual" >&2
    return 1
  fi
  printf '%s=PASS value=%q\n' "$label" "$actual"
}

printf 'tier1_image=%s\n' "$PG_IMAGE"
printf 'tier2_image=%s\n' "$TS_IMAGE"
docker pull "$PG_IMAGE"
docker pull "$TS_IMAGE"

# ---------------------------------------------------------------------------
# Tier 1 — real multi-connection PostgreSQL acceptance evidence.
# ---------------------------------------------------------------------------
docker run -d --name "$PG_CONTAINER" \
  -e POSTGRES_PASSWORD="$DB_PASSWORD" \
  -e POSTGRES_DB=jlmirror \
  "$PG_IMAGE" >/dev/null
wait_for_postgres "$PG_CONTAINER"

printf '%s\n' '--- Tier 1 PostgreSQL version ---'
admin_psql "$PG_CONTAINER" -Atq -c "SELECT version();"

docker cp sql/d2-open-rel-030/001_tier1_acceptance.sql \
  "$PG_CONTAINER:/tmp/001_tier1_acceptance.sql"
docker cp sql/d2-open-rel-030/002_tier1_assertions.sql \
  "$PG_CONTAINER:/tmp/002_tier1_assertions.sql"
admin_psql "$PG_CONTAINER" -f /tmp/001_tier1_acceptance.sql
python3 tools/open_rel_030/tier1_concurrency.py "$PG_CONTAINER"
admin_psql "$PG_CONTAINER" -f /tmp/002_tier1_assertions.sql

# ---------------------------------------------------------------------------
# Tier 2 — Timescale candidate isolation attack matrix.
# ---------------------------------------------------------------------------
docker run -d --name "$TS_CONTAINER" \
  -e POSTGRES_PASSWORD="$DB_PASSWORD" \
  -e POSTGRES_DB=jlmirror \
  "$TS_IMAGE" >/dev/null
wait_for_postgres "$TS_CONTAINER"

docker cp sql/d2-open-rel-030/010_timescale_candidate.sql \
  "$TS_CONTAINER:/tmp/010_timescale_candidate.sql"
admin_psql "$TS_CONTAINER" -f /tmp/010_timescale_candidate.sql

TENANT_A="aaaaaaaa-0000-0000-0000-000000000001"
TENANT_B="aaaaaaaa-0000-0000-0000-000000000002"

# Trusted platform-runtime RLS profile: no context -> no rows; transaction-local
# A context -> only A. The same runtime credential can establish B only because
# this trust class assumes server-resolved trusted context; it is not exposed as
# caller-authored arbitrary SQL.
runtime_no_context="$(login_psql "$TS_CONTAINER" ts_runtime runtime-evidence-only \
  "SELECT count(*) FROM ts_evidence.rls_history;")"
assert_exact "timescale_runtime_missing_context_default_deny" "0" "$runtime_no_context"

runtime_a="$(login_psql "$TS_CONTAINER" ts_runtime runtime-evidence-only \
  "BEGIN; SET LOCAL jlmirror.tenant_id='$TENANT_A'; SELECT string_agg(tenant_id::text, ',' ORDER BY tenant_id::text) FROM ts_evidence.rls_history; COMMIT;")"
assert_exact "timescale_rowstore_rls_tenant_a" "$TENANT_A" "$runtime_a"

runtime_b="$(login_psql "$TS_CONTAINER" ts_runtime runtime-evidence-only \
  "BEGIN; SET LOCAL jlmirror.tenant_id='$TENANT_B'; SELECT string_agg(tenant_id::text, ',' ORDER BY tenant_id::text) FROM ts_evidence.rls_history; COMMIT;")"
assert_exact "timescale_rowstore_rls_tenant_b" "$TENANT_B" "$runtime_b"

expect_login_failure \
  "timescale_rowstore_rls_cross_tenant_insert" \
  "$TS_CONTAINER" ts_runtime runtime-evidence-only \
  "BEGIN; SET LOCAL jlmirror.tenant_id='$TENANT_A'; INSERT INTO ts_evidence.rls_history(tenant_id,observed_at,metric_definition_id,numeric_value) VALUES ('$TENANT_B','2026-08-28T00:00:00Z','bbbbbbbb-0000-0000-0000-000000000002',99); COMMIT;"

runtime_bypass="$(admin_psql "$TS_CONTAINER" -Atq -c \
  "SELECT rolbypassrls::text || '|' || rolsuper::text FROM pg_roles WHERE rolname='ts_runtime';")"
assert_exact "timescale_runtime_no_bypassrls" "false|false" "$runtime_bypass"

# If the direct RLS relation was converted to columnstore successfully, it must
# still never leak a second tenant. An execution error is classified as the
# direct profile being unusable; a cross-tenant result is a hard harness failure.
columnstore_supported="$(admin_psql "$TS_CONTAINER" -Atq -c \
  "SELECT supported::text FROM ts_evidence.capability_probe WHERE probe='direct_rls_plus_columnstore';")"
if [[ "$columnstore_supported" == "true" ]]; then
  set +e
  columnstore_output="$(login_psql "$TS_CONTAINER" ts_runtime runtime-evidence-only \
    "BEGIN; SET LOCAL jlmirror.tenant_id='$TENANT_A'; SELECT string_agg(tenant_id::text, ',' ORDER BY tenant_id::text) FROM ts_evidence.rls_history; COMMIT;" 2>&1)"
  columnstore_rc=$?
  set -e
  if [[ $columnstore_rc -ne 0 ]]; then
    printf 'timescale_direct_rls_columnstore_query=INELIGIBLE error=%q\n' "$columnstore_output"
  elif [[ "$columnstore_output" == "$TENANT_A" ]]; then
    printf 'timescale_direct_rls_columnstore_query=PASS value=%q\n' "$columnstore_output"
  else
    printf 'timescale_direct_rls_columnstore_query=LEAK value=%q\n' "$columnstore_output" >&2
    exit 1
  fi
else
  printf 'timescale_direct_rls_columnstore=INELIGIBLE_BY_CAPABILITY_PROBE\n'
fi

# Mediated reporting profile. The reporting principals must be unable to read
# any shared relation directly and may see only the tenant bound to their login
# identity through the fixed-search-path SECURITY DEFINER function.
expect_login_failure \
  "timescale_report_a_no_direct_raw" \
  "$TS_CONTAINER" ts_report_a report-a-evidence-only \
  "SELECT count(*) FROM ts_evidence.shared_history;"
expect_login_failure \
  "timescale_report_a_no_direct_cagg" \
  "$TS_CONTAINER" ts_report_a report-a-evidence-only \
  "SELECT count(*) FROM ts_evidence.shared_hourly;"
expect_login_failure \
  "timescale_report_a_no_mapping_read" \
  "$TS_CONTAINER" ts_report_a report-a-evidence-only \
  "SELECT count(*) FROM ts_evidence.report_principal_tenant;"

report_a="$(login_psql "$TS_CONTAINER" ts_report_a report-a-evidence-only \
  "SELECT string_agg(tenant_id::text, ',' ORDER BY tenant_id::text) FROM ts_evidence.read_hourly();")"
assert_exact "timescale_mediated_report_tenant_a" "$TENANT_A" "$report_a"

report_b="$(login_psql "$TS_CONTAINER" ts_report_b report-b-evidence-only \
  "SELECT string_agg(tenant_id::text, ',' ORDER BY tenant_id::text) FROM ts_evidence.read_hourly();")"
assert_exact "timescale_mediated_report_tenant_b" "$TENANT_B" "$report_b"

report_a_setconfig="$(login_psql "$TS_CONTAINER" ts_report_a report-a-evidence-only \
  "SET jlmirror.tenant_id='$TENANT_B'; SELECT string_agg(tenant_id::text, ',' ORDER BY tenant_id::text) FROM ts_evidence.read_hourly();")"
assert_exact "timescale_mediated_set_config_cannot_change_authority" "$TENANT_A" "$report_a_setconfig"

report_a_search_path="$(login_psql "$TS_CONTAINER" ts_report_a report-a-evidence-only \
  "SET search_path=pg_temp,public,ts_evidence; CREATE TEMP TABLE report_principal_tenant(login_name name,tenant_id uuid); INSERT INTO report_principal_tenant VALUES ('ts_report_a','$TENANT_B'); SELECT string_agg(tenant_id::text, ',' ORDER BY tenant_id::text) FROM ts_evidence.read_hourly();")"
assert_exact "timescale_mediated_search_path_shadow_cannot_change_authority" "$TENANT_A" "$report_a_search_path"

expect_login_failure \
  "timescale_mediated_set_role_owner_rejected" \
  "$TS_CONTAINER" ts_report_a report-a-evidence-only \
  "SET ROLE ts_owner; SELECT current_user;"
expect_login_failure \
  "timescale_mediated_session_authorization_rejected" \
  "$TS_CONTAINER" ts_report_a report-a-evidence-only \
  "SET SESSION AUTHORIZATION ts_report_b; SELECT session_user;"

function_security="$(admin_psql "$TS_CONTAINER" -Atq -c \
  "SELECT prosecdef::text || '|' || array_to_string(proconfig, ',') FROM pg_proc WHERE oid='ts_evidence.read_hourly()'::regprocedure;")"
if [[ "$function_security" != true\|*search_path*pg_catalog*ts_evidence* ]]; then
  printf 'timescale_security_definer_profile_invalid=%q\n' "$function_security" >&2
  exit 1
fi
printf 'timescale_security_definer_fixed_search_path=PASS value=%q\n' "$function_security"

printf '%s\n' '--- Timescale capability probes ---'
admin_psql "$TS_CONTAINER" -Atq -c \
  "SELECT probe || '|' || supported::text || '|' || coalesce(sqlstate,'') || '|' || detail FROM ts_evidence.capability_probe ORDER BY probe;"

printf '%s\n' 'open_rel_030_initial_conformance=PASS'
printf '%s\n' 'closure_claim=false remaining_vectors=see implementation/d2-open-rel-030/EVIDENCE_MANIFEST.json'
