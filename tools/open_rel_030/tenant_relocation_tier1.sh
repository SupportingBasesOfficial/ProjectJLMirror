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
other_tenant="aaaaaaaa-0000-0000-0000-000000000002"
metric="55555555-5555-5555-5555-555555555555"
race_out="$(mktemp)"
seal_out="$(mktemp)"
seal_mutation_out="$(mktemp)"
attestation_key="$(openssl rand -hex 32)"
target_verify_password="$(openssl rand -hex 24)"
tier1_verify_password="$(openssl rand -hex 24)"
pg_ip="$(docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' "$pg_container")"
ts_ip="$(docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' "$ts_container")"

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
  local label="$1" expected="$2" actual="$3"
  if [[ "$actual" != "$expected" ]]; then
    printf '%s expected=%q actual=%q\n' "$label" "$expected" "$actual" >&2
    return 1
  fi
  printf '%s=PASS value=%q\n' "$label" "$actual"
}

expect_pg_reject() {
  local label="$1" needle="$2" sql="$3" output rc
  set +e
  output="$(pg_sql "$sql" 2>&1)"; rc=$?
  set -e
  if [[ $rc -eq 0 || "$output" != *"$needle"* ]]; then
    printf '%s expected rejection containing=%q rc=%s output=%q\n' "$label" "$needle" "$rc" "$output" >&2
    return 1
  fi
  printf '%s=PASS rejected=%q\n' "$label" "$needle"
}

expect_ts_reject() {
  local label="$1" needle="$2" sql="$3" output rc
  set +e
  output="$(ts_sql "$sql" 2>&1)"; rc=$?
  set -e
  if [[ $rc -eq 0 || "$output" != *"$needle"* ]]; then
    printf '%s expected rejection containing=%q rc=%s output=%q\n' "$label" "$needle" "$rc" "$output" >&2
    return 1
  fi
  printf '%s=PASS rejected=%q\n' "$label" "$needle"
}

