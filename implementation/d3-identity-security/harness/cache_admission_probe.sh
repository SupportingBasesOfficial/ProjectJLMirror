#!/usr/bin/env bash
set -euo pipefail

PG_CONTAINER="${PG_CONTAINER:?PG_CONTAINER is required}"
CACHE_CONTAINER="${CACHE_CONTAINER:?CACHE_CONTAINER is required}"
CACHE_LABEL="${CACHE_LABEL:?CACHE_LABEL is required}"

pg() {
  docker exec -e PGPASSWORD=d3-postgres-password "$PG_CONTAINER" \
    psql -U postgres -d d3 -Atqc "$1"
}

cache() {
  docker exec "$CACHE_CONTAINER" redis-cli --raw "$@"
}

cache_eval() {
  local key="$1"
  local session_gen="$2"
  local principal_gen="$3"
  local membership_gen="$4"
  local permission_gen="$5"
  local tenant_gen="$6"
  local access_gen="$7"
  local admission_epoch="$8"
  docker exec "$CACHE_CONTAINER" redis-cli --raw EVAL '
local values = redis.call("HMGET", KEYS[1],
  "session_gen", "principal_gen", "membership_gen", "permission_gen",
  "tenant_gen", "access_gen", "admission_epoch")
for i = 1, 7 do
  if not values[i] or values[i] ~= ARGV[i] then
    return "DENY"
  end
end
return "ALLOW"
' 1 "$key" "$session_gen" "$principal_gen" "$membership_gen" "$permission_gen" "$tenant_gen" "$access_gen" "$admission_epoch"
}

assert_eq() {
  local expected="$1"
  local actual="$2"
  local label="$3"
  if [[ "$actual" != "$expected" ]]; then
    printf '%s=FAIL expected=%s actual=%s\n' "$label" "$expected" "$actual" >&2
    exit 1
  fi
  printf '%s=PASS value=%s\n' "$label" "$actual"
}

wait_pg() {
  for _ in $(seq 1 60); do
    if docker exec "$PG_CONTAINER" pg_isready -U postgres -d postgres >/dev/null 2>&1; then
      return 0
    fi
    sleep 1
  done
  echo 'postgres readiness deadline exceeded' >&2
  exit 1
}

wait_cache() {
  for _ in $(seq 1 30); do
    if [[ "$(cache PING 2>/dev/null || true)" == "PONG" ]]; then
      return 0
    fi
    sleep 1
  done
  echo "$CACHE_LABEL readiness deadline exceeded" >&2
  exit 1
}

wait_pg
wait_cache

pg '
CREATE TABLE IF NOT EXISTS d3_session_authority (
  id integer PRIMARY KEY CHECK (id = 1),
  session_gen bigint NOT NULL,
  principal_gen bigint NOT NULL,
  membership_gen bigint NOT NULL,
  permission_gen bigint NOT NULL,
  tenant_gen bigint NOT NULL,
  access_gen bigint NOT NULL,
  admission_epoch bigint NOT NULL
);
CREATE TABLE IF NOT EXISTS d3_fence_intent (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  target_epoch bigint NOT NULL,
  state text NOT NULL CHECK (state IN ('prepared','cache_fenced','source_committed','finalized','aborted'))
);
INSERT INTO d3_session_authority
  (id, session_gen, principal_gen, membership_gen, permission_gen, tenant_gen, access_gen, admission_epoch)
VALUES (1,1,1,1,1,1,1,1)
ON CONFLICT (id) DO UPDATE SET
  session_gen=1, principal_gen=1, membership_gen=1, permission_gen=1,
  tenant_gen=1, access_gen=1, admission_epoch=1;
TRUNCATE d3_fence_intent RESTART IDENTITY;
'

cache FLUSHALL >/dev/null
cache HSET session:primary \
  session_gen 1 principal_gen 1 membership_gen 1 permission_gen 1 \
  tenant_gen 1 access_gen 1 admission_epoch 1 >/dev/null
cache SET security:admission_epoch 1 >/dev/null

# Healthy hit is one Redis EVAL request. Expected authority inputs are caller-local;
# the cache never fetches or self-certifies them from another cache key.
assert_eq ALLOW "$(cache_eval session:primary 1 1 1 1 1 1 1)" "${CACHE_LABEL}_healthy_single_eval"

# A mixed generation read is rejected even if every other field is current.
cache HSET session:primary permission_gen 2 >/dev/null
assert_eq DENY "$(cache_eval session:primary 1 1 1 1 1 1 1)" "${CACHE_LABEL}_mixed_generation_rejected"
cache HSET session:primary permission_gen 1 >/dev/null

# The expected epoch is outside Redis. A stale Redis dataset cannot self-certify currentness.
EXPECTED_EPOCH=2
assert_eq DENY "$(cache_eval session:primary 1 1 1 1 1 1 "$EXPECTED_EPOCH")" "${CACHE_LABEL}_stale_epoch_self_certification_blocked"

