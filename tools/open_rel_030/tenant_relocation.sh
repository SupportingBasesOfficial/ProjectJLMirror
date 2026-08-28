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
metric="55555555-5555-5555-5555-555555555555"
race_out="$(mktemp)"
seal_out="$(mktemp)"
seal_mutation_out="$(mktemp)"
attestation_key="$(openssl rand -hex 32)"

cleanup() {
  rm -f "$race_out" "$seal_out" "$seal_mutation_out" >/dev/null 2>&1 || true
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

expect_pg_reject() {
  local label="$1"
  local needle="$2"
  local sql="$3"
  local output rc
  set +e
  output="$(pg_sql "$sql" 2>&1)"
  rc=$?
  set -e
  if [[ $rc -eq 0 || "$output" != *"$needle"* ]]; then
    printf '%s expected rejection containing=%q rc=%s output=%q\n' "$label" "$needle" "$rc" "$output" >&2
    return 1
  fi
  printf '%s=PASS rejected=%q\n' "$label" "$needle"
}

expect_ts_reject() {
  local label="$1"
  local needle="$2"
  local sql="$3"
  local output rc
  set +e
  output="$(ts_sql "$sql" 2>&1)"
  rc=$?
  set -e
  if [[ $rc -eq 0 || "$output" != *"$needle"* ]]; then
    printf '%s expected rejection containing=%q rc=%s output=%q\n' "$label" "$needle" "$rc" "$output" >&2
    return 1
  fi
  printf '%s=PASS rejected=%q\n' "$label" "$needle"
}

# Tier 1 owns authoritative acceptance/fencing and verifies target-issued
# attestations. The target checkpoint fields are never trusted by value alone.
pg_sql "
  CREATE EXTENSION IF NOT EXISTS pgcrypto;
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
    metric_definition_id uuid NOT NULL,
    observed_at timestamptz NOT NULL,
    numeric_value numeric NOT NULL,
    accepted_by text NOT NULL,
    placement_version bigint NOT NULL,
    UNIQUE (tenant_id, observation_id)
  );

  CREATE TABLE relocation_evidence.target_attestation_key (
    singleton boolean PRIMARY KEY DEFAULT true CHECK (singleton),
    key_material text NOT NULL
  );
  INSERT INTO relocation_evidence.target_attestation_key(singleton,key_material)
  VALUES (true,'$attestation_key');
  REVOKE ALL ON relocation_evidence.target_attestation_key FROM PUBLIC;

  CREATE TABLE relocation_evidence.projection_receipt (
    tenant_id uuid NOT NULL,
    fence_ordinal bigint NOT NULL,
    checkpoint_id uuid NOT NULL,
    checkpoint_generation bigint NOT NULL,
    target_sealed boolean NOT NULL,
    authoritative_count bigint NOT NULL,
    authoritative_digest text NOT NULL,
    target_count bigint NOT NULL,
    target_digest text NOT NULL,
    target_max_ordinal bigint NOT NULL,
    target_attestation text NOT NULL,
    state text NOT NULL CHECK (state IN ('complete','incomplete')),
    verified_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (tenant_id, fence_ordinal)
  );

  CREATE OR REPLACE FUNCTION relocation_evidence.accept_observation(
    p_tenant uuid,
    p_writer text,
    p_placement_version bigint,
    p_observation_id text,
    p_metric_definition_id uuid,
    p_observed_at timestamptz,
    p_numeric_value numeric,
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

    INSERT INTO relocation_evidence.acceptance (
      tenant_id,observation_id,metric_definition_id,observed_at,numeric_value,
      accepted_by,placement_version
    ) VALUES (
      p_tenant,p_observation_id,p_metric_definition_id,p_observed_at,p_numeric_value,
      p_writer,p_placement_version
    )
    ON CONFLICT (tenant_id,observation_id) DO NOTHING;
    GET DIAGNOSTICS v_inserted = ROW_COUNT;
    RETURN v_inserted = 1;
  END;
  \$\$;

  CREATE OR REPLACE FUNCTION relocation_evidence.authoritative_digest(
    p_tenant uuid,
    p_fence bigint
  ) RETURNS text
  LANGUAGE sql
  STABLE
  SET search_path = pg_catalog, relocation_evidence
  AS \$\$
    SELECT encode(public.digest(convert_to(coalesce(string_agg(
      accepted_ordinal::text || E'\\x1f' ||
      observation_id || E'\\x1f' ||
      metric_definition_id::text || E'\\x1f' ||
      to_char(observed_at AT TIME ZONE 'UTC','YYYY-MM-DD\"T\"HH24:MI:SS.US\"Z\"') || E'\\x1f' ||
      trim_scale(numeric_value)::text,
      E'\\x1e' ORDER BY accepted_ordinal, observation_id
    ),''),'UTF8'),'sha256'),'hex')
    FROM relocation_evidence.acceptance
    WHERE tenant_id=p_tenant AND accepted_ordinal <= p_fence
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
    p_checkpoint_id uuid,
    p_checkpoint_generation bigint,
    p_target_sealed boolean,
    p_target_count bigint,
    p_target_digest text,
    p_target_max_ordinal bigint,
    p_target_attestation text
  ) RETURNS text
  LANGUAGE plpgsql
  SET search_path = pg_catalog, relocation_evidence
  AS \$\$
  DECLARE
    v_phase text;
    v_writer text;
    v_f bigint;
    v_source_count bigint;
    v_source_digest text;
    v_key text;
    v_expected_attestation text;
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

    SELECT key_material INTO STRICT v_key
      FROM relocation_evidence.target_attestation_key
     WHERE singleton;

    v_expected_attestation := encode(public.hmac(
      convert_to(concat_ws('|','open-rel-030-target-checkpoint-v1',
        p_tenant::text,p_fence::text,p_checkpoint_id::text,
        p_checkpoint_generation::text,p_target_sealed::text,p_target_count::text,
        p_target_digest,p_target_max_ordinal::text),'UTF8'),
      decode(v_key,'hex'),'sha256'),'hex');

    IF v_expected_attestation IS DISTINCT FROM p_target_attestation THEN
      RAISE EXCEPTION 'invalid target checkpoint attestation';
    END IF;

    SELECT count(*), relocation_evidence.authoritative_digest(p_tenant,p_fence)
      INTO v_source_count,v_source_digest
      FROM relocation_evidence.acceptance
     WHERE tenant_id=p_tenant AND accepted_ordinal <= p_fence;

    v_state := CASE
      WHEN p_target_sealed
       AND p_target_count = v_source_count
       AND p_target_digest = v_source_digest
       AND p_target_max_ordinal = p_fence
      THEN 'complete'
      ELSE 'incomplete'
    END;

    INSERT INTO relocation_evidence.projection_receipt (
      tenant_id,fence_ordinal,checkpoint_id,checkpoint_generation,target_sealed,
      authoritative_count,authoritative_digest,target_count,target_digest,
      target_max_ordinal,target_attestation,state
    ) VALUES (
      p_tenant,p_fence,p_checkpoint_id,p_checkpoint_generation,p_target_sealed,
      v_source_count,v_source_digest,p_target_count,p_target_digest,
      p_target_max_ordinal,p_target_attestation,v_state
    )
    ON CONFLICT (tenant_id,fence_ordinal) DO UPDATE SET
      checkpoint_id=EXCLUDED.checkpoint_id,
      checkpoint_generation=EXCLUDED.checkpoint_generation,
      target_sealed=EXCLUDED.target_sealed,
      authoritative_count=EXCLUDED.authoritative_count,
      authoritative_digest=EXCLUDED.authoritative_digest,
      target_count=EXCLUDED.target_count,
      target_digest=EXCLUDED.target_digest,
      target_max_ordinal=EXCLUDED.target_max_ordinal,
      target_attestation=EXCLUDED.target_attestation,
      state=EXCLUDED.state,
      verified_at=clock_timestamp();

    RETURN v_state;
  END;
  \$\$;

  CREATE OR REPLACE FUNCTION relocation_evidence.activate_target(p_tenant uuid)
  RETURNS boolean
  LANGUAGE plpgsql
  SET search_path = pg_catalog, relocation_evidence
  AS \$\$
  DECLARE
    v_f bigint;
    v_source_count bigint;
    v_source_digest text;
    v_key text;
    v_expected_attestation text;
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
       AND state='complete'
       AND target_sealed;
    IF NOT FOUND THEN
      RETURN false;
    END IF;

    SELECT key_material INTO STRICT v_key
      FROM relocation_evidence.target_attestation_key
     WHERE singleton;

    v_expected_attestation := encode(public.hmac(
      convert_to(concat_ws('|','open-rel-030-target-checkpoint-v1',
        v_receipt.tenant_id::text,v_receipt.fence_ordinal::text,
        v_receipt.checkpoint_id::text,v_receipt.checkpoint_generation::text,
        v_receipt.target_sealed::text,v_receipt.target_count::text,
        v_receipt.target_digest,v_receipt.target_max_ordinal::text),'UTF8'),
      decode(v_key,'hex'),'sha256'),'hex');

    IF v_expected_attestation IS DISTINCT FROM v_receipt.target_attestation THEN
      RETURN false;
    END IF;

    SELECT count(*), relocation_evidence.authoritative_digest(p_tenant,v_f)
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

