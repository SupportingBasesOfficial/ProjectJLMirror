# ---------------------------------------------------------------------------
# Tier 2 target authority. The effective checkpoint HMAC key is generated
# inside this database authority; it is not provisioned by Tier 1 or the shell
# controller. The controller remains trusted laboratory setup/fault injection,
# not a modeled production/Tier-1 application principal.
# The verifier role can ask yes/no questions but cannot read key/state tables.
# ---------------------------------------------------------------------------
ts_sql "
  CREATE EXTENSION IF NOT EXISTS pgcrypto;
  CREATE EXTENSION IF NOT EXISTS dblink;
  DROP SCHEMA IF EXISTS relocation_evidence CASCADE;
  DO \$\$
  BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='relocation_target_verifier') THEN
      EXECUTE 'DROP OWNED BY relocation_target_verifier';
      EXECUTE 'DROP ROLE relocation_target_verifier';
    END IF;
  END
  \$\$;
  CREATE ROLE relocation_target_verifier LOGIN PASSWORD '$target_verify_password';
  ALTER ROLE relocation_target_verifier SET statement_timeout='2s';
  CREATE SCHEMA relocation_evidence AUTHORIZATION ts_owner;
  GRANT USAGE ON SCHEMA relocation_evidence TO ts_automation_owner;

  CREATE TABLE relocation_evidence.target_history(
    tenant_id uuid NOT NULL,
    observation_id text NOT NULL,
    metric_definition_id uuid NOT NULL,
    accepted_ordinal bigint NOT NULL,
    observed_at timestamptz NOT NULL,
    numeric_value numeric NOT NULL,
    UNIQUE(tenant_id,observation_id,observed_at)
  );
  ALTER TABLE relocation_evidence.target_history OWNER TO ts_owner;
  SELECT public.create_hypertable('relocation_evidence.target_history','observed_at',chunk_time_interval=>interval '1 day');

  CREATE TABLE relocation_evidence.target_control(
    tenant_id uuid PRIMARY KEY,
    phase text NOT NULL CHECK(phase IN('open','sealed','activated')),
    fence_ordinal bigint,
    checkpoint_id uuid,
    checkpoint_generation bigint NOT NULL DEFAULT 0
  );
  ALTER TABLE relocation_evidence.target_control OWNER TO ts_owner;

  CREATE TABLE relocation_evidence.target_checkpoint(
    checkpoint_id uuid PRIMARY KEY,
    tenant_id uuid NOT NULL,
    fence_ordinal bigint NOT NULL,
    checkpoint_generation bigint NOT NULL,
    target_count bigint NOT NULL,
    target_digest text NOT NULL,
    target_max_ordinal bigint NOT NULL,
    attestation text NOT NULL,
    sealed_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    UNIQUE(tenant_id,checkpoint_generation)
  );
  ALTER TABLE relocation_evidence.target_checkpoint OWNER TO ts_owner;

  CREATE TABLE relocation_evidence.target_attestation_key(
    singleton boolean PRIMARY KEY DEFAULT true CHECK(singleton),
    key_material text NOT NULL
  );
  ALTER TABLE relocation_evidence.target_attestation_key OWNER TO ts_owner;
  INSERT INTO relocation_evidence.target_attestation_key(singleton,key_material)
  VALUES(true,encode(gen_random_bytes(32),'hex'));

  INSERT INTO relocation_evidence.target_control(tenant_id,phase) VALUES('$tenant','open');

  GRANT SELECT,INSERT,UPDATE,DELETE ON relocation_evidence.target_history TO ts_automation_owner;
  REVOKE ALL ON relocation_evidence.target_control FROM PUBLIC,ts_runtime,ts_report_a,ts_report_b,ts_automation_owner;
  REVOKE ALL ON relocation_evidence.target_checkpoint FROM PUBLIC,ts_runtime,ts_report_a,ts_report_b,ts_automation_owner;
  REVOKE ALL ON relocation_evidence.target_attestation_key FROM PUBLIC,ts_runtime,ts_report_a,ts_report_b,ts_automation_owner,relocation_target_verifier;
  REVOKE ALL ON relocation_evidence.target_history FROM PUBLIC,ts_runtime,ts_report_a,ts_report_b,relocation_target_verifier;

  CREATE OR REPLACE FUNCTION relocation_evidence.canonical_field(p_value text)
  RETURNS text LANGUAGE sql IMMUTABLE STRICT SECURITY DEFINER
  SET search_path=pg_catalog
  AS \$\$
    SELECT octet_length(convert_to(p_value,'UTF8'))::text || ':' ||
           encode(convert_to(p_value,'UTF8'),'hex')
  \$\$;
  ALTER FUNCTION relocation_evidence.canonical_field(text) OWNER TO ts_owner;
  REVOKE ALL ON FUNCTION relocation_evidence.canonical_field(text) FROM PUBLIC;

  CREATE OR REPLACE FUNCTION relocation_evidence.canonical_checkpoint_payload(
    p_tenant uuid,p_fence bigint,p_checkpoint_id uuid,p_generation bigint,
    p_sealed boolean,p_count bigint,p_digest text,p_max bigint
  ) RETURNS text LANGUAGE sql IMMUTABLE STRICT SECURITY DEFINER
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
  ALTER FUNCTION relocation_evidence.canonical_checkpoint_payload(uuid,bigint,uuid,bigint,boolean,bigint,text,bigint) OWNER TO ts_owner;
  REVOKE ALL ON FUNCTION relocation_evidence.canonical_checkpoint_payload(uuid,bigint,uuid,bigint,boolean,bigint,text,bigint) FROM PUBLIC;

  CREATE OR REPLACE FUNCTION relocation_evidence.target_digest(p_tenant uuid,p_fence bigint)
  RETURNS text LANGUAGE sql STABLE SECURITY DEFINER
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
    FROM relocation_evidence.target_history
    WHERE tenant_id=p_tenant AND accepted_ordinal<=p_fence
  \$\$;
  ALTER FUNCTION relocation_evidence.target_digest(uuid,bigint) OWNER TO ts_owner;
  REVOKE ALL ON FUNCTION relocation_evidence.target_digest(uuid,bigint) FROM PUBLIC;

  CREATE OR REPLACE FUNCTION relocation_evidence.freeze_target_history()
  RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER
  SET search_path=pg_catalog,relocation_evidence
  AS \$\$
  DECLARE v_control record;
  BEGIN
    IF TG_OP='UPDATE' AND NEW.tenant_id IS DISTINCT FROM OLD.tenant_id THEN
      RAISE EXCEPTION 'target history tenant identity is immutable';
    END IF;
    FOR v_control IN
      SELECT tenant_id,phase,fence_ordinal
        FROM relocation_evidence.target_control
       WHERE tenant_id IN (
         CASE WHEN TG_OP='INSERT' THEN NEW.tenant_id ELSE OLD.tenant_id END,
         CASE WHEN TG_OP='DELETE' THEN OLD.tenant_id ELSE NEW.tenant_id END
       )
       ORDER BY tenant_id FOR SHARE
    LOOP
      IF v_control.phase='sealed' THEN
        RAISE EXCEPTION 'sealed target checkpoint forbids all pre-activation mutation';
      END IF;
      IF v_control.phase='activated' THEN
        IF TG_OP <> 'INSERT' THEN RAISE EXCEPTION 'activated target history is immutable'; END IF;
        IF NEW.tenant_id=v_control.tenant_id
           AND v_control.fence_ordinal IS NOT NULL
           AND NEW.accepted_ordinal<=v_control.fence_ordinal THEN
          RAISE EXCEPTION 'activated target rejects ordinal through relocation fence';
        END IF;
      END IF;
    END LOOP;
    IF TG_OP='DELETE' THEN RETURN OLD; END IF;
    RETURN NEW;
  END;
  \$\$;
  ALTER FUNCTION relocation_evidence.freeze_target_history() OWNER TO ts_owner;

  CREATE TRIGGER target_history_freeze
  BEFORE INSERT OR UPDATE OR DELETE ON relocation_evidence.target_history
  FOR EACH ROW EXECUTE FUNCTION relocation_evidence.freeze_target_history();

  CREATE OR REPLACE FUNCTION relocation_evidence.attest_target_checkpoint(
    p_tenant uuid,p_fence bigint,p_seal boolean,p_hold_after_lock_seconds double precision DEFAULT 0
  ) RETURNS TABLE(
    checkpoint_id uuid,checkpoint_generation bigint,target_sealed boolean,
    target_count bigint,target_digest text,target_max_ordinal bigint,attestation text
  ) LANGUAGE plpgsql SECURITY DEFINER
  SET search_path=pg_catalog,relocation_evidence
  AS \$\$
  DECLARE
    v_phase text; v_generation bigint; v_key text; v_checkpoint_id uuid;
    v_count bigint; v_digest text; v_max bigint; v_attestation text; v_future bigint;
    v_payload text;
  BEGIN
    SELECT tc.phase,tc.checkpoint_generation INTO v_phase,v_generation
      FROM relocation_evidence.target_control tc
     WHERE tc.tenant_id=p_tenant FOR UPDATE;
    IF NOT FOUND THEN RAISE EXCEPTION 'target checkpoint has no control authority'; END IF;
    IF p_seal AND v_phase<>'open' THEN RAISE EXCEPTION 'target checkpoint already sealed or activated'; END IF;
    IF p_hold_after_lock_seconds>0 THEN PERFORM pg_sleep(p_hold_after_lock_seconds); END IF;
    IF p_seal THEN
      SELECT count(*) INTO v_future FROM relocation_evidence.target_history
       WHERE tenant_id=p_tenant AND accepted_ordinal>p_fence;
      IF v_future<>0 THEN RAISE EXCEPTION 'target contains uncheckpointed rows above fence'; END IF;
    END IF;
    SELECT count(*),relocation_evidence.target_digest(p_tenant,p_fence),coalesce(max(accepted_ordinal),0)
      INTO v_count,v_digest,v_max
      FROM relocation_evidence.target_history
     WHERE tenant_id=p_tenant AND accepted_ordinal<=p_fence;
    v_checkpoint_id:=gen_random_uuid();
    v_generation:=v_generation+1;
    SELECT key_material INTO STRICT v_key FROM relocation_evidence.target_attestation_key WHERE singleton;
    v_payload := relocation_evidence.canonical_checkpoint_payload(
      p_tenant,p_fence,v_checkpoint_id,v_generation,p_seal,v_count,v_digest,v_max
    );
    v_attestation:=encode(public.hmac(convert_to(v_payload,'UTF8'),decode(v_key,'hex'),'sha256'),'hex');
    IF p_seal THEN
      UPDATE relocation_evidence.target_control
         SET phase='sealed',fence_ordinal=p_fence,checkpoint_id=v_checkpoint_id,
             checkpoint_generation=v_generation
       WHERE tenant_id=p_tenant;
      INSERT INTO relocation_evidence.target_checkpoint(
        checkpoint_id,tenant_id,fence_ordinal,checkpoint_generation,target_count,
        target_digest,target_max_ordinal,attestation
      ) VALUES(v_checkpoint_id,p_tenant,p_fence,v_generation,v_count,v_digest,v_max,v_attestation);
    END IF;
    checkpoint_id:=v_checkpoint_id; checkpoint_generation:=v_generation;
    target_sealed:=p_seal; target_count:=v_count; target_digest:=v_digest;
    target_max_ordinal:=v_max; attestation:=v_attestation;
    RETURN NEXT;
  END;
  \$\$;
  ALTER FUNCTION relocation_evidence.attest_target_checkpoint(uuid,bigint,boolean,double precision) OWNER TO ts_owner;
  REVOKE ALL ON FUNCTION relocation_evidence.attest_target_checkpoint(uuid,bigint,boolean,double precision) FROM PUBLIC;
  GRANT EXECUTE ON FUNCTION relocation_evidence.attest_target_checkpoint(uuid,bigint,boolean,double precision) TO ts_automation_owner;

  CREATE OR REPLACE FUNCTION relocation_evidence.verify_target_attestation(
    p_tenant uuid,p_fence bigint,p_checkpoint_id uuid,p_checkpoint_generation bigint,
    p_target_sealed boolean,p_target_count bigint,p_target_digest text,
    p_target_max_ordinal bigint,p_target_attestation text
  ) RETURNS boolean LANGUAGE plpgsql STABLE SECURITY DEFINER
  SET search_path=pg_catalog,relocation_evidence
  AS \$\$
  DECLARE
    v_key text; v_payload text; v_expected text;
    v_count bigint; v_digest text; v_max bigint;
  BEGIN
    SELECT key_material INTO STRICT v_key FROM relocation_evidence.target_attestation_key WHERE singleton;
    v_payload:=relocation_evidence.canonical_checkpoint_payload(
      p_tenant,p_fence,p_checkpoint_id,p_checkpoint_generation,p_target_sealed,
      p_target_count,p_target_digest,p_target_max_ordinal
    );
    v_expected:=encode(public.hmac(convert_to(v_payload,'UTF8'),decode(v_key,'hex'),'sha256'),'hex');
    IF v_expected IS DISTINCT FROM p_target_attestation THEN RETURN false; END IF;

    IF p_target_sealed THEN
      RETURN EXISTS(
        SELECT 1
        FROM relocation_evidence.target_control tc
        JOIN relocation_evidence.target_checkpoint cp ON cp.checkpoint_id=tc.checkpoint_id
        WHERE tc.tenant_id=p_tenant
          AND tc.phase='sealed'
          AND tc.fence_ordinal=p_fence
          AND tc.checkpoint_id=p_checkpoint_id
          AND tc.checkpoint_generation=p_checkpoint_generation
          AND cp.tenant_id=p_tenant
          AND cp.fence_ordinal=p_fence
          AND cp.checkpoint_generation=p_checkpoint_generation
          AND cp.target_count=p_target_count
          AND cp.target_digest=p_target_digest
          AND cp.target_max_ordinal=p_target_max_ordinal
          AND cp.attestation=p_target_attestation
      );
    END IF;

    SELECT count(*),relocation_evidence.target_digest(p_tenant,p_fence),coalesce(max(accepted_ordinal),0)
      INTO v_count,v_digest,v_max
      FROM relocation_evidence.target_history
     WHERE tenant_id=p_tenant AND accepted_ordinal<=p_fence;
    RETURN v_count=p_target_count AND v_digest=p_target_digest AND v_max=p_target_max_ordinal;
  END;
  \$\$;
  ALTER FUNCTION relocation_evidence.verify_target_attestation(uuid,bigint,uuid,bigint,boolean,bigint,text,bigint,text) OWNER TO ts_owner;
  REVOKE ALL ON FUNCTION relocation_evidence.verify_target_attestation(uuid,bigint,uuid,bigint,boolean,bigint,text,bigint,text) FROM PUBLIC;
  GRANT USAGE ON SCHEMA relocation_evidence TO relocation_target_verifier;
  GRANT EXECUTE ON FUNCTION relocation_evidence.verify_target_attestation(uuid,bigint,uuid,bigint,boolean,bigint,text,bigint,text)
    TO relocation_target_verifier;

  CREATE OR REPLACE FUNCTION relocation_evidence.tier1_activation_grant_is_valid(
    p_tenant uuid,p_fence bigint,p_checkpoint_id uuid,p_checkpoint_generation bigint,
    p_placement_version bigint,p_target_attestation text
  ) RETURNS boolean LANGUAGE plpgsql
  SET search_path=pg_catalog,public
  AS \$\$
  DECLARE v_verified boolean;
  BEGIN
    SELECT verified INTO v_verified
    FROM public.dblink(
      'host=$pg_ip port=5432 dbname=jlmirror user=relocation_tier1_verifier password=$tier1_verify_password connect_timeout=2',
      format(
        'SELECT relocation_evidence.verify_activation_grant(%L::uuid,%s,%L::uuid,%s,%s,%L)',
        p_tenant,p_fence,p_checkpoint_id,p_checkpoint_generation,p_placement_version,p_target_attestation
      )
    ) AS r(verified boolean);
    RETURN coalesce(v_verified,false);
  EXCEPTION WHEN OTHERS THEN
    RETURN false;
  END;
  \$\$;
  ALTER FUNCTION relocation_evidence.tier1_activation_grant_is_valid(uuid,bigint,uuid,bigint,bigint,text) OWNER TO ts_owner;
  REVOKE ALL ON FUNCTION relocation_evidence.tier1_activation_grant_is_valid(uuid,bigint,uuid,bigint,bigint,text) FROM PUBLIC;

  CREATE OR REPLACE FUNCTION relocation_evidence.mark_target_checkpoint_activated(
    p_tenant uuid,p_checkpoint_id uuid,p_expected_placement_version bigint
  ) RETURNS boolean LANGUAGE plpgsql SECURITY DEFINER
  SET search_path=pg_catalog,relocation_evidence
  AS \$\$
  DECLARE
    v_f bigint; v_generation bigint; v_attestation text;
    v_locked_f bigint; v_locked_generation bigint; v_locked_checkpoint uuid;
  BEGIN
    SELECT tc.fence_ordinal,tc.checkpoint_generation,cp.attestation
      INTO v_f,v_generation,v_attestation
      FROM relocation_evidence.target_control tc
      JOIN relocation_evidence.target_checkpoint cp ON cp.checkpoint_id=tc.checkpoint_id
     WHERE tc.tenant_id=p_tenant AND tc.phase='sealed' AND tc.checkpoint_id=p_checkpoint_id;
    IF NOT FOUND THEN RETURN false; END IF;

    IF NOT relocation_evidence.tier1_activation_grant_is_valid(
      p_tenant,v_f,p_checkpoint_id,v_generation,p_expected_placement_version,v_attestation
    ) THEN
      RETURN false;
    END IF;

    SELECT fence_ordinal,checkpoint_generation,checkpoint_id
      INTO v_locked_f,v_locked_generation,v_locked_checkpoint
      FROM relocation_evidence.target_control
     WHERE tenant_id=p_tenant FOR UPDATE;
    IF NOT FOUND
       OR v_locked_checkpoint<>p_checkpoint_id
       OR v_locked_f<>v_f
       OR v_locked_generation<>v_generation
       OR (SELECT phase FROM relocation_evidence.target_control WHERE tenant_id=p_tenant)<>'sealed' THEN
      RETURN false;
    END IF;

    UPDATE relocation_evidence.target_control SET phase='activated'
     WHERE tenant_id=p_tenant AND phase='sealed' AND checkpoint_id=p_checkpoint_id
       AND checkpoint_generation=v_generation AND fence_ordinal=v_f;
    RETURN FOUND;
  END;
  \$\$;
  ALTER FUNCTION relocation_evidence.mark_target_checkpoint_activated(uuid,uuid,bigint) OWNER TO ts_owner;
  REVOKE ALL ON FUNCTION relocation_evidence.mark_target_checkpoint_activated(uuid,uuid,bigint) FROM PUBLIC;
  GRANT EXECUTE ON FUNCTION relocation_evidence.mark_target_checkpoint_activated(uuid,uuid,bigint) TO ts_automation_owner;
" >/dev/null
