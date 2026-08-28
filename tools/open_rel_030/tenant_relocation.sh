#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 2 ]]; then
  echo "usage: tenant_relocation.sh <tier1-postgres-container> <tier2-timescale-container>" >&2
  exit 2
fi

pg_container="$1"
ts_container="$2"
password="evidence"
tenant="aaaaaaaa-0000-0000-0000-000000000001"
race_out="$(mktemp)"

cleanup() {
  rm -f "$race_out" >/dev/null 2>&1 || true
}
trap cleanup EXIT

pg_sql() {
  local sql="$1"
  docker exec -e PGPASSWORD="$password" "$pg_container" \
    psql -X -v ON_ERROR_STOP=1 -U postgres -d jlmirror -Atq -c "$sql"
}

ts_sql() {
  local sql="$1"
  docker exec -e PGPASSWORD="$password" "$ts_container" \
    psql -X -v ON_ERROR_STOP=1 -U postgres -d jlmirror -Atq -c "$sql"
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

# Tier 1 owns acceptance, the relocation fence and the durable projection
# reconciliation receipt. Target activation never trusts a caller-provided
# watermark alone.
pg_sql "
  DROP SCHEMA IF EXISTS relocation_evidence CASCADE;
  CREATE SCHEMA relocation_evidence;

  CREATE TABLE relocation_evidence.placement (
    tenant_id uuid PRIMARY KEY,
    phase text NOT NULL CHECK (phase IN ('active','fenced')),
    current_writer text NOT NULL CHECK (current_writer IN ('source','target','none')),
    placement_version bigint NOT NULL,
    fence_ordinal bigint
  );

  CREATE TABLE relocation_evidence.acceptance (
    accepted_ordinal bigserial PRIMARY KEY,
    tenant_id uuid NOT NULL,
    observation_id text NOT NULL,
    accepted_by text NOT NULL,
    placement_version bigint NOT NULL,
    UNIQUE (tenant_id, observation_id)
  );

  CREATE TABLE relocation_evidence.projection_receipt (
    tenant_id uuid NOT NULL,
    fence_ordinal bigint NOT NULL,
    authoritative_count bigint NOT NULL,
    authoritative_digest text NOT NULL,
    target_count bigint NOT NULL,
    target_digest text NOT NULL,
    target_max_ordinal bigint NOT NULL,
    state text NOT NULL CHECK (state IN ('complete','incomplete')),
    verified_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (tenant_id, fence_ordinal)
  );

  CREATE OR REPLACE FUNCTION relocation_evidence.accept_observation(
    p_tenant uuid,
    p_writer text,
    p_placement_version bigint,
    p_observation_id text,
    p_hold_after_lock_seconds double precision DEFAULT 0
  ) RETURNS boolean
  LANGUAGE plpgsql
  AS \$\$
  DECLARE
    v_phase text;
    v_writer text;
    v_version bigint;
    v_inserted bigint;
  BEGIN
    SELECT phase,current_writer,placement_version
      INTO v_phase,v_writer,v_version
      FROM relocation_evidence.placement
     WHERE tenant_id=p_tenant
     FOR UPDATE;

    IF v_phase <> 'active' OR v_writer <> p_writer OR v_version <> p_placement_version THEN
      RETURN false;
    END IF;

    IF p_hold_after_lock_seconds > 0 THEN
      PERFORM pg_sleep(p_hold_after_lock_seconds);
    END IF;

    INSERT INTO relocation_evidence.acceptance
      (tenant_id,observation_id,accepted_by,placement_version)
    VALUES (p_tenant,p_observation_id,p_writer,p_placement_version)
    ON CONFLICT (tenant_id,observation_id) DO NOTHING;
    GET DIAGNOSTICS v_inserted = ROW_COUNT;
    RETURN v_inserted = 1;
  END;
  \$\$;

  CREATE OR REPLACE FUNCTION relocation_evidence.fence_source(p_tenant uuid)
  RETURNS bigint
  LANGUAGE plpgsql
  AS \$\$
  DECLARE
    v_phase text;
    v_writer text;
    v_f bigint;
  BEGIN
    -- Lock the placement authority before observing the accepted set. Any
    -- acceptance that already owns this lock must commit/rollback first; any
    -- later acceptance observes the fenced state and is rejected.
    SELECT phase,current_writer
      INTO v_phase,v_writer
      FROM relocation_evidence.placement
     WHERE tenant_id=p_tenant
     FOR UPDATE;

    IF v_phase <> 'active' OR v_writer <> 'source' THEN
      RAISE EXCEPTION 'source fence lost single-winner authority';
    END IF;

    SELECT coalesce(max(accepted_ordinal),0) INTO v_f
      FROM relocation_evidence.acceptance
     WHERE tenant_id=p_tenant;

    UPDATE relocation_evidence.placement
       SET phase='fenced',current_writer='none',fence_ordinal=v_f
     WHERE tenant_id=p_tenant;
    RETURN v_f;
  END;
  \$\$;

  CREATE OR REPLACE FUNCTION relocation_evidence.record_projection_receipt(
    p_tenant uuid,
    p_fence bigint,
    p_target_count bigint,
    p_target_digest text,
    p_target_max_ordinal bigint
  ) RETURNS text
  LANGUAGE plpgsql
  AS \$\$
  DECLARE
    v_phase text;
    v_writer text;
    v_f bigint;
    v_source_count bigint;
    v_source_digest text;
    v_state text;
  BEGIN
    SELECT phase,current_writer,fence_ordinal
      INTO v_phase,v_writer,v_f
      FROM relocation_evidence.placement
     WHERE tenant_id=p_tenant
     FOR UPDATE;

    IF v_phase <> 'fenced' OR v_writer <> 'none' OR v_f IS DISTINCT FROM p_fence THEN
      RAISE EXCEPTION 'projection receipt does not match current relocation fence';
    END IF;

    SELECT count(*), md5(coalesce(string_agg(
      accepted_ordinal::text || ':' || observation_id,
      '|' ORDER BY accepted_ordinal, observation_id
    ),''))
      INTO v_source_count,v_source_digest
      FROM relocation_evidence.acceptance
     WHERE tenant_id=p_tenant AND accepted_ordinal <= p_fence;

    v_state := CASE
      WHEN p_target_count = v_source_count
       AND p_target_digest = v_source_digest
       AND p_target_max_ordinal = p_fence
      THEN 'complete'
      ELSE 'incomplete'
    END;

    INSERT INTO relocation_evidence.projection_receipt (
      tenant_id,fence_ordinal,authoritative_count,authoritative_digest,
      target_count,target_digest,target_max_ordinal,state
    ) VALUES (
      p_tenant,p_fence,v_source_count,v_source_digest,
      p_target_count,p_target_digest,p_target_max_ordinal,v_state
    )
    ON CONFLICT (tenant_id,fence_ordinal) DO UPDATE SET
      authoritative_count=EXCLUDED.authoritative_count,
      authoritative_digest=EXCLUDED.authoritative_digest,
      target_count=EXCLUDED.target_count,
      target_digest=EXCLUDED.target_digest,
      target_max_ordinal=EXCLUDED.target_max_ordinal,
      state=EXCLUDED.state,
      verified_at=clock_timestamp();

    RETURN v_state;
  END;
  \$\$;

  CREATE OR REPLACE FUNCTION relocation_evidence.activate_target(p_tenant uuid)
  RETURNS boolean
  LANGUAGE plpgsql
  AS \$\$
  DECLARE
    v_f bigint;
    v_source_count bigint;
    v_source_digest text;
    v_receipt relocation_evidence.projection_receipt%ROWTYPE;
  BEGIN
    SELECT fence_ordinal INTO v_f
      FROM relocation_evidence.placement
     WHERE tenant_id=p_tenant
       AND phase='fenced'
       AND current_writer='none'
     FOR UPDATE;
    IF NOT FOUND OR v_f IS NULL THEN
      RETURN false;
    END IF;

    SELECT * INTO v_receipt
      FROM relocation_evidence.projection_receipt
     WHERE tenant_id=p_tenant
       AND fence_ordinal=v_f
       AND state='complete';
    IF NOT FOUND THEN
      RETURN false;
    END IF;

    -- Re-establish that the durable receipt still covers the complete frozen
    -- authoritative set. No caller-provided max/watermark can substitute.
    SELECT count(*), md5(coalesce(string_agg(
      accepted_ordinal::text || ':' || observation_id,
      '|' ORDER BY accepted_ordinal, observation_id
    ),''))
      INTO v_source_count,v_source_digest
      FROM relocation_evidence.acceptance
     WHERE tenant_id=p_tenant AND accepted_ordinal <= v_f;

    IF v_receipt.authoritative_count <> v_source_count
       OR v_receipt.authoritative_digest <> v_source_digest
       OR v_receipt.target_count <> v_source_count
       OR v_receipt.target_digest <> v_source_digest
       OR v_receipt.target_max_ordinal <> v_f THEN
      RETURN false;
    END IF;

    UPDATE relocation_evidence.placement
       SET phase='active',current_writer='target',placement_version=placement_version+1
     WHERE tenant_id=p_tenant AND phase='fenced' AND current_writer='none';
    RETURN FOUND;
  END;
  \$\$;

  INSERT INTO relocation_evidence.placement
    (tenant_id,phase,current_writer,placement_version)
  VALUES ('$tenant','active','source',1);
" >/dev/null

pre1="$(pg_sql "SELECT relocation_evidence.accept_observation('$tenant','source',1,'obs-pre-1')::text;")"
pre2="$(pg_sql "SELECT relocation_evidence.accept_observation('$tenant','source',1,'obs-pre-2')::text;")"
assert_exact "relocation_source_pre1_accept" "true" "$pre1"
assert_exact "relocation_source_pre2_accept" "true" "$pre2"

# Tier 2 has separate source/target physical projections. Both remain internal;
# no tenant-facing role receives direct privilege.
ts_sql "
  DROP SCHEMA IF EXISTS relocation_evidence CASCADE;
  CREATE SCHEMA relocation_evidence AUTHORIZATION ts_automation_owner;
  GRANT USAGE ON SCHEMA relocation_evidence TO ts_owner;

  SET ROLE ts_automation_owner;
  CREATE TABLE relocation_evidence.source_history (
    tenant_id uuid NOT NULL,
    observation_id text NOT NULL,
    accepted_ordinal bigint NOT NULL,
    observed_at timestamptz NOT NULL,
    UNIQUE (tenant_id,observation_id,observed_at)
  );
  SELECT public.create_hypertable('relocation_evidence.source_history','observed_at',chunk_time_interval=>interval '1 day');

  CREATE TABLE relocation_evidence.target_history (
    tenant_id uuid NOT NULL,
    observation_id text NOT NULL,
    accepted_ordinal bigint NOT NULL,
    observed_at timestamptz NOT NULL,
    UNIQUE (tenant_id,observation_id,observed_at)
  );
  SELECT public.create_hypertable('relocation_evidence.target_history','observed_at',chunk_time_interval=>interval '1 day');
  RESET ROLE;

  REVOKE ALL ON relocation_evidence.source_history FROM PUBLIC,ts_runtime,ts_report_a,ts_report_b;
  REVOKE ALL ON relocation_evidence.target_history FROM PUBLIC,ts_runtime,ts_report_a,ts_report_b;
" >/dev/null

ord1="$(pg_sql "SELECT accepted_ordinal FROM relocation_evidence.acceptance WHERE observation_id='obs-pre-1';")"
ord2="$(pg_sql "SELECT accepted_ordinal FROM relocation_evidence.acceptance WHERE observation_id='obs-pre-2';")"
ts_sql "
  SET ROLE ts_automation_owner;
  INSERT INTO relocation_evidence.source_history VALUES
    ('$tenant','obs-pre-1',$ord1,'2026-08-28T10:00:00Z'),
    ('$tenant','obs-pre-2',$ord2,'2026-08-28T10:01:00Z');
  RESET ROLE;
" >/dev/null

# Concurrency falsifier for fence derivation. The acceptance function sleeps
# only after it holds placement FOR UPDATE. We wait until pg_stat_activity proves
# that exact PgSleep state, then race fence_source. Correct lock ordering forces
# the fence to wait and include the acceptance that already owned authority.
set +e
docker exec -e PGPASSWORD="$password" "$pg_container" \
  psql -X -v ON_ERROR_STOP=1 -U postgres -d jlmirror -Atq -c \
  "SELECT relocation_evidence.accept_observation('$tenant','source',1,'obs-race-pre-fence',2.0)::text;" \
  >"$race_out" 2>&1 &
race_pid=$!
set -e

race_sleeping=0
for _ in $(seq 1 100); do
  sleeping="$(pg_sql "
    SELECT count(*) FROM pg_stat_activity
    WHERE datname='jlmirror'
      AND query LIKE '%obs-race-pre-fence%'
      AND wait_event='PgSleep';
  ")"
  if [[ "$sleeping" -ge 1 ]]; then
    race_sleeping=1
    break
  fi
  sleep 0.02
done
if [[ "$race_sleeping" != "1" ]]; then
  cat "$race_out" >&2 || true
  kill "$race_pid" >/dev/null 2>&1 || true
  wait "$race_pid" >/dev/null 2>&1 || true
  echo "relocation fence race setup never observed acceptance sleeping after placement lock" >&2
  exit 1
fi
printf '%s\n' 'relocation_acceptance_lock_race_setup=PASS'

fence="$(pg_sql "SELECT relocation_evidence.fence_source('$tenant');")"
wait "$race_pid"
race_result="$(tr -d '[:space:]' < "$race_out")"
assert_exact "relocation_racing_acceptance_committed" "t" "$race_result"

ord_race="$(pg_sql "SELECT accepted_ordinal FROM relocation_evidence.acceptance WHERE observation_id='obs-race-pre-fence';")"
assert_exact "relocation_fence_includes_inflight_acceptance" "$ord_race" "$fence"

ts_sql "
  SET ROLE ts_automation_owner;
  INSERT INTO relocation_evidence.source_history VALUES
    ('$tenant','obs-race-pre-fence',$ord_race,'2026-08-28T10:01:30Z');
  RESET ROLE;
" >/dev/null

stale_during_fence="$(pg_sql "SELECT relocation_evidence.accept_observation('$tenant','source',1,'obs-stale-during-fence')::text;")"
assert_exact "relocation_source_blocked_after_fence" "false" "$stale_during_fence"

# No receipt means no target authority regardless of any caller knowledge.
premature_no_receipt="$(pg_sql "SELECT relocation_evidence.activate_target('$tenant')::text;")"
assert_exact "relocation_target_cannot_activate_without_receipt" "false" "$premature_no_receipt"

# Deliberately transfer only the highest ordinal. max(target)=F is therefore
# true while the target is incomplete. This directly falsifies max-only
# watermark admission.
ts_sql "
  SET ROLE ts_automation_owner;
  INSERT INTO relocation_evidence.target_history
    (tenant_id,observation_id,accepted_ordinal,observed_at)
  SELECT tenant_id,observation_id,accepted_ordinal,observed_at
    FROM relocation_evidence.source_history
   WHERE accepted_ordinal = $fence
  ON CONFLICT DO NOTHING;
  RESET ROLE;
" >/dev/null

incomplete_count="$(ts_sql "SELECT count(*) FROM relocation_evidence.target_history WHERE tenant_id='$tenant';")"
incomplete_max="$(ts_sql "SELECT coalesce(max(accepted_ordinal),0) FROM relocation_evidence.target_history WHERE tenant_id='$tenant';")"
incomplete_digest="$(ts_sql "SELECT md5(coalesce(string_agg(accepted_ordinal::text || ':' || observation_id,'|' ORDER BY accepted_ordinal,observation_id),'')) FROM relocation_evidence.target_history WHERE tenant_id='$tenant' AND accepted_ordinal <= $fence;")"
assert_exact "relocation_incomplete_target_still_reaches_F" "$fence" "$incomplete_max"

incomplete_receipt="$(pg_sql "SELECT relocation_evidence.record_projection_receipt('$tenant',$fence,$incomplete_count,'$incomplete_digest',$incomplete_max);")"
assert_exact "relocation_gap_receipt_detected" "incomplete" "$incomplete_receipt"

premature_gap="$(pg_sql "SELECT relocation_evidence.activate_target('$tenant')::text;")"
assert_exact "relocation_target_cannot_activate_with_gap_at_F" "false" "$premature_gap"

# Complete the replay through F, derive a digest/count over the exact target set,
# and only then record a complete durable receipt.
ts_sql "
  SET ROLE ts_automation_owner;
  INSERT INTO relocation_evidence.target_history
    (tenant_id,observation_id,accepted_ordinal,observed_at)
  SELECT tenant_id,observation_id,accepted_ordinal,observed_at
    FROM relocation_evidence.source_history
   WHERE accepted_ordinal <= $fence
  ON CONFLICT DO NOTHING;
  RESET ROLE;
" >/dev/null

target_count_at_f="$(ts_sql "SELECT count(*) FROM relocation_evidence.target_history WHERE tenant_id='$tenant' AND accepted_ordinal <= $fence;")"
target_max_at_f="$(ts_sql "SELECT coalesce(max(accepted_ordinal),0) FROM relocation_evidence.target_history WHERE tenant_id='$tenant' AND accepted_ordinal <= $fence;")"
target_digest_at_f="$(ts_sql "SELECT md5(coalesce(string_agg(accepted_ordinal::text || ':' || observation_id,'|' ORDER BY accepted_ordinal,observation_id),'')) FROM relocation_evidence.target_history WHERE tenant_id='$tenant' AND accepted_ordinal <= $fence;")"
complete_receipt="$(pg_sql "SELECT relocation_evidence.record_projection_receipt('$tenant',$fence,$target_count_at_f,'$target_digest_at_f',$target_max_at_f);")"
assert_exact "relocation_complete_projection_receipt" "complete" "$complete_receipt"

activated="$(pg_sql "SELECT relocation_evidence.activate_target('$tenant')::text;")"
assert_exact "relocation_target_activate_after_complete_receipt" "true" "$activated"

post="$(pg_sql "SELECT relocation_evidence.accept_observation('$tenant','target',2,'obs-post-1')::text;")"
assert_exact "relocation_target_post_cutover_accept" "true" "$post"

stale_source="$(pg_sql "SELECT relocation_evidence.accept_observation('$tenant','source',1,'obs-stale-source')::text;")"
assert_exact "relocation_stale_source_rejected" "false" "$stale_source"

ord_post="$(pg_sql "SELECT accepted_ordinal FROM relocation_evidence.acceptance WHERE observation_id='obs-post-1';")"
ts_sql "
  SET ROLE ts_automation_owner;
  INSERT INTO relocation_evidence.target_history
    (tenant_id,observation_id,accepted_ordinal,observed_at)
  VALUES ('$tenant','obs-post-1',$ord_post,'2026-08-28T10:02:00Z')
  ON CONFLICT DO NOTHING;
  RESET ROLE;
" >/dev/null

acceptance_count="$(pg_sql "SELECT count(*) FROM relocation_evidence.acceptance WHERE tenant_id='$tenant';")"
target_count="$(ts_sql "SELECT count(*) FROM relocation_evidence.target_history WHERE tenant_id='$tenant';")"
target_distinct="$(ts_sql "SELECT count(DISTINCT observation_id) FROM relocation_evidence.target_history WHERE tenant_id='$tenant';")"
source_post_count="$(ts_sql "SELECT count(*) FROM relocation_evidence.source_history WHERE observation_id='obs-post-1';")"
placement="$(pg_sql "SELECT phase||'|'||current_writer||'|'||placement_version||'|'||fence_ordinal FROM relocation_evidence.placement WHERE tenant_id='$tenant';")"
receipt_state="$(pg_sql "SELECT state||'|'||authoritative_count||'|'||target_count||'|'||target_max_ordinal FROM relocation_evidence.projection_receipt WHERE tenant_id='$tenant' AND fence_ordinal=$fence;")"

assert_exact "relocation_authoritative_acceptance_count" "4" "$acceptance_count"
assert_exact "relocation_target_history_complete" "$acceptance_count" "$target_count"
assert_exact "relocation_target_history_no_duplicates" "$target_count" "$target_distinct"
assert_exact "relocation_retired_source_no_post_cutover_projection" "0" "$source_post_count"
assert_exact "relocation_final_authority" "active|target|2|$fence" "$placement"
assert_exact "relocation_durable_complete_receipt" "complete|3|3|$fence" "$receipt_state"

# Tenant-facing roles still cannot bypass the internal Tier 2 relocation tables.
if docker exec -e PGPASSWORD=report-a-evidence-only "$ts_container" \
    psql -X -v ON_ERROR_STOP=1 -h 127.0.0.1 -U ts_report_a -d jlmirror -Atq \
    -c "SELECT count(*) FROM relocation_evidence.target_history;" >/tmp/relocation-attack.out 2>&1; then
  echo "relocation tenant-facing direct target-history read unexpectedly succeeded" >&2
  cat /tmp/relocation-attack.out >&2 || true
  exit 1
fi
printf '%s\n' 'relocation_tier2_direct_tenant_read=PASS rejected'

printf 'tenant_relocation_tier1_tier2_continuity=PASS F=%s receipt=%s\n' "$fence" "$receipt_state"