# ---------------------------------------------------------------------------
# Tier 1 source authority. It intentionally has no target signing key.
# Cross-authority verification uses a target verifier credential that can only
# execute the target-side verification function; the local authority cannot mint.
# Remote calls happen before local authority locks and are bounded/fail-closed.
# ---------------------------------------------------------------------------
pg_sql "
  CREATE EXTENSION IF NOT EXISTS pgcrypto;
  CREATE EXTENSION IF NOT EXISTS dblink;
  DROP SCHEMA IF EXISTS relocation_evidence CASCADE;
  DO \$\$
  BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='relocation_tier1_verifier') THEN
      EXECUTE 'DROP OWNED BY relocation_tier1_verifier';
      EXECUTE 'DROP ROLE relocation_tier1_verifier';
    END IF;
  END
  \$\$;
  CREATE ROLE relocation_tier1_verifier LOGIN PASSWORD '$tier1_verify_password';
  ALTER ROLE relocation_tier1_verifier SET statement_timeout='2s';
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

  CREATE TABLE relocation_evidence.activation_grant (
    tenant_id uuid NOT NULL,
    fence_ordinal bigint NOT NULL,
    checkpoint_id uuid NOT NULL,
    checkpoint_generation bigint NOT NULL,
    target_attestation text NOT NULL,
    placement_version bigint NOT NULL,
    state text NOT NULL CHECK (state='committed'),
    granted_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (tenant_id, fence_ordinal)
  );

  CREATE OR REPLACE FUNCTION relocation_evidence.canonical_field(p_value text)
  RETURNS text LANGUAGE sql IMMUTABLE STRICT
  SET search_path=pg_catalog
  AS \$\$
    SELECT octet_length(convert_to(p_value,'UTF8'))::text || ':' ||
           encode(convert_to(p_value,'UTF8'),'hex')
  \$\$;

  CREATE OR REPLACE FUNCTION relocation_evidence.canonical_checkpoint_payload(
    p_tenant uuid,p_fence bigint,p_checkpoint_id uuid,p_generation bigint,
    p_sealed boolean,p_count bigint,p_digest text,p_max bigint
  ) RETURNS text LANGUAGE sql IMMUTABLE STRICT
  SET search_path=pg_catalog,relocation_evidence
  AS \$\$
    SELECT
      relocation_evidence.canonical_field('open-rel-030-target-checkpoint-v1') ||
      relocation_evidence.canonical_field(p_tenant::text) ||
      relocation_evidence.canonical_field(p_fence::text) ||
      relocation_evidence.canonical_field(p_checkpoint_id::text) ||
      relocation_evidence.canonical_field(p_generation::text) ||
      relocation_evidence.canonical_field(p_sealed::text) ||
      relocation_evidence.canonical_field(p_count::text) ||
      relocation_evidence.canonical_field(p_digest) ||
      relocation_evidence.canonical_field(p_max::text)
  \$\$;

  CREATE OR REPLACE FUNCTION relocation_evidence.authoritative_digest(p_tenant uuid,p_fence bigint)
  RETURNS text LANGUAGE sql STABLE
  SET search_path=pg_catalog,relocation_evidence
  AS \$\$
    SELECT encode(public.digest(convert_to(coalesce(string_agg(
      relocation_evidence.canonical_field(accepted_ordinal::text) ||
      relocation_evidence.canonical_field(observation_id) ||
      relocation_evidence.canonical_field(metric_definition_id::text) ||
      relocation_evidence.canonical_field(
        to_char(observed_at AT TIME ZONE 'UTC','YYYY-MM-DD\"T\"HH24:MI:SS.US\"Z\"')
      ) ||
      relocation_evidence.canonical_field(trim_scale(numeric_value)::text),
      '' ORDER BY accepted_ordinal,observation_id
    ),''),'UTF8'),'sha256'),'hex')
    FROM relocation_evidence.acceptance
    WHERE tenant_id=p_tenant AND accepted_ordinal<=p_fence
  \$\$;

  CREATE OR REPLACE FUNCTION relocation_evidence.accept_observation(
    p_tenant uuid,p_writer text,p_placement_version bigint,p_observation_id text,
    p_metric_definition_id uuid,p_observed_at timestamptz,p_numeric_value numeric,
    p_hold_after_lock_seconds double precision DEFAULT 0
  ) RETURNS boolean
  LANGUAGE plpgsql
  AS \$\$
  DECLARE v_phase text; v_writer text; v_version bigint; v_inserted bigint;
  BEGIN
    SELECT phase,current_writer,placement_version
      INTO v_phase,v_writer,v_version
      FROM relocation_evidence.placement
     WHERE tenant_id=p_tenant FOR UPDATE;
    IF v_phase <> 'active' OR v_writer <> p_writer OR v_version <> p_placement_version THEN
      RETURN false;
    END IF;
    IF p_hold_after_lock_seconds > 0 THEN PERFORM pg_sleep(p_hold_after_lock_seconds); END IF;
    INSERT INTO relocation_evidence.acceptance(
      tenant_id,observation_id,metric_definition_id,observed_at,numeric_value,accepted_by,placement_version
    ) VALUES (
      p_tenant,p_observation_id,p_metric_definition_id,p_observed_at,p_numeric_value,p_writer,p_placement_version
    ) ON CONFLICT (tenant_id,observation_id) DO NOTHING;
    GET DIAGNOSTICS v_inserted = ROW_COUNT;
    RETURN v_inserted = 1;
  END;
  \$\$;

  CREATE OR REPLACE FUNCTION relocation_evidence.fence_source(p_tenant uuid)
  RETURNS bigint LANGUAGE plpgsql AS \$\$
  DECLARE v_phase text; v_writer text; v_f bigint;
  BEGIN
    SELECT phase,current_writer INTO v_phase,v_writer
      FROM relocation_evidence.placement WHERE tenant_id=p_tenant FOR UPDATE;
    IF v_phase <> 'active' OR v_writer <> 'source' THEN
      RAISE EXCEPTION 'source fence lost single-winner authority';
    END IF;
    SELECT coalesce(max(accepted_ordinal),0) INTO v_f
      FROM relocation_evidence.acceptance WHERE tenant_id=p_tenant;
    UPDATE relocation_evidence.placement
       SET phase='fenced',current_writer='none',fence_ordinal=v_f
     WHERE tenant_id=p_tenant;
    RETURN v_f;
  END;
  \$\$;

  CREATE OR REPLACE FUNCTION relocation_evidence.target_attestation_is_valid(
    p_tenant uuid,p_fence bigint,p_checkpoint_id uuid,p_checkpoint_generation bigint,
    p_target_sealed boolean,p_target_count bigint,p_target_digest text,
    p_target_max_ordinal bigint,p_target_attestation text
  ) RETURNS boolean LANGUAGE plpgsql
  SET search_path=pg_catalog,relocation_evidence,public
  AS \$\$
  DECLARE v_verified boolean;
  BEGIN
    SELECT verified INTO v_verified
    FROM public.dblink(
      'host=$ts_ip port=5432 dbname=jlmirror user=relocation_target_verifier password=$target_verify_password connect_timeout=2',
      format(
        'SELECT relocation_evidence.verify_target_attestation(%L::uuid,%s,%L::uuid,%s,%L::boolean,%s,%L,%s,%L)',
        p_tenant,p_fence,p_checkpoint_id,p_checkpoint_generation,p_target_sealed,
        p_target_count,p_target_digest,p_target_max_ordinal,p_target_attestation
      )
    ) AS r(verified boolean);
    RETURN coalesce(v_verified,false);
  EXCEPTION WHEN OTHERS THEN
    RETURN false;
  END;
  \$\$;

  CREATE OR REPLACE FUNCTION relocation_evidence.record_projection_receipt(
    p_tenant uuid,p_fence bigint,p_checkpoint_id uuid,p_checkpoint_generation bigint,
    p_target_sealed boolean,p_target_count bigint,p_target_digest text,
    p_target_max_ordinal bigint,p_target_attestation text
  ) RETURNS text LANGUAGE plpgsql
  SET search_path=pg_catalog,relocation_evidence
  AS \$\$
  DECLARE
    v_phase text; v_writer text; v_f bigint; v_source_count bigint;
    v_source_digest text; v_state text;
  BEGIN
    IF NOT relocation_evidence.target_attestation_is_valid(
      p_tenant,p_fence,p_checkpoint_id,p_checkpoint_generation,p_target_sealed,
      p_target_count,p_target_digest,p_target_max_ordinal,p_target_attestation
    ) THEN
      RAISE EXCEPTION 'target checkpoint not verified by target authority';
    END IF;

    SELECT phase,current_writer,fence_ordinal INTO v_phase,v_writer,v_f
      FROM relocation_evidence.placement WHERE tenant_id=p_tenant FOR UPDATE;
    IF v_phase <> 'fenced' OR v_writer <> 'none' OR v_f IS DISTINCT FROM p_fence THEN
      RAISE EXCEPTION 'projection receipt does not match current relocation fence';
    END IF;
    SELECT count(*),relocation_evidence.authoritative_digest(p_tenant,p_fence)
      INTO v_source_count,v_source_digest
      FROM relocation_evidence.acceptance WHERE tenant_id=p_tenant AND accepted_ordinal<=p_fence;
    v_state := CASE WHEN p_target_sealed AND p_target_count=v_source_count
      AND p_target_digest=v_source_digest AND p_target_max_ordinal=p_fence
      THEN 'complete' ELSE 'incomplete' END;
    INSERT INTO relocation_evidence.projection_receipt(
      tenant_id,fence_ordinal,checkpoint_id,checkpoint_generation,target_sealed,
      authoritative_count,authoritative_digest,target_count,target_digest,target_max_ordinal,
      target_attestation,state
    ) VALUES (
      p_tenant,p_fence,p_checkpoint_id,p_checkpoint_generation,p_target_sealed,
      v_source_count,v_source_digest,p_target_count,p_target_digest,p_target_max_ordinal,
      p_target_attestation,v_state
    ) ON CONFLICT (tenant_id,fence_ordinal) DO UPDATE SET
      checkpoint_id=EXCLUDED.checkpoint_id,checkpoint_generation=EXCLUDED.checkpoint_generation,
      target_sealed=EXCLUDED.target_sealed,authoritative_count=EXCLUDED.authoritative_count,
      authoritative_digest=EXCLUDED.authoritative_digest,target_count=EXCLUDED.target_count,
      target_digest=EXCLUDED.target_digest,target_max_ordinal=EXCLUDED.target_max_ordinal,
      target_attestation=EXCLUDED.target_attestation,state=EXCLUDED.state,
      verified_at=clock_timestamp();
    RETURN v_state;
  END;
  \$\$;

  CREATE OR REPLACE FUNCTION relocation_evidence.activate_target(p_tenant uuid)
  RETURNS boolean LANGUAGE plpgsql
  SET search_path=pg_catalog,relocation_evidence
  AS \$\$
  DECLARE
    v_f bigint; v_version bigint; v_new_version bigint;
    v_source_count bigint; v_source_digest text;
    v_before relocation_evidence.projection_receipt%ROWTYPE;
    v_receipt relocation_evidence.projection_receipt%ROWTYPE;
  BEGIN
    SELECT * INTO v_before FROM relocation_evidence.projection_receipt
     WHERE tenant_id=p_tenant AND state='complete' AND target_sealed
     ORDER BY verified_at DESC LIMIT 1;
    IF NOT FOUND THEN RETURN false; END IF;

    IF NOT relocation_evidence.target_attestation_is_valid(
      v_before.tenant_id,v_before.fence_ordinal,v_before.checkpoint_id,
      v_before.checkpoint_generation,v_before.target_sealed,v_before.target_count,
      v_before.target_digest,v_before.target_max_ordinal,v_before.target_attestation
    ) THEN
      RETURN false;
    END IF;

    SELECT fence_ordinal,placement_version INTO v_f,v_version
      FROM relocation_evidence.placement
     WHERE tenant_id=p_tenant AND phase='fenced' AND current_writer='none' FOR UPDATE;
    IF NOT FOUND OR v_f IS NULL OR v_f<>v_before.fence_ordinal THEN RETURN false; END IF;

    SELECT * INTO v_receipt FROM relocation_evidence.projection_receipt
     WHERE tenant_id=p_tenant AND fence_ordinal=v_f AND state='complete' AND target_sealed
     FOR UPDATE;
    IF NOT FOUND
       OR v_receipt.checkpoint_id<>v_before.checkpoint_id
       OR v_receipt.checkpoint_generation<>v_before.checkpoint_generation
       OR v_receipt.target_attestation<>v_before.target_attestation THEN
      RETURN false;
    END IF;

    SELECT count(*),relocation_evidence.authoritative_digest(p_tenant,v_f)
      INTO v_source_count,v_source_digest
      FROM relocation_evidence.acceptance WHERE tenant_id=p_tenant AND accepted_ordinal<=v_f;
    IF v_receipt.authoritative_count<>v_source_count
       OR v_receipt.authoritative_digest<>v_source_digest
       OR v_receipt.target_count<>v_source_count
       OR v_receipt.target_digest<>v_source_digest
       OR v_receipt.target_max_ordinal<>v_f THEN RETURN false; END IF;

    v_new_version:=v_version+1;
    INSERT INTO relocation_evidence.activation_grant(
      tenant_id,fence_ordinal,checkpoint_id,checkpoint_generation,target_attestation,
      placement_version,state
    ) VALUES(
      p_tenant,v_f,v_receipt.checkpoint_id,v_receipt.checkpoint_generation,
      v_receipt.target_attestation,v_new_version,'committed'
    ) ON CONFLICT (tenant_id,fence_ordinal) DO NOTHING;
    IF NOT FOUND THEN RETURN false; END IF;

    UPDATE relocation_evidence.placement
       SET phase='active',current_writer='target',placement_version=v_new_version
     WHERE tenant_id=p_tenant AND phase='fenced' AND current_writer='none'
       AND placement_version=v_version;
    RETURN FOUND;
  END;
  \$\$;

  CREATE OR REPLACE FUNCTION relocation_evidence.verify_activation_grant(
    p_tenant uuid,p_fence bigint,p_checkpoint_id uuid,p_checkpoint_generation bigint,
    p_placement_version bigint,p_target_attestation text
  ) RETURNS boolean
  LANGUAGE sql STABLE SECURITY DEFINER
  SET search_path=pg_catalog,relocation_evidence
  AS \$\$
    SELECT EXISTS(
      SELECT 1
      FROM relocation_evidence.activation_grant g
      JOIN relocation_evidence.placement p USING (tenant_id)
      WHERE g.tenant_id=p_tenant
        AND g.fence_ordinal=p_fence
        AND g.checkpoint_id=p_checkpoint_id
        AND g.checkpoint_generation=p_checkpoint_generation
        AND g.placement_version=p_placement_version
        AND g.target_attestation=p_target_attestation
        AND g.state='committed'
        AND p.phase='active'
        AND p.current_writer='target'
        AND p.fence_ordinal=p_fence
        AND p.placement_version=p_placement_version
    )
  \$\$;
  REVOKE ALL ON FUNCTION relocation_evidence.verify_activation_grant(uuid,bigint,uuid,bigint,bigint,text) FROM PUBLIC;
  GRANT USAGE ON SCHEMA relocation_evidence TO relocation_tier1_verifier;
  GRANT EXECUTE ON FUNCTION relocation_evidence.verify_activation_grant(uuid,bigint,uuid,bigint,bigint,text)
    TO relocation_tier1_verifier;
  REVOKE ALL ON relocation_evidence.activation_grant FROM relocation_tier1_verifier;
  REVOKE ALL ON relocation_evidence.placement FROM relocation_tier1_verifier;

  INSERT INTO relocation_evidence.placement(tenant_id,phase,current_writer,placement_version)
  VALUES ('$tenant','active','source',1);
