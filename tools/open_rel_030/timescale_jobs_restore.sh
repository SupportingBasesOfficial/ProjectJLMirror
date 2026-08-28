#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "usage: timescale_jobs_restore.sh <timescale-container-name>" >&2
  exit 2
fi

container="$1"
password="evidence"
source_db="jlmirror"
restore_db="jlmirror_restore"
tenant_a="aaaaaaaa-0000-0000-0000-000000000001"
tenant_b="aaaaaaaa-0000-0000-0000-000000000002"

admin_psql() {
  local db="$1"
  local sql="$2"
  docker exec -e PGPASSWORD="$password" "$container" \
    psql -X -v ON_ERROR_STOP=1 -U postgres -d "$db" -Atq -c "$sql"
}

login_psql() {
  local db="$1"
  local user="$2"
  local user_password="$3"
  local sql="$4"
  docker exec -e PGPASSWORD="$user_password" "$container" \
    psql -X -v ON_ERROR_STOP=1 -h 127.0.0.1 -U "$user" -d "$db" -Atq -c "$sql"
}

expect_login_failure() {
  local label="$1"
  local db="$2"
  local user="$3"
  local user_password="$4"
  local sql="$5"
  local output
  if output="$(login_psql "$db" "$user" "$user_password" "$sql" 2>&1)"; then
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

attack_profile() {
  local db="$1"
  local prefix="$2"

  expect_login_failure \
    "${prefix}_report_a_no_direct_raw" \
    "$db" ts_report_a report-a-evidence-only \
    "SELECT count(*) FROM ts_evidence.shared_history;"

  expect_login_failure \
    "${prefix}_report_a_no_direct_cagg" \
    "$db" ts_report_a report-a-evidence-only \
    "SELECT count(*) FROM ts_evidence.shared_hourly;"

  local materialization
  materialization="$(admin_psql "$db" "
    SELECT quote_ident(materialization_hypertable_schema) || '.' || quote_ident(materialization_hypertable_name)
    FROM timescaledb_information.continuous_aggregates
    WHERE view_schema='ts_evidence' AND view_name='shared_hourly';
  ")"
  if [[ -z "$materialization" ]]; then
    echo "${prefix}: could not resolve continuous-aggregate materialization relation" >&2
    return 1
  fi
  expect_login_failure \
    "${prefix}_report_a_no_internal_materialization" \
    "$db" ts_report_a report-a-evidence-only \
    "SELECT count(*) FROM $materialization;"

  local report_a report_b
  report_a="$(login_psql "$db" ts_report_a report-a-evidence-only \
    "SELECT string_agg(DISTINCT tenant_id::text, ',' ORDER BY tenant_id::text) FROM ts_evidence.read_hourly();")"
  report_b="$(login_psql "$db" ts_report_b report-b-evidence-only \
    "SELECT string_agg(DISTINCT tenant_id::text, ',' ORDER BY tenant_id::text) FROM ts_evidence.read_hourly();")"
  assert_exact "${prefix}_report_a_tenant_bound" "$tenant_a" "$report_a"
  assert_exact "${prefix}_report_b_tenant_bound" "$tenant_b" "$report_b"

  local setconfig searchpath
  setconfig="$(login_psql "$db" ts_report_a report-a-evidence-only \
    "SET jlmirror.tenant_id='$tenant_b'; SELECT string_agg(DISTINCT tenant_id::text, ',' ORDER BY tenant_id::text) FROM ts_evidence.read_hourly();")"
  assert_exact "${prefix}_setconfig_cannot_change_authority" "$tenant_a" "$setconfig"

  searchpath="$(login_psql "$db" ts_report_a report-a-evidence-only \
    "SET search_path=pg_temp,public,ts_evidence; CREATE TEMP TABLE report_principal_tenant(login_name name,tenant_id uuid); INSERT INTO report_principal_tenant VALUES ('ts_report_a','$tenant_b'); SELECT string_agg(DISTINCT tenant_id::text, ',' ORDER BY tenant_id::text) FROM ts_evidence.read_hourly();")"
  assert_exact "${prefix}_search_path_shadow_cannot_change_authority" "$tenant_a" "$searchpath"

  expect_login_failure \
    "${prefix}_set_role_owner_rejected" \
    "$db" ts_report_a report-a-evidence-only \
    "SET ROLE ts_owner; SELECT current_user;"
  expect_login_failure \
    "${prefix}_set_role_automation_owner_rejected" \
    "$db" ts_report_a report-a-evidence-only \
    "SET ROLE ts_automation_owner; SELECT current_user;"
  expect_login_failure \
    "${prefix}_set_role_runtime_rejected" \
    "$db" ts_report_a report-a-evidence-only \
    "SET ROLE ts_runtime; SELECT current_user;"
  expect_login_failure \
    "${prefix}_session_authorization_rejected" \
    "$db" ts_report_a report-a-evidence-only \
    "SET SESSION AUTHORIZATION ts_report_b; SELECT session_user;"
  expect_login_failure \
    "${prefix}_grant_owner_membership_rejected" \
    "$db" ts_report_a report-a-evidence-only \
    "GRANT ts_owner TO ts_report_a;"
  expect_login_failure \
    "${prefix}_grant_automation_owner_membership_rejected" \
    "$db" ts_report_a report-a-evidence-only \
    "GRANT ts_automation_owner TO ts_report_a;"
  expect_login_failure \
    "${prefix}_grant_raw_select_rejected" \
    "$db" ts_report_a report-a-evidence-only \
    "GRANT SELECT ON ts_evidence.shared_history TO ts_report_a;"
  expect_login_failure \
    "${prefix}_bypassrls_escalation_rejected" \
    "$db" ts_report_a report-a-evidence-only \
    "ALTER ROLE ts_report_a BYPASSRLS;"

  local function_security owner_profile
  function_security="$(admin_psql "$db" "
    SELECT prosecdef::text || '|' || array_to_string(proconfig, ',')
    FROM pg_proc
    WHERE oid='ts_evidence.read_hourly()'::regprocedure;
  ")"
  if [[ "$function_security" != true\|*search_path*pg_catalog*ts_evidence* ]]; then
    printf '%s_security_definer_invalid=%q\n' "$prefix" "$function_security" >&2
    return 1
  fi
  printf '%s_security_definer=PASS value=%q\n' "$prefix" "$function_security"

  owner_profile="$(admin_psql "$db" "
    SELECT string_agg(
      rolname || ':' || rolcanlogin::text || ':' || rolsuper::text || ':' || rolcreaterole::text || ':' || rolbypassrls::text,
      ',' ORDER BY rolname
    )
    FROM pg_roles
    WHERE rolname IN ('ts_owner','ts_automation_owner');
  ")"
  assert_exact "${prefix}_owner_trust_classes" \
    "ts_automation_owner:true:false:false:false,ts_owner:false:false:false:false" \
    "$owner_profile"
}

mapfile -t job_ids < <(admin_psql "$source_db" \
  "SELECT job_id FROM ts_evidence.job_evidence ORDER BY job_id;")
if [[ ${#job_ids[@]} -lt 2 ]]; then
  echo "expected at least two Timescale policy jobs" >&2
  exit 1
fi
for job_id in "${job_ids[@]}"; do
  echo "timescale_run_job job_id=$job_id"
  admin_psql "$source_db" "CALL public.run_job($job_id);" >/dev/null
  echo "timescale_run_job_${job_id}=PASS"
done

attack_profile "$source_db" "timescale_post_job"

start_ns="$(date +%s%N)"
row_count="$(login_psql "$source_db" ts_report_a report-a-evidence-only \
  "SELECT count(*) FROM ts_evidence.read_hourly();")"
end_ns="$(date +%s%N)"
if [[ "$row_count" -le 0 ]]; then
  echo "mediated capacity query returned no rows" >&2
  exit 1
fi
printf 'timescale_mediated_capacity_query=MEASURED rows=%s duration_ns=%s\n' \
  "$row_count" "$((end_ns - start_ns))"

docker exec -e PGPASSWORD="$password" "$container" \
  pg_dump -U postgres -d "$source_db" -Fc -f /tmp/open-rel-030-timescale.bak

admin_psql postgres "DROP DATABASE IF EXISTS $restore_db WITH (FORCE);" >/dev/null
admin_psql postgres "CREATE DATABASE $restore_db;" >/dev/null
admin_psql "$restore_db" "CREATE EXTENSION IF NOT EXISTS timescaledb;" >/dev/null
admin_psql "$restore_db" "SELECT public.timescaledb_pre_restore();" >/dev/null

docker exec -e PGPASSWORD="$password" "$container" \
  pg_restore -U postgres -d "$restore_db" --exit-on-error \
  /tmp/open-rel-030-timescale.bak

admin_psql "$restore_db" "SELECT public.timescaledb_post_restore();" >/dev/null
admin_psql "$restore_db" "ANALYZE;" >/dev/null

versions="$(admin_psql "$restore_db" \
  "SELECT current_setting('server_version') || '|' || extversion FROM pg_extension WHERE extname='timescaledb';")"
printf 'timescale_restore_versions=%s\n' "$versions"

restored_count="$(admin_psql "$restore_db" "SELECT count(*) FROM ts_evidence.shared_history;")"
source_count="$(admin_psql "$source_db" "SELECT count(*) FROM ts_evidence.shared_history;")"
assert_exact "timescale_restore_row_count" "$source_count" "$restored_count"

restore_jobs="$(admin_psql "$restore_db" "
  SELECT count(*) FROM timescaledb_information.jobs
  WHERE hypertable_schema='ts_evidence'
    AND hypertable_name IN ('shared_history','shared_hourly');
")"
if [[ "$restore_jobs" -lt 2 ]]; then
  echo "Timescale restore lost expected background jobs: $restore_jobs" >&2
  exit 1
fi
printf 'timescale_restore_jobs=PASS count=%s\n' "$restore_jobs"

attack_profile "$restore_db" "timescale_post_restore"

restored_job="$(admin_psql "$restore_db" "
  SELECT job_id FROM timescaledb_information.jobs
  WHERE hypertable_schema='ts_evidence'
    AND hypertable_name IN ('shared_history','shared_hourly')
  ORDER BY job_id LIMIT 1;
")"
admin_psql "$restore_db" "CALL public.run_job($restored_job);" >/dev/null
attack_profile "$restore_db" "timescale_post_restore_job"

printf 'timescale_jobs_restore=PASS source_rows=%s restored_rows=%s\n' \
  "$source_count" "$restored_count"