pre1="$(pg_sql "SELECT relocation_evidence.accept_observation('$tenant','source',1,'obs-pre-1','$metric','2026-08-28T10:00:00Z',10.5)::text;")"
pre2="$(pg_sql "SELECT relocation_evidence.accept_observation('$tenant','source',1,'obs-pre-2','$metric','2026-08-28T10:01:00Z',11.5)::text;")"
assert_exact "relocation_source_pre1_accept" "true" "$pre1"
assert_exact "relocation_source_pre2_accept" "true" "$pre2"

# Tier 2 owns the checkpoint and freeze state. ts_automation_owner can project
# rows but cannot alter checkpoint authority or disable the freeze trigger.
ts_sql "
  CREATE EXTENSION IF NOT EXISTS pgcrypto;
  DROP SCHEMA IF EXISTS relocation_evidence CASCADE;
  CREATE SCHEMA relocation_evidence AUTHORIZATION ts_owner;
  GRANT USAGE ON SCHEMA relocation_evidence TO ts_automation_owner;

  CREATE TABLE relocation_evidence.source_history (
    tenant_id uuid NOT NULL,
    observation_id text NOT NULL,
    metric_definition_id uuid NOT NULL,
    accepted_ordinal bigint NOT NULL,
    observed_at timestamptz NOT NULL,
    numeric_value numeric NOT NULL,
    UNIQUE (tenant_id,observation_id,observed_at)
  );
  ALTER TABLE relocation_evidence.source_history OWNER TO ts_owner;
  SELECT public.create_hypertable('relocation_evidence.source_history','observed_at',chunk_time_interval=>interval '1 day');

  CREATE TABLE relocation_evidence.target_history (
    tenant_id uuid NOT NULL,
    observation_id text NOT NULL,
    metric_definition_id uuid NOT NULL,
    accepted_ordinal bigint NOT NULL,
    observed_at timestamptz NOT NULL,
    numeric_value numeric NOT NULL,
    UNIQUE (tenant_id,observation_id,observed_at)
  );
  ALTER TABLE relocation_evidence.target_history OWNER TO ts_owner;
  SELECT public.create_hypertable('relocation_evidence.target_history','observed_at',chunk_time_interval=>interval '1 day');

  CREATE TABLE relocation_evidence.target_control (
    tenant_id uuid PRIMARY KEY,
    phase text NOT NULL CHECK (phase IN ('open','sealed','activated')),
    fence_ordinal bigint,
    checkpoint_id uuid,
    checkpoint_generation bigint NOT NULL DEFAULT 0
  );
  ALTER TABLE relocation_evidence.target_control OWNER TO ts_owner;

  CREATE TABLE relocation_evidence.target_checkpoint (
    checkpoint_id uuid PRIMARY KEY,
    tenant_id uuid NOT NULL,
    fence_ordinal bigint NOT NULL,
    checkpoint_generation bigint NOT NULL,
    target_count bigint NOT NULL,
    target_digest text NOT NULL,
    target_max_ordinal bigint NOT NULL,
    attestation text NOT NULL,
    sealed_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    UNIQUE (tenant_id,checkpoint_generation)
  );
  ALTER TABLE relocation_evidence.target_checkpoint OWNER TO ts_owner;

  CREATE TABLE relocation_evidence.target_attestation_key (
    singleton boolean PRIMARY KEY DEFAULT true CHECK (singleton),
    key_material text NOT NULL
  );
  ALTER TABLE relocation_evidence.target_attestation_key OWNER TO ts_owner;
  INSERT INTO relocation_evidence.target_attestation_key(singleton,key_material)
  VALUES (true,'$attestation_key');

  INSERT INTO relocation_evidence.target_control(tenant_id,phase)
  VALUES ('$tenant','open');

  GRANT SELECT,INSERT,UPDATE,DELETE ON relocation_evidence.source_history TO ts_automation_owner;
  GRANT SELECT,INSERT,UPDATE,DELETE ON relocation_evidence.target_history TO ts_automation_owner;
  REVOKE ALL ON relocation_evidence.target_control FROM PUBLIC,ts_runtime,ts_report_a,ts_report_b,ts_automation_owner;
  REVOKE ALL ON relocation_evidence.target_checkpoint FROM PUBLIC,ts_runtime,ts_report_a,ts_report_b,ts_automation_owner;
  REVOKE ALL ON relocation_evidence.target_attestation_key FROM PUBLIC,ts_runtime,ts_report_a,ts_report_b,ts_automation_owner;
  REVOKE ALL ON relocation_evidence.source_history FROM PUBLIC,ts_runtime,ts_report_a,ts_report_b;
  REVOKE ALL ON relocation_evidence.target_history FROM PUBLIC,ts_runtime,ts_report_a,ts_report_b;

  CREATE OR REPLACE FUNCTION relocation_evidence.target_digest(p_tenant uuid,p_fence bigint)
  RETURNS text
  LANGUAGE sql
  STABLE
  SECURITY DEFINER
  SET search_path = pg_catalog, relocation_evidence
  AS \$\$
    SELECT encode(public.digest(convert_to(coalesce(string_agg(
      accepted_ordinal::text || E'\\x1f' ||
      observation_id || E'\\x1f' ||
      metric_definition_id::text || E'\\x1f' ||
      to_char(observed_at AT TIME ZONE 'UTC','YYYY-MM-DD\"T\"HH24:MI:SS.US\"Z\"') || E'\\x1f' ||
      trim_scale(numeric_value)::text,
      E'\\x1e' ORDER BY accepted_ordinal, observation_id
    ),''),'UTF8'),'sha256'),'hex')
    FROM relocation_evidence.target_history
    WHERE tenant_id=p_tenant AND accepted_ordinal <= p_fence
  \$\$;
  ALTER FUNCTION relocation_evidence.target_digest(uuid,bigint) OWNER TO ts_owner;
  REVOKE ALL ON FUNCTION relocation_evidence.target_digest(uuid,bigint) FROM PUBLIC;

  CREATE OR REPLACE FUNCTION relocation_evidence.freeze_target_history()
  RETURNS trigger
  LANGUAGE plpgsql
  SECURITY DEFINER
  SET search_path = pg_catalog, relocation_evidence
  AS \$\$
  DECLARE
    v_old_phase text;
    v_old_f bigint;
    v_new_phase text;
    v_new_f bigint;
  BEGIN
    IF TG_OP = 'UPDATE' THEN
      PERFORM tenant_id
        FROM relocation_evidence.target_control
       WHERE tenant_id IN (OLD.tenant_id, NEW.tenant_id)
       ORDER BY tenant_id
       FOR SHARE;

      SELECT phase,fence_ordinal INTO v_old_phase,v_old_f
        FROM relocation_evidence.target_control
       WHERE tenant_id=OLD.tenant_id;
      SELECT phase,fence_ordinal INTO v_new_phase,v_new_f
        FROM relocation_evidence.target_control
       WHERE tenant_id=NEW.tenant_id;

      IF v_old_phase IN ('sealed','activated') AND v_old_f IS NOT NULL
         AND OLD.accepted_ordinal <= v_old_f THEN
        RAISE EXCEPTION 'sealed target checkpoint forbids mutation through fence';
      END IF;
      IF v_new_phase IN ('sealed','activated') AND v_new_f IS NOT NULL
         AND NEW.accepted_ordinal <= v_new_f THEN
        RAISE EXCEPTION 'sealed target checkpoint forbids mutation through fence';
      END IF;
      RETURN NEW;
    END IF;

    IF TG_OP = 'DELETE' THEN
      SELECT phase,fence_ordinal INTO v_old_phase,v_old_f
        FROM relocation_evidence.target_control
       WHERE tenant_id=OLD.tenant_id
       FOR SHARE;
      IF v_old_phase IN ('sealed','activated') AND v_old_f IS NOT NULL
         AND OLD.accepted_ordinal <= v_old_f THEN
        RAISE EXCEPTION 'sealed target checkpoint forbids mutation through fence';
      END IF;
      RETURN OLD;
    END IF;

    SELECT phase,fence_ordinal INTO v_new_phase,v_new_f
      FROM relocation_evidence.target_control
     WHERE tenant_id=NEW.tenant_id
     FOR SHARE;
    IF v_new_phase IN ('sealed','activated') AND v_new_f IS NOT NULL
       AND NEW.accepted_ordinal <= v_new_f THEN
      RAISE EXCEPTION 'sealed target checkpoint forbids mutation through fence';
    END IF;
    RETURN NEW;
  END;
  \$\$;
  ALTER FUNCTION relocation_evidence.freeze_target_history() OWNER TO ts_owner;

  CREATE TRIGGER target_history_freeze
  BEFORE INSERT OR UPDATE OR DELETE ON relocation_evidence.target_history
  FOR EACH ROW EXECUTE FUNCTION relocation_evidence.freeze_target_history();

  CREATE OR REPLACE FUNCTION relocation_evidence.attest_target_checkpoint(
    p_tenant uuid,
    p_fence bigint,
    p_seal boolean,
    p_hold_after_lock_seconds double precision DEFAULT 0
  ) RETURNS TABLE (
    checkpoint_id uuid,
    checkpoint_generation bigint,
    target_sealed boolean,
    target_count bigint,
    target_digest text,
    target_max_ordinal bigint,
    attestation text
  )
  LANGUAGE plpgsql
  SECURITY DEFINER
  SET search_path = pg_catalog, relocation_evidence
  AS \$\$
  DECLARE
    v_phase text;
    v_generation bigint;
    v_key text;
    v_checkpoint_id uuid;
    v_count bigint;
    v_digest text;
    v_max bigint;
    v_attestation text;
  BEGIN
    SELECT tc.phase,tc.checkpoint_generation
      INTO v_phase,v_generation
      FROM relocation_evidence.target_control AS tc
     WHERE tc.tenant_id=p_tenant
     FOR UPDATE;

    IF NOT FOUND THEN
      RAISE EXCEPTION 'target checkpoint has no control authority';
    END IF;
    IF p_seal AND v_phase <> 'open' THEN
      RAISE EXCEPTION 'target checkpoint already sealed or activated';
    END IF;

    IF p_hold_after_lock_seconds > 0 THEN
      PERFORM pg_sleep(p_hold_after_lock_seconds);
    END IF;

    SELECT count(*), relocation_evidence.target_digest(p_tenant,p_fence),
           coalesce(max(accepted_ordinal),0)
      INTO v_count,v_digest,v_max
      FROM relocation_evidence.target_history
     WHERE tenant_id=p_tenant AND accepted_ordinal <= p_fence;

    v_checkpoint_id := gen_random_uuid();
    v_generation := v_generation + 1;
    SELECT key_material INTO STRICT v_key
      FROM relocation_evidence.target_attestation_key
     WHERE singleton;

    v_attestation := encode(public.hmac(
      convert_to(concat_ws('|','open-rel-030-target-checkpoint-v1',
        p_tenant::text,p_fence::text,v_checkpoint_id::text,
        v_generation::text,p_seal::text,v_count::text,v_digest,v_max::text),'UTF8'),
      decode(v_key,'hex'),'sha256'),'hex');

    IF p_seal THEN
      UPDATE relocation_evidence.target_control
         SET phase='sealed',fence_ordinal=p_fence,
             checkpoint_id=v_checkpoint_id,checkpoint_generation=v_generation
       WHERE tenant_id=p_tenant;

      INSERT INTO relocation_evidence.target_checkpoint (
        checkpoint_id,tenant_id,fence_ordinal,checkpoint_generation,
        target_count,target_digest,target_max_ordinal,attestation
      ) VALUES (
        v_checkpoint_id,p_tenant,p_fence,v_generation,
        v_count,v_digest,v_max,v_attestation
      );
    END IF;

    checkpoint_id := v_checkpoint_id;
    checkpoint_generation := v_generation;
    target_sealed := p_seal;
    target_count := v_count;
    target_digest := v_digest;
    target_max_ordinal := v_max;
    attestation := v_attestation;
    RETURN NEXT;
  END;
  \$\$;
  ALTER FUNCTION relocation_evidence.attest_target_checkpoint(uuid,bigint,boolean,double precision) OWNER TO ts_owner;
  REVOKE ALL ON FUNCTION relocation_evidence.attest_target_checkpoint(uuid,bigint,boolean,double precision) FROM PUBLIC;
  GRANT EXECUTE ON FUNCTION relocation_evidence.attest_target_checkpoint(uuid,bigint,boolean,double precision) TO ts_automation_owner;

  CREATE OR REPLACE FUNCTION relocation_evidence.mark_target_checkpoint_activated(
    p_tenant uuid,p_checkpoint_id uuid
  ) RETURNS boolean
  LANGUAGE plpgsql
  SECURITY DEFINER
  SET search_path = pg_catalog, relocation_evidence
  AS \$\$
  BEGIN
    UPDATE relocation_evidence.target_control
       SET phase='activated'
     WHERE tenant_id=p_tenant AND phase='sealed' AND checkpoint_id=p_checkpoint_id;
    RETURN FOUND;
  END;
  \$\$;
  ALTER FUNCTION relocation_evidence.mark_target_checkpoint_activated(uuid,uuid) OWNER TO ts_owner;
  REVOKE ALL ON FUNCTION relocation_evidence.mark_target_checkpoint_activated(uuid,uuid) FROM PUBLIC;
  GRANT EXECUTE ON FUNCTION relocation_evidence.mark_target_checkpoint_activated(uuid,uuid) TO ts_automation_owner;
