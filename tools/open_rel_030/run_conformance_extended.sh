#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

PG_CONTAINER="jlmirror-open-rel-030-pg-extended"
TS_CONTAINER="jlmirror-open-rel-030-ts-extended"
TS_RESTORE_CONTAINER="${TS_CONTAINER}-fresh-restore"
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
  docker rm -f "$PG_CONTAINER" "$TS_CONTAINER" "$TS_RESTORE_CONTAINER" >/dev/null 2>&1 || true
}
trap cleanup EXIT
cleanup

wait_for_postgres() {
  local container="$1"
  local consecutive=0
  for _ in $(seq 1 120); do
    if docker exec -e PGPASSWORD="$DB_PASSWORD" "$container" \
      pg_isready -h 127.0.0.1 -U postgres -d jlmirror >/dev/null 2>&1; then
      consecutive=$((consecutive + 1))
      if [[ "$consecutive" -ge 3 ]]; then return 0; fi
    else
      consecutive=0
    fi
    sleep 0.25
  done
  echo "database TCP path did not become stably ready: $container" >&2
  docker logs "$container" >&2 || true
  return 1
}

admin_psql() {
  local container="$1"
  shift
  docker exec -e PGPASSWORD="$DB_PASSWORD" "$container" \
    psql -X -v ON_ERROR_STOP=1 -U postgres -d jlmirror "$@"
}

docker pull "$PG_IMAGE" >/dev/null
docker pull "$TS_IMAGE" >/dev/null

# ---------------------------------------------------------------------------
# Tier 1 extended fault/recovery vectors.
# Every ordered history-hardening module is part of the executable evidence
# chain; adding a module without wiring it here is a conformance failure.
# ---------------------------------------------------------------------------
docker run -d --name "$PG_CONTAINER" \
  -e POSTGRES_PASSWORD="$DB_PASSWORD" \
  -e POSTGRES_DB=jlmirror \
  "$PG_IMAGE" >/dev/null
wait_for_postgres "$PG_CONTAINER"

HISTORY_MODULES=(
  004_history_reconciliation.sql
  005_history_identity_window_hardening.sql
  006_history_dataset_revision_hardening.sql
  007_history_dataset_revision_edge_hardening.sql
  008_history_visibility_correction_hardening.sql
  009_history_retained_finalized_watermark_hardening.sql
  010_history_lock_order_hardening.sql
)

for file in \
  001_tier1_acceptance.sql \
  003_tier1_recovery_authority.sql \
  "${HISTORY_MODULES[@]}"
do
  docker cp "sql/d2-open-rel-030/$file" "$PG_CONTAINER:/tmp/$file"
done

admin_psql "$PG_CONTAINER" -f /tmp/001_tier1_acceptance.sql
wait_for_postgres "$PG_CONTAINER"
bash tools/open_rel_030/tier1_commit_ambiguity.sh "$PG_CONTAINER"
admin_psql "$PG_CONTAINER" -f /tmp/003_tier1_recovery_authority.sql
for file in "${HISTORY_MODULES[@]}"; do
  admin_psql "$PG_CONTAINER" -f "/tmp/$file"
done

# #51: provider-visible mutation, sweep and finalization now share one explicit
# authority-row order (provider_authority -> stream_state). Exercise real
# concurrent mutation-vs-finalize and mutation-vs-sweep races; either session
# aborting on deadlock is a conformance failure.
bash tools/open_rel_030/history_lock_order_concurrency.sh "$PG_CONTAINER"

# Native physical PostgreSQL PITR to R, with F held by a separate surviving
# authority. The end-to-end wrapper composes
# physical_pitr_active_authority_hardening.sh and then resets/replays the real
# winner through claim -> hardened fetch -> apply, proving the #45 definitions
# themselves complete a legitimate admission (#46).
bash tools/open_rel_030/physical_pitr_active_authority_end_to_end.sh "$PG_CONTAINER" "$PG_IMAGE"

# A second physical vector snapshots PGDATA only after the restored identity has
# been enrolled. Its public entrypoint delegates to a bounded async implementation
# that proves both cooperative and real-blackhole response deadlines before the
# positive-control/main authority checks (#47).
bash tools/open_rel_030/physical_pitr_post_enrollment_clone.sh "$PG_CONTAINER" "$PG_IMAGE"

# ---------------------------------------------------------------------------
# Tier 2 exact safe-profile jobs/capacity/fresh-cluster restore vectors.
# ---------------------------------------------------------------------------
docker run -d --name "$TS_CONTAINER" \
  -e POSTGRES_PASSWORD="$DB_PASSWORD" \
  -e POSTGRES_DB=jlmirror \
  "$TS_IMAGE" >/dev/null
wait_for_postgres "$TS_CONTAINER"

for file in 010_timescale_candidate.sql 011_timescale_jobs_capacity.sql; do
  docker cp "sql/d2-open-rel-030/$file" "$TS_CONTAINER:/tmp/$file"
done

admin_psql "$TS_CONTAINER" -f /tmp/010_timescale_candidate.sql
wait_for_postgres "$TS_CONTAINER"
admin_psql "$TS_CONTAINER" -f /tmp/011_timescale_jobs_capacity.sql
wait_for_postgres "$TS_CONTAINER"

# Restore into a separate Timescale container, prove JLMirror roles were absent,
# reconstruct the minimum topology and repeat isolation/escalation/job attacks.
bash tools/open_rel_030/timescale_jobs_restore.sh "$TS_CONTAINER" "$TS_IMAGE"

# Cross-store relocation: source fencing, era/non-finite-aware canonical payload
# equivalence, target checkpoint authority and activation grant jointly permit
# cutover only after all negative vectors pass. The ordered verifier composition
# installs session-retirement timeout semantics before those authority tests (#48).
bash tools/open_rel_030/tenant_relocation.sh "$PG_CONTAINER" "$TS_CONTAINER"

printf '%s\n' 'open_rel_030_extended_conformance=PASS'
printf '%s\n' 'closure_claim=false governed Track B acceptance still required; production/Wave4/merge authorization not granted'
