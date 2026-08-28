#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "usage: tier1_commit_ambiguity.sh <postgres-container-name>" >&2
  exit 2
fi

container="$1"
password="evidence"
tenant="12121212-1212-1212-1212-121212121212"
metric="23232323-2323-2323-2323-232323232323"
source_generation="34343434-3434-3434-3434-343434343434"
observation="45454545-4545-4545-4545-454545454545"

psql_exec() {
  docker exec -e PGPASSWORD="$password" "$container" \
    psql -X -v ON_ERROR_STOP=1 -U postgres -d jlmirror -Atq -c "$1"
}

# The client performs the authoritative transaction and then blocks in an
# unrelated query. A second connection observes the committed row before we
# terminate the first client. From the first caller's perspective the command
# never returned success, so its outcome is ambiguous despite the commit being
# durable.
sql="
BEGIN;
SELECT * FROM tel_evidence.accept_observation(
  '$tenant'::uuid,
  'ambiguity-vector',
  '$observation'::uuid,
  '$metric'::uuid,
  '$source_generation'::uuid,
  '$source_generation'::uuid,
  20,
  1,
  '2026-08-28T13:00:00Z'::timestamptz,
  123.45,
  true,
  NULL
);
COMMIT;
SELECT pg_sleep(30);
"

set +e
docker exec -e PGPASSWORD="$password" "$container" \
  psql -X -v ON_ERROR_STOP=1 -U postgres -d jlmirror -Atq -c "$sql" \
  >/tmp/jlmirror-open-rel-030-ambiguous-client.out 2>&1 &
client_pid=$!
set -e

committed=0
for _ in $(seq 1 100); do
  count="$(psql_exec "SELECT count(*) FROM tel_evidence.observation WHERE tenant_id='$tenant'::uuid AND observation_identity_scope='ambiguity-vector' AND observation_id='$observation'::uuid;")"
  if [[ "$count" == "1" ]]; then
    committed=1
    break
  fi
  sleep 0.05
done

if [[ "$committed" != "1" ]]; then
  cat /tmp/jlmirror-open-rel-030-ambiguous-client.out >&2 || true
  kill "$client_pid" >/dev/null 2>&1 || true
  wait "$client_pid" >/dev/null 2>&1 || true
  echo "ambiguous client transaction never became externally visible" >&2
  exit 1
fi

# Lose the client-side result after commit has been proven by a separate DB
# session. The caller cannot distinguish success from transport loss.
kill -TERM "$client_pid" >/dev/null 2>&1 || true
set +e
wait "$client_pid"
client_rc=$?
set -e
if [[ "$client_rc" -eq 0 ]]; then
  echo "ambiguity injection failed: client returned success instead of being interrupted" >&2
  exit 1
fi

# Retry with the same canonical identity. It must observe the committed result,
# not create another durable observation/history obligation/semantic signal.
retry="$(psql_exec "
SELECT newly_accepted::text || '|' || ordering_advanced::text || '|' || semantic_transition::text
FROM tel_evidence.accept_observation(
  '$tenant'::uuid,
  'ambiguity-vector',
  '$observation'::uuid,
  '$metric'::uuid,
  '$source_generation'::uuid,
  '$source_generation'::uuid,
  20,
  1,
  '2026-08-28T13:00:00Z'::timestamptz,
  123.45,
  true,
  NULL
);")"

if [[ "$retry" != "false|false|false" && "$retry" != "f|f|f" ]]; then
  echo "ambiguous retry did not converge idempotently: $retry" >&2
  exit 1
fi

counts="$(psql_exec "
SELECT
  (SELECT count(*) FROM tel_evidence.observation
    WHERE tenant_id='$tenant'::uuid AND observation_identity_scope='ambiguity-vector' AND observation_id='$observation'::uuid)::text
  || '|' ||
  (SELECT count(*) FROM tel_evidence.historical_projection_outbox
    WHERE tenant_id='$tenant'::uuid AND observation_identity_scope='ambiguity-vector' AND observation_id='$observation'::uuid)::text
  || '|' ||
  (SELECT count(*) FROM tel_evidence.current_changed_outbox
    WHERE tenant_id='$tenant'::uuid AND metric_definition_id='$metric'::uuid)::text;")"

if [[ "$counts" != "1|1|1" ]]; then
  echo "ambiguous post-commit retry duplicated/lost durable state: $counts" >&2
  exit 1
fi

printf 'tier1_post_commit_ambiguity=PASS client_rc=%s retry=%s counts=%s\n' \
  "$client_rc" "$retry" "$counts"