" >/dev/null

expect_ts_reject \
  "relocation_projection_writer_cannot_read_attestation_key" \
  "permission denied" \
  "SET ROLE ts_automation_owner; SELECT key_material FROM relocation_evidence.target_attestation_key;"

expect_ts_reject \
  "relocation_projection_writer_cannot_disable_freeze" \
  "must be owner" \
  "SET ROLE ts_automation_owner; ALTER TABLE relocation_evidence.target_history DISABLE TRIGGER target_history_freeze;"

ord1="$(pg_sql "SELECT accepted_ordinal FROM relocation_evidence.acceptance WHERE observation_id='obs-pre-1';")"
ord2="$(pg_sql "SELECT accepted_ordinal FROM relocation_evidence.acceptance WHERE observation_id='obs-pre-2';")"
ts_sql "
  SET ROLE ts_automation_owner;
  INSERT INTO relocation_evidence.source_history
    (tenant_id,observation_id,metric_definition_id,accepted_ordinal,observed_at,numeric_value)
  VALUES
    ('$tenant','obs-pre-1','$metric',$ord1,'2026-08-28T10:00:00Z',10.5),
    ('$tenant','obs-pre-2','$metric',$ord2,'2026-08-28T10:01:00Z',11.5);
  RESET ROLE;
" >/dev/null