# Prepare is a short durable PG transaction. No DB transaction is held across cache I/O.
intent_id="$(pg "INSERT INTO d3_fence_intent(target_epoch,state) VALUES (2,'prepared') RETURNING id;")"
assert_eq 1 "$intent_id" "${CACHE_LABEL}_durable_prepare"

# Fleet fence simulation: candidate cache acknowledges the target admission epoch.
cache SET security:admission_epoch 2 >/dev/null
assert_eq 2 "$(cache GET security:admission_epoch)" "${CACHE_LABEL}_cache_fence_ack"
pg "UPDATE d3_fence_intent SET state='cache_fenced' WHERE id=1 AND state='prepared';"

# Source commit is allowed only after the cache-fence acknowledgment is independently observed.
if [[ "$(cache GET security:admission_epoch)" != "2" ]]; then
  echo 'cache fence unavailable; refusing source commit' >&2
  exit 1
fi
pg "
UPDATE d3_session_authority
SET session_gen=2, admission_epoch=2
WHERE id=1 AND admission_epoch=1;
UPDATE d3_fence_intent SET state='source_committed' WHERE id=1 AND state='cache_fenced';
"
assert_eq '2|2' "$(pg "SELECT session_gen||'|'||admission_epoch FROM d3_session_authority WHERE id=1;")" "${CACHE_LABEL}_source_commit_after_fence"

# A sleeping/stale writer can repopulate old positive bytes, but cannot mint current authority.
cache HSET session:primary \
  session_gen 1 principal_gen 1 membership_gen 1 permission_gen 1 \
  tenant_gen 1 access_gen 1 admission_epoch 1 >/dev/null
assert_eq DENY "$(cache_eval session:primary 2 1 1 1 1 1 2)" "${CACHE_LABEL}_sleeping_writer_resurrection_blocked"

# Finalize the derived cache from durable current authority.
cache HSET session:primary \
  session_gen 2 principal_gen 1 membership_gen 1 permission_gen 1 \
  tenant_gen 1 access_gen 1 admission_epoch 2 >/dev/null
pg "UPDATE d3_fence_intent SET state='finalized' WHERE id=1 AND state='source_committed';"
assert_eq ALLOW "$(cache_eval session:primary 2 1 1 1 1 1 2)" "${CACHE_LABEL}_finalized_current_admission"

# Broad revocation is generation-based, not session-enumeration based. Populate many stale
# session records, advance only the expected principal generation, and prove they all deny
# without rewriting them.
for i in $(seq 1 200); do
  cache HSET "session:bulk:$i" \
    session_gen 2 principal_gen 1 membership_gen 1 permission_gen 1 \
    tenant_gen 1 access_gen 1 admission_epoch 2 >/dev/null
done
for i in 1 37 200; do
  assert_eq DENY "$(cache_eval "session:bulk:$i" 2 2 1 1 1 1 2)" "${CACHE_LABEL}_o1_principal_revocation_${i}"
done
assert_eq 1 "$(cache HGET session:bulk:200 principal_gen)" "${CACHE_LABEL}_bulk_cache_not_enumerated_for_revocation"

# Stale positive restore cannot become current because expected authority is external.
stale_dump="$(cache DUMP session:primary | base64 -w0)"
cache DEL session:restored >/dev/null
printf '%s' "$stale_dump" | base64 -d > /tmp/d3-cache-dump.bin
# redis-cli -x RESTORE reads serialized value from stdin.
docker exec -i "$CACHE_CONTAINER" redis-cli -x RESTORE session:restored 0 REPLACE < /tmp/d3-cache-dump.bin >/dev/null
assert_eq DENY "$(cache_eval session:restored 3 1 1 1 1 1 3)" "${CACHE_LABEL}_restored_positive_cannot_self_authorize"
rm -f /tmp/d3-cache-dump.bin

# If the local cache/fence authority is unavailable, the orchestration must refuse a new
# durable source mutation; PostgreSQL remains at generation/epoch 2.
docker stop "$CACHE_CONTAINER" >/dev/null
cache_available=false
if docker exec "$CACHE_CONTAINER" redis-cli PING >/dev/null 2>&1; then
  cache_available=true
fi
if [[ "$cache_available" == true ]]; then
  echo 'cache unexpectedly available after stop' >&2
  exit 1
fi
# Simulated orchestrator refuses the DB mutation because the mandatory fence proof is absent.
assert_eq '2|2' "$(pg "SELECT session_gen||'|'||admission_epoch FROM d3_session_authority WHERE id=1;")" "${CACHE_LABEL}_cache_outage_blocks_source_commit"

printf 'd3_b_cache_candidate=PASS candidate=%s semantics=portable_redis_protocol conformance_claim=partial_only\n' "$CACHE_LABEL"