" >/dev/null

pre1="$(pg_sql "SELECT relocation_evidence.accept_observation('$tenant','source',1,'obs-pre-1','$metric','2026-08-28T10:00:00Z',10.5)::text;")"
pre2="$(pg_sql "SELECT relocation_evidence.accept_observation('$tenant','source',1,'obs-pre-2','$metric','2026-08-28T10:01:00Z',11.5)::text;")"
assert_exact "relocation_source_pre1_accept" "true" "$pre1"
assert_exact "relocation_source_pre2_accept" "true" "$pre2"

serialization_probe="$(pg_sql "
  SELECT (
    ('a' || E'\\x1f' || (E'b\\x1ec')) = ((E'a\\x1fb') || E'\\x1e' || 'c')
  )::text || '|' || (
    relocation_evidence.canonical_field('a') || relocation_evidence.canonical_field(E'b\\x1ec') <>
    relocation_evidence.canonical_field(E'a\\x1fb') || relocation_evidence.canonical_field('c')
  )::text;
")"
assert_exact "relocation_delimiter_collision_closed" "true|true" "$serialization_probe"
assert_exact "relocation_tier1_has_no_target_signing_key" "true" \
  "$(pg_sql "SELECT (to_regclass('relocation_evidence.target_attestation_key') IS NULL)::text;")"
expect_pg_reject "relocation_remote_activation_verifier_cannot_read_grant_table" "permission denied" \
  "SET ROLE relocation_tier1_verifier; SELECT * FROM relocation_evidence.activation_grant;"