set +e
docker exec -e PGPASSWORD="$password" "$pg_container" \
  psql -X -v ON_ERROR_STOP=1 -U postgres -d jlmirror -Atq -c \
  "SELECT relocation_evidence.accept_observation('$tenant','source',1,'obs-race-pre-fence','$metric','2026-08-28T10:01:30Z',12.5,2.0)::text;" \
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
assert_exact "relocation_racing_acceptance_committed" "true" "$race_result"

ord_race="$(pg_sql "SELECT accepted_ordinal FROM relocation_evidence.acceptance WHERE observation_id='obs-race-pre-fence';")"
assert_exact "relocation_fence_includes_inflight_acceptance" "$ord_race" "$fence"

ts_sql "
  SET ROLE ts_automation_owner;
  INSERT INTO relocation_evidence.source_history
    (tenant_id,observation_id,metric_definition_id,accepted_ordinal,observed_at,numeric_value)
  VALUES ('$tenant','obs-race-pre-fence','$metric',$ord_race,'2026-08-28T10:01:30Z',12.5);
  RESET ROLE;
" >/dev/null

stale_during_fence="$(pg_sql "SELECT relocation_evidence.accept_observation('$tenant','source',1,'obs-stale-during-fence','$metric','2026-08-28T10:01:45Z',99)::text;")"
assert_exact "relocation_source_blocked_after_fence" "false" "$stale_during_fence"

