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

# Tier 1 owns acceptance and the relocation fence. During fenced transfer there
# is deliberately no authoritative writer; target activation is conditional on
# the Tier 2 target watermark having reached F.
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

  CREATE OR REPLACE FUNCTION relocation_evidence.accept_observation(
    p_tenant uuid,
    p_writer text,
    p_placement_version bigint,
    p_observation_id text
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
  DECLARE v_f bigint;
  BEGIN
    SELECT coalesce(max(accepted_ordinal),0) INTO v_f
      FROM relocation_evidence.acceptance WHERE tenant_id=p_tenant;
    UPDATE relocation_evidence.placement
       SET phase='fenced',current_writer='none',fence_ordinal=v_f
     WHERE tenant_id=p_tenant
       AND phase='active'
       AND current_writer='source';
    IF NOT FOUND THEN
      RAISE EXCEPTION 'source fence lost single-winner authority';
    END IF;
    RETURN v_f;
  END;
  \$\$;

  CREATE OR REPLACE FUNCTION relocation_evidence.activate_target(
    p_tenant uuid,
    p_target_watermark bigint
  ) RETURNS boolean
  LANGUAGE plpgsql
  AS \$\$
  DECLARE v_f bigint;
  BEGIN
    SELECT fence_ordinal INTO v_f
      FROM relocation_evidence.placement
     WHERE tenant_id=p_tenant
     FOR UPDATE;
    IF v_f IS NULL OR p_target_watermark < v_f THEN
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

fence="$(pg_sql "SELECT relocation_evidence.fence_source('$tenant');")"
assert_exact "relocation_fence_F" "$ord2" "$fence"

stale_during_fence="$(pg_sql "SELECT relocation_evidence.accept_observation('$tenant','source',1,'obs-stale-during-fence')::text;")"
assert_exact "relocation_source_blocked_after_fence" "false" "$stale_during_fence"

# Transfer/replay through F is idempotent and bounded by canonical identity.
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

target_watermark="$(ts_sql "SELECT coalesce(max(accepted_ordinal),0) FROM relocation_evidence.target_history WHERE tenant_id='$tenant';")"

premature="$(pg_sql "SELECT relocation_evidence.activate_target('$tenant',$((fence - 1)))::text;")"
assert_exact "relocation_target_cannot_activate_below_F" "false" "$premature"

activated="$(pg_sql "SELECT relocation_evidence.activate_target('$tenant',$target_watermark)::text;")"
assert_exact "relocation_target_activate_at_F" "true" "$activated"

post="$(pg_sql "SELECT relocation_evidence.accept_observation('$tenant','target',2,'obs-post-1')::text;")"
assert_exact "relocation_target_post_cutover_accept" "true" "$post"

stale_source="$(pg_sql "SELECT relocation_evidence.accept_observation('$tenant','source',1,'obs-stale-source')::text;")"
assert_exact "relocation_stale_source_rejected" "false" "$stale_source"

ord3="$(pg_sql "SELECT accepted_ordinal FROM relocation_evidence.acceptance WHERE observation_id='obs-post-1';")"
ts_sql "
  SET ROLE ts_automation_owner;
  INSERT INTO relocation_evidence.target_history
    (tenant_id,observation_id,accepted_ordinal,observed_at)
  VALUES ('$tenant','obs-post-1',$ord3,'2026-08-28T10:02:00Z')
  ON CONFLICT DO NOTHING;
  RESET ROLE;
" >/dev/null

acceptance_count="$(pg_sql "SELECT count(*) FROM relocation_evidence.acceptance WHERE tenant_id='$tenant';")"
target_count="$(ts_sql "SELECT count(*) FROM relocation_evidence.target_history WHERE tenant_id='$tenant';")"
target_distinct="$(ts_sql "SELECT count(DISTINCT observation_id) FROM relocation_evidence.target_history WHERE tenant_id='$tenant';")"
source_post_count="$(ts_sql "SELECT count(*) FROM relocation_evidence.source_history WHERE observation_id='obs-post-1';")"
placement="$(pg_sql "SELECT phase||'|'||current_writer||'|'||placement_version||'|'||fence_ordinal FROM relocation_evidence.placement WHERE tenant_id='$tenant';")"

assert_exact "relocation_authoritative_acceptance_count" "3" "$acceptance_count"
assert_exact "relocation_target_history_complete" "$acceptance_count" "$target_count"
assert_exact "relocation_target_history_no_duplicates" "$target_count" "$target_distinct"
assert_exact "relocation_retired_source_no_post_cutover_projection" "0" "$source_post_count"
assert_exact "relocation_final_authority" "active|target|2|$fence" "$placement"

# Tenant-facing roles still cannot bypass the internal Tier 2 relocation tables.
if docker exec -e PGPASSWORD=report-a-evidence-only "$ts_container" \
    psql -X -v ON_ERROR_STOP=1 -h 127.0.0.1 -U ts_report_a -d jlmirror -Atq \
    -c "SELECT count(*) FROM relocation_evidence.target_history;" >/tmp/relocation-attack.out 2>&1; then
  echo "relocation tenant-facing direct target-history read unexpectedly succeeded" >&2
  cat /tmp/relocation-attack.out >&2 || true
  exit 1
fi
printf '%s\n' 'relocation_tier2_direct_tenant_read=PASS rejected'

printf 'tenant_relocation_tier1_tier2_continuity=PASS F=%s target_watermark=%s\n' "$fence" "$target_watermark"
