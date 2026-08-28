#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

PG_CONTAINER="jlmirror-open-rel-030-pg-extended"
TS_CONTAINER="jlmirror-open-rel-030-ts-extended"
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
  local consecutive=0
  for _ in $(seq 1 120); do
    if docker exec -e PGPASSWORD="$DB_PASSWORD" "$container" \
      pg_isready -h 127.0.0.1 -U postgres -d jlmirror >/dev/null 2>&1; then
      consecutive=$((consecutive + 1))
      if [[ "$consecutive" -ge 3 ]]; then
        return 0
      fi
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
# ---------------------------------------------------------------------------
docker run -d --name "$PG_CONTAINER" \
  -e POSTGRES_PASSWORD="$DB_PASSWORD" \
  -e POSTGRES_DB=jlmirror \
  "$PG_IMAGE" >/dev/null
wait_for_postgres "$PG_CONTAINER"

for file in \
  001_tier1_acceptance.sql \
  003_tier1_recovery_authority.sql \
  004_history_reconciliation.sql
do
  docker cp "sql/d2-open-rel-030/$file" "$PG_CONTAINER:/tmp/$file"
done

admin_psql "$PG_CONTAINER" -f /tmp/001_tier1_acceptance.sql
wait_for_postgres "$PG_CONTAINER"
bash tools/open_rel_030/tier1_commit_ambiguity.sh "$PG_CONTAINER"
admin_psql "$PG_CONTAINER" -f /tmp/003_tier1_recovery_authority.sql
admin_psql "$PG_CONTAINER" -f /tmp/004_history_reconciliation.sql

# Native physical PostgreSQL PITR to R, with F held by a separate surviving
# authority. This must pass before the restored authority may be admitted.
bash tools/open_rel_030/physical_pitr.sh "$PG_CONTAINER" "$PG_IMAGE"

# ---------------------------------------------------------------------------
# Tier 2 exact safe-profile jobs/capacity/restore vectors.
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
bash tools/open_rel_030/timescale_jobs_restore.sh "$TS_CONTAINER"

# Cross-store relocation: Tier 1 source fencing and Tier 2 projection watermark
# must jointly permit target activation; stale source writes remain rejected.
bash tools/open_rel_030/tenant_relocation.sh "$PG_CONTAINER" "$TS_CONTAINER"

printf '%s\n' 'open_rel_030_extended_conformance=PASS'
printf '%s\n' 'closure_claim=false final evidence classification and governed decision update still required'