premature_no_receipt="$(pg_sql "SELECT relocation_evidence.activate_target('$tenant')::text;")"
assert_exact "relocation_target_cannot_activate_without_receipt" "false" "$premature_no_receipt"

ts_sql "
  SET ROLE ts_automation_owner;
  INSERT INTO relocation_evidence.target_history
    (tenant_id,observation_id,metric_definition_id,accepted_ordinal,observed_at,numeric_value)
  SELECT tenant_id,observation_id,metric_definition_id,accepted_ordinal,observed_at,numeric_value
    FROM relocation_evidence.source_history
   WHERE accepted_ordinal = $fence;
  RESET ROLE;
" >/dev/null

gap_attestation="$(ts_sql "
  SET ROLE ts_automation_owner;
  SELECT checkpoint_id||'|'||checkpoint_generation||'|'||target_sealed||'|'||target_count||'|'||target_digest||'|'||target_max_ordinal||'|'||attestation
    FROM relocation_evidence.attest_target_checkpoint('$tenant',$fence,false,0);
  RESET ROLE;
")"
IFS='|' read -r gap_cp gap_gen gap_sealed gap_count gap_digest gap_max gap_hmac <<< "$gap_attestation"
assert_exact "relocation_incomplete_target_still_reaches_F" "$fence" "$gap_max"

