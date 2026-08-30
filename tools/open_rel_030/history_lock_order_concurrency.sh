#!/usr/bin/env bash
set -euo pipefail

PG_CONTAINER="${1:?postgres container name required}"
DB_PASSWORD="${DB_PASSWORD:-evidence}"

psql_admin() {
  docker exec -i -e PGPASSWORD="$DB_PASSWORD" "$PG_CONTAINER" \
    psql -X -v ON_ERROR_STOP=1 -U postgres -d jlmirror "$@"
}

setup_stream() {
  local stream_id="$1"
  psql_admin -q <<SQL
INSERT INTO history_reconcile_evidence.stream_state (
    stream_id, supported_history_floor, state
) VALUES (
    '$stream_id', '2026-08-28T11:00:00Z', 'reconciliation_required'
);
INSERT INTO history_reconcile_evidence.provider_authority (
    stream_id, authority_generation, current_snapshot_at,
    finality_floor, required_reconciliation_snapshot_at
) VALUES (
    '$stream_id', 1,
    '2026-08-28T13:00:00Z', '2026-08-28T13:00:00Z', '2026-08-28T13:00:00Z'
);
SQL
}

wait_holder_sleeping() {
  local app_name="$1"
  local ready=0
  for _ in $(seq 1 80); do
    ready="$(psql_admin -Atq -c "SELECT count(*) FROM pg_stat_activity WHERE application_name='$app_name' AND state='active' AND query LIKE '%pg_sleep(2)%';")"
    if [[ "$ready" == "1" ]]; then
      return 0
    fi
    sleep 0.025
  done
  echo "history lock-order holder did not reach post-provider-lock sleep: $app_name" >&2
  return 1
}

run_race() {
  local name="$1"
  local stream_id="$2"
  local worker_sql="$3"
  local expected_pattern="$4"
  local marker="$5"
  local holder_app="history_lock_holder_${name}"
  local worker_app="history_lock_worker_${name}"
  local holder_log worker_log holder_pid worker_pid holder_rc worker_rc

  holder_log="$(mktemp)"
  worker_log="$(mktemp)"
  trap 'rm -f "$holder_log" "$worker_log"' RETURN

  setup_stream "$stream_id"

  docker exec -i -e PGPASSWORD="$DB_PASSWORD" "$PG_CONTAINER" \
    psql -X -v ON_ERROR_STOP=1 -U postgres -d jlmirror >"$holder_log" 2>&1 <<SQL &
SET application_name = '$holder_app';
BEGIN;
SELECT 1
  FROM history_reconcile_evidence.provider_authority
 WHERE stream_id = '$stream_id'
 FOR UPDATE;
SELECT pg_sleep(2);
SELECT history_reconcile_evidence.invalidate_provider_dataset('$stream_id');
COMMIT;
SQL
  holder_pid=$!

  wait_holder_sleeping "$holder_app"

  timeout 8s docker exec -i -e PGPASSWORD="$DB_PASSWORD" "$PG_CONTAINER" \
    psql -X -v ON_ERROR_STOP=1 -U postgres -d jlmirror >"$worker_log" 2>&1 <<SQL &
SET application_name = '$worker_app';
SET ROLE history_reconcile_worker;
$worker_sql
RESET ROLE;
SQL
  worker_pid=$!

  set +e
  wait "$holder_pid"
  holder_rc=$?
  wait "$worker_pid"
  worker_rc=$?
  set -e

  if [[ "$holder_rc" -ne 0 || "$worker_rc" -ne 0 ]]; then
    echo "history lock-order race failed: $name holder_rc=$holder_rc worker_rc=$worker_rc" >&2
    echo "--- holder ---" >&2
    cat "$holder_log" >&2
    echo "--- worker ---" >&2
    cat "$worker_log" >&2
    return 1
  fi

  if grep -Eqi 'deadlock detected|canceling statement|statement timeout|lock timeout' "$holder_log" "$worker_log"; then
    echo "history lock-order race observed lock failure: $name" >&2
    cat "$holder_log" "$worker_log" >&2
    return 1
  fi

  if ! grep -Eq "$expected_pattern" "$worker_log"; then
    echo "history lock-order race worker result mismatch: $name" >&2
    cat "$worker_log" >&2
    return 1
  fi

  printf '%s\n' "$marker"
}

run_race \
  finalize \
  'zabbix:item:lock-order-finalize' \
  "SELECT history_reconcile_evidence.try_finalize('zabbix:item:lock-order-finalize','2026-08-28T11:15:00Z') AS finalized;" \
  '^[[:space:]]*f[[:space:]]*$' \
  'history_finalization_lock_order_concurrency=PASS'

run_race \
  sweep \
  'zabbix:item:lock-order-sweep' \
  "SELECT history_reconcile_evidence.sweep('zabbix:item:lock-order-sweep','2026-08-28T11:00:00Z','2026-08-28T11:15:00Z',1) AS discovered;" \
  '^[[:space:]]*0[[:space:]]*$' \
  'history_sweep_lock_order_concurrency=PASS'

printf '%s\n' 'history_authority_lock_order=provider_authority_then_stream_state=PASS'