gap_receipt="$(pg_sql "SELECT relocation_evidence.record_projection_receipt('$tenant',$fence,'$gap_cp',$gap_gen,$gap_sealed,$gap_count,'$gap_digest',$gap_max,'$gap_hmac');")"
assert_exact "relocation_gap_receipt_detected" "incomplete" "$gap_receipt"

premature_gap="$(pg_sql "SELECT relocation_evidence.activate_target('$tenant')::text;")"
assert_exact "relocation_target_cannot_activate_with_gap_at_F" "false" "$premature_gap"

ts_sql "
  SET ROLE ts_automation_owner;
  INSERT INTO relocation_evidence.target_history
    (tenant_id,observation_id,metric_definition_id,accepted_ordinal,observed_at,numeric_value)
  SELECT tenant_id,observation_id,metric_definition_id,accepted_ordinal,observed_at,numeric_value
    FROM relocation_evidence.source_history
   WHERE accepted_ordinal <= $fence
  ON CONFLICT DO NOTHING;
  RESET ROLE;
" >/dev/null

ts_sql "
  SET ROLE ts_automation_owner;
  UPDATE relocation_evidence.target_history
     SET observed_at = observed_at + interval '1 second'
   WHERE tenant_id='$tenant' AND observation_id='obs-pre-1';
  RESET ROLE;
" >/dev/null

payload_attestation="$(ts_sql "
  SET ROLE ts_automation_owner;
  SELECT checkpoint_id||'|'||checkpoint_generation||'|'||target_sealed||'|'||target_count||'|'||target_digest||'|'||target_max_ordinal||'|'||attestation
    FROM relocation_evidence.attest_target_checkpoint('$tenant',$fence,false,0);
  RESET ROLE;
")"
IFS='|' read -r payload_cp payload_gen payload_sealed payload_count payload_digest payload_max payload_hmac <<< "$payload_attestation"

payload_receipt="$(pg_sql "SELECT relocation_evidence.record_projection_receipt('$tenant',$fence,'$payload_cp',$payload_gen,$payload_sealed,$payload_count,'$payload_digest',$payload_max,'$payload_hmac');")"
assert_exact "relocation_canonical_payload_mismatch_detected" "incomplete" "$payload_receipt"

ts_sql "
  SET ROLE ts_automation_owner;
  UPDATE relocation_evidence.target_history
     SET observed_at = '2026-08-28T10:00:00Z'
   WHERE tenant_id='$tenant' AND observation_id='obs-pre-1';
  RESET ROLE;
" >/dev/null

set +e
docker exec -e PGPASSWORD="$password" "$ts_container" \
  psql -X -v ON_ERROR_STOP=1 -U postgres -d jlmirror -Atq -c \
  "SET ROLE ts_automation_owner; SELECT checkpoint_id||'|'||checkpoint_generation||'|'||target_sealed||'|'||target_count||'|'||target_digest||'|'||target_max_ordinal||'|'||attestation FROM relocation_evidence.attest_target_checkpoint('$tenant',$fence,true,2.0); RESET ROLE;" \
  >"$seal_out" 2>&1 &
seal_pid=$!
set -e

seal_sleeping=0
for _ in $(seq 1 100); do
  sleeping="$(ts_sql "
    SELECT count(*) FROM pg_stat_activity
    WHERE datname='jlmirror'
      AND query LIKE '%attest_target_checkpoint%true,2.0%'
      AND wait_event='PgSleep';
  ")"
  if [[ "$sleeping" -ge 1 ]]; then
    seal_sleeping=1
    break
  fi
  sleep 0.02
done
if [[ "$seal_sleeping" != "1" ]]; then
  cat "$seal_out" >&2 || true
  kill "$seal_pid" >/dev/null 2>&1 || true
  wait "$seal_pid" >/dev/null 2>&1 || true
  echo "relocation target seal race never observed checkpoint authority sleeping after FOR UPDATE" >&2
  exit 1
fi
printf '%s\n' 'relocation_target_seal_lock_race_setup=PASS'

set +e
docker exec -e PGPASSWORD="$password" "$ts_container" \
  psql -X -v ON_ERROR_STOP=1 -U postgres -d jlmirror -Atq -c \
  "SET ROLE ts_automation_owner; UPDATE relocation_evidence.target_history SET numeric_value=numeric_value+1 WHERE tenant_id='$tenant' AND observation_id='obs-pre-1'; RESET ROLE;" \
  >"$seal_mutation_out" 2>&1 &
seal_mutation_pid=$!
set -e

sleep 0.10
if ! kill -0 "$seal_mutation_pid" >/dev/null 2>&1; then
  cat "$seal_mutation_out" >&2 || true
  wait "$seal_mutation_pid" >/dev/null 2>&1 || true
  echo "relocation concurrent target mutation did not block behind checkpoint seal" >&2
  exit 1
fi
printf '%s\n' 'relocation_target_seal_blocks_concurrent_mutation=PASS'

wait "$seal_pid"
sealed_attestation="$(tr -d '\r\n' < "$seal_out")"
IFS='|' read -r sealed_cp sealed_gen sealed_flag sealed_count sealed_digest sealed_max sealed_hmac <<< "$sealed_attestation"
assert_exact "relocation_target_checkpoint_is_sealed" "true" "$sealed_flag"

set +e
wait "$seal_mutation_pid"
seal_mutation_rc=$?
set -e
seal_mutation_result="$(cat "$seal_mutation_out")"
if [[ $seal_mutation_rc -eq 0 || "$seal_mutation_result" != *"sealed target checkpoint forbids mutation through fence"* ]]; then
  printf 'relocation_target_seal_rejects_concurrent_mutation expected sealed rejection rc=%s output=%q\n' "$seal_mutation_rc" "$seal_mutation_result" >&2
  exit 1
fi
printf '%s\n' 'relocation_target_seal_rejects_concurrent_mutation=PASS'

expect_pg_reject \
  "relocation_fabricated_target_attestation_rejected" \
  "invalid target checkpoint attestation" \
  "SELECT relocation_evidence.record_projection_receipt('$tenant',$fence,'$sealed_cp',$sealed_gen,$sealed_flag,$sealed_count,'00$sealed_digest',$sealed_max,'$sealed_hmac');"

complete_receipt="$(pg_sql "SELECT relocation_evidence.record_projection_receipt('$tenant',$fence,'$sealed_cp',$sealed_gen,$sealed_flag,$sealed_count,'$sealed_digest',$sealed_max,'$sealed_hmac');")"
assert_exact "relocation_authenticated_complete_projection_receipt" "complete" "$complete_receipt"

expect_ts_reject \
  "relocation_sealed_target_delete_rejected" \
  "sealed target checkpoint forbids mutation through fence" \
  "SET ROLE ts_automation_owner; DELETE FROM relocation_evidence.target_history WHERE tenant_id='$tenant' AND observation_id='obs-pre-2';"

expect_ts_reject \
  "relocation_sealed_target_tenant_move_rejected" \
  "sealed target checkpoint forbids mutation through fence" \
  "SET ROLE ts_automation_owner; UPDATE relocation_evidence.target_history SET tenant_id='bbbbbbbb-0000-0000-0000-000000000099' WHERE tenant_id='$tenant' AND observation_id='obs-pre-1';"

activated="$(pg_sql "SELECT relocation_evidence.activate_target('$tenant')::text;")"
assert_exact "relocation_target_activate_after_authenticated_checkpoint" "true" "$activated"

target_marked="$(ts_sql "SET ROLE ts_automation_owner; SELECT relocation_evidence.mark_target_checkpoint_activated('$tenant','$sealed_cp')::text; RESET ROLE;")"
assert_exact "relocation_target_checkpoint_marked_activated" "true" "$target_marked"

post="$(pg_sql "SELECT relocation_evidence.accept_observation('$tenant','target',2,'obs-post-1','$metric','2026-08-28T10:02:00Z',13.5)::text;")"
assert_exact "relocation_target_post_cutover_accept" "true" "$post"

stale_source="$(pg_sql "SELECT relocation_evidence.accept_observation('$tenant','source',1,'obs-stale-source','$metric','2026-08-28T10:03:00Z',88)::text;")"
assert_exact "relocation_stale_source_rejected" "false" "$stale_source"

ord_post="$(pg_sql "SELECT accepted_ordinal FROM relocation_evidence.acceptance WHERE observation_id='obs-post-1';")"
ts_sql "
  SET ROLE ts_automation_owner;
  INSERT INTO relocation_evidence.target_history
    (tenant_id,observation_id,metric_definition_id,accepted_ordinal,observed_at,numeric_value)
  VALUES ('$tenant','obs-post-1','$metric',$ord_post,'2026-08-28T10:02:00Z',13.5);
  RESET ROLE;
" >/dev/null

acceptance_count="$(pg_sql "SELECT count(*) FROM relocation_evidence.acceptance WHERE tenant_id='$tenant';")"
target_count="$(ts_sql "SELECT count(*) FROM relocation_evidence.target_history WHERE tenant_id='$tenant';")"
target_distinct="$(ts_sql "SELECT count(DISTINCT observation_id) FROM relocation_evidence.target_history WHERE tenant_id='$tenant';")"
source_post_count="$(ts_sql "SELECT count(*) FROM relocation_evidence.source_history WHERE observation_id='obs-post-1';")"
placement="$(pg_sql "SELECT phase||'|'||current_writer||'|'||placement_version||'|'||fence_ordinal FROM relocation_evidence.placement WHERE tenant_id='$tenant';")"
receipt_state="$(pg_sql "SELECT state||'|'||authoritative_count||'|'||target_count||'|'||target_max_ordinal||'|'||target_sealed FROM relocation_evidence.projection_receipt WHERE tenant_id='$tenant' AND fence_ordinal=$fence;")"
target_checkpoint_state="$(ts_sql "SELECT phase||'|'||checkpoint_id||'|'||checkpoint_generation FROM relocation_evidence.target_control WHERE tenant_id='$tenant';")"
source_digest="$(pg_sql "SELECT relocation_evidence.authoritative_digest('$tenant',$fence);")"
sealed_target_digest="$(ts_sql "SELECT target_digest FROM relocation_evidence.target_checkpoint WHERE checkpoint_id='$sealed_cp';")"

assert_exact "relocation_authoritative_acceptance_count" "4" "$acceptance_count"
assert_exact "relocation_target_history_complete" "$acceptance_count" "$target_count"
assert_exact "relocation_target_history_no_duplicates" "$target_count" "$target_distinct"
assert_exact "relocation_retired_source_no_post_cutover_projection" "0" "$source_post_count"
assert_exact "relocation_final_authority" "active|target|2|$fence" "$placement"
assert_exact "relocation_durable_complete_receipt" "complete|3|3|$fence|true" "$receipt_state"
assert_exact "relocation_sha256_canonical_payload_digest" "$source_digest" "$sealed_target_digest"
assert_exact "relocation_target_checkpoint_current" "activated|$sealed_cp|$sealed_gen" "$target_checkpoint_state"

if docker exec -e PGPASSWORD=report-a-evidence-only "$ts_container" \
    psql -X -v ON_ERROR_STOP=1 -h 127.0.0.1 -U ts_report_a -d jlmirror -Atq \
    -c "SELECT count(*) FROM relocation_evidence.target_history;" >/tmp/relocation-attack.out 2>&1; then
  echo "relocation tenant-facing direct target-history read unexpectedly succeeded" >&2
  cat /tmp/relocation-attack.out >&2 || true
  exit 1
fi
printf '%s\n' 'relocation_tier2_direct_tenant_read=PASS rejected'

printf 'tenant_relocation_tier1_tier2_continuity=PASS F=%s receipt=%s checkpoint=%s\n' "$fence" "$receipt_state" "$sealed_cp"
