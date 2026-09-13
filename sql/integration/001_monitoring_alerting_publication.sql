-- Wave 4 Monitoring -> Alerting publication bridge runtime.
-- Authority: wave4.monitoring-alerting-publication@1.
-- This is a composed cross-wave migration: it requires the accepted Wave 2
-- async outbox substrate plus the accepted Wave 4 Problem/Health transition tables.
-- It creates no broker, no second outbox, and no Alerting business state.

BEGIN;

DO $$
DECLARE
    v_executor_oid OID;
BEGIN
    IF to_regclass('system.async_outbox_message') IS NULL
       OR to_regclass('system.async_outbox_dispatch') IS NULL THEN
        RAISE EXCEPTION 'monitoring.publication_wave2_outbox_substrate_required';
    END IF;
    IF to_regclass('monitoring.monitoring_problem_transition') IS NULL
       OR to_regclass('monitoring.health_projection_transition') IS NULL THEN
        RAISE EXCEPTION 'monitoring.publication_wave4_transition_substrate_required';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='jlmirror_wave4_recovery_authority') THEN
        RAISE EXCEPTION 'monitoring.publication_recovery_authority_required';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='jlmirror_wave4_monitoring_publication_executor') THEN
        CREATE ROLE jlmirror_wave4_monitoring_publication_executor
            NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS;
    END IF;

    SELECT oid INTO v_executor_oid
      FROM pg_roles
     WHERE rolname='jlmirror_wave4_monitoring_publication_executor';

    IF EXISTS (
        SELECT 1
          FROM pg_roles
         WHERE oid=v_executor_oid
           AND (rolcanlogin OR rolsuper OR rolcreatedb OR rolcreaterole OR rolinherit OR rolreplication OR rolbypassrls)
    ) THEN
        RAISE EXCEPTION 'monitoring.publication_executor_unsafe_attributes';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM pg_auth_members
         WHERE roleid=v_executor_oid OR member=v_executor_oid
    ) THEN
        RAISE EXCEPTION 'monitoring.publication_executor_unsafe_membership';
    END IF;
END;
$$;

-- The executor is a dedicated capability owner. Before granting it any outbox
-- authority, prove via PostgreSQL ownership dependencies that it owns no
-- persistent object of any class outside this bridge's five canonical routines.
-- This closes owner-mediated authority through views, materialized views,
-- relations, sequences, schemas, types, or any other object class as well as
-- unrelated SECURITY DEFINER routines.
DO $$
DECLARE
    v_executor_oid OID;
    v_unexpected TEXT;
BEGIN
    SELECT oid INTO v_executor_oid
      FROM pg_roles
     WHERE rolname='jlmirror_wave4_monitoring_publication_executor';

    WITH allowed_proc_oids AS (
        SELECT to_regprocedure(signature) AS proc_oid
          FROM (VALUES
              ('monitoring.wave4_ensure_monitoring_invalidation(text,text,text,text,text,timestamptz,jsonb)'),
              ('monitoring.wave4_publish_problem_transition()'),
              ('monitoring.wave4_publish_health_transition()'),
              ('monitoring.recover_problem_state_publication(text,text)'),
              ('monitoring.recover_health_projection_publication(text,text)')
          ) AS allowed(signature)
    )
    SELECT format('class=%s,objid=%s,dbid=%s', d.classid::regclass::TEXT, d.objid, d.dbid)
      INTO v_unexpected
      FROM pg_shdepend d
     WHERE d.refclassid='pg_authid'::regclass
       AND d.refobjid=v_executor_oid
       AND d.deptype='o'
       AND NOT (
            d.classid='pg_proc'::regclass
            AND d.objid IN (
                SELECT proc_oid
                  FROM allowed_proc_oids
                 WHERE proc_oid IS NOT NULL
            )
       )
     ORDER BY d.dbid,d.classid,d.objid
     LIMIT 1;

    IF v_unexpected IS NOT NULL THEN
        RAISE EXCEPTION 'monitoring.publication_executor_unexpected_owned_object:%', v_unexpected;
    END IF;
END;
$$;

-- CREATE OR REPLACE preserves a function OID. Any pre-existing database object
-- that depends on either trigger-function OID would therefore remain attached
-- after the function is replaced and elevated to SECURITY DEFINER. Reject every
-- inbound persistent dependency before outbox grants land; this includes
-- pg_trigger bindings and also rules/defaults/generated expressions/indexes or
-- other catalog objects that could retain an invocation path to the old OID.
DO $$
DECLARE
    v_row RECORD;
    v_proc_oid OID;
    v_dependency TEXT;
BEGIN
    FOR v_row IN
        SELECT signature
          FROM (VALUES
              ('monitoring.wave4_publish_problem_transition()'),
              ('monitoring.wave4_publish_health_transition()')
          ) AS guarded(signature)
    LOOP
        v_proc_oid := to_regprocedure(v_row.signature);
        IF v_proc_oid IS NULL THEN
            CONTINUE;
        END IF;

        SELECT format(
                   'class=%s,objid=%s,objsubid=%s,deptype=%s',
                   d.classid::regclass::TEXT,d.objid,d.objsubid,d.deptype
               )
          INTO v_dependency
          FROM pg_depend d
         WHERE d.refclassid='pg_proc'::regclass
           AND d.refobjid=v_proc_oid
         ORDER BY d.classid,d.objid,d.objsubid,d.deptype
         LIMIT 1;

        IF v_dependency IS NOT NULL THEN
            RAISE EXCEPTION 'monitoring.publication_existing_function_dependency_unsafe:%:%',
                v_row.signature,v_dependency;
        END IF;
    END LOOP;
END;
$$;

GRANT USAGE ON SCHEMA monitoring, system
TO jlmirror_wave4_monitoring_publication_executor;
REVOKE CREATE ON SCHEMA monitoring, system
FROM jlmirror_wave4_monitoring_publication_executor;

-- The publication executor is NOLOGIN and is never granted to application roles.
-- It owns the SECURITY DEFINER bridge functions and has only the exact storage
-- privileges required to materialize/recover accepted outbox obligations.
GRANT SELECT, INSERT ON system.async_outbox_message
TO jlmirror_wave4_monitoring_publication_executor;
GRANT SELECT, INSERT ON system.async_outbox_dispatch
TO jlmirror_wave4_monitoring_publication_executor;
GRANT USAGE, SELECT ON SEQUENCE system.async_outbox_message_outbox_record_id_seq
TO jlmirror_wave4_monitoring_publication_executor;
GRANT SELECT ON monitoring.monitoring_problem_transition,
    monitoring.health_projection_transition
TO jlmirror_wave4_monitoring_publication_executor;

-- CREATE OR REPLACE FUNCTION preserves existing ACLs. Because the following
-- functions become SECURITY DEFINER under a privileged NOLOGIN owner, any
-- unexpected retained named EXECUTE grant must be rejected before the body is
-- replaced. Recovery functions may retain only a non-grantable EXECUTE for the
-- canonical recovery authority; WITH GRANT OPTION is never accepted.
DO $$
DECLARE
    v_recovery_oid OID;
    v_row RECORD;
    v_proc_oid OID;
BEGIN
    SELECT oid INTO v_recovery_oid
      FROM pg_roles
     WHERE rolname='jlmirror_wave4_recovery_authority';

    FOR v_row IN
        SELECT *
          FROM (VALUES
              ('monitoring.wave4_ensure_monitoring_invalidation(text,text,text,text,text,timestamptz,jsonb)', false),
              ('monitoring.wave4_publish_problem_transition()', false),
              ('monitoring.wave4_publish_health_transition()', false),
              ('monitoring.recover_problem_state_publication(text,text)', true),
              ('monitoring.recover_health_projection_publication(text,text)', true)
          ) AS guarded(signature, allow_recovery_authority)
    LOOP
        v_proc_oid := to_regprocedure(v_row.signature);
        IF v_proc_oid IS NULL THEN
            CONTINUE;
        END IF;

        IF EXISTS (
            SELECT 1
              FROM pg_proc p,
                   LATERAL aclexplode(COALESCE(p.proacl, ARRAY[]::aclitem[])) a
             WHERE p.oid=v_proc_oid
               AND a.privilege_type='EXECUTE'
               AND a.grantee<>0
               AND a.grantee<>p.proowner
               AND (
                    NOT v_row.allow_recovery_authority
                    OR a.grantee<>v_recovery_oid
                    OR a.is_grantable
               )
        ) THEN
            RAISE EXCEPTION 'monitoring.publication_existing_function_acl_unsafe:%', v_row.signature;
        END IF;
    END LOOP;
END;
$$;

CREATE OR REPLACE FUNCTION monitoring.wave4_ensure_monitoring_invalidation(
    p_tenant_id TEXT,
    p_contract_name TEXT,
    p_subject_type TEXT,
    p_subject_id TEXT,
    p_transition_id TEXT,
    p_occurred_at TIMESTAMPTZ,
    p_payload JSONB
) RETURNS BIGINT
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, monitoring, system
AS $$
DECLARE
    v_keys TEXT[];
    v_message_id TEXT;
    v_correlation_id TEXT;
    v_causation_id TEXT;
    v_producer_scope TEXT;
    v_payload_bytes BYTEA;
    v_equivalence_bytes BYTEA;
    v_outbox_id BIGINT;
    v_existing system.async_outbox_message%ROWTYPE;
BEGIN
    IF p_tenant_id IS NULL OR p_tenant_id='' OR length(p_tenant_id)>512
       OR p_subject_id IS NULL OR p_subject_id='' OR length(p_subject_id)>1024
       OR p_transition_id IS NULL OR p_transition_id='' OR length(p_transition_id)>1024
       OR p_occurred_at IS NULL
       OR p_payload IS NULL OR jsonb_typeof(p_payload)<>'object' THEN
        RAISE EXCEPTION 'monitoring.publication_invalid_input';
    END IF;

    SELECT array_agg(k ORDER BY k)
      INTO v_keys
      FROM jsonb_object_keys(p_payload) AS keys(k);

    IF p_contract_name='monitoring.problem-state.changed' THEN
        IF p_subject_type<>'monitoring_problem'
           OR v_keys IS DISTINCT FROM ARRAY[
                'monitoring_resource_id','monitoring_source_id','problem_id',
                'problem_transition_id','projection_revision','source_instance_generation'
           ]::TEXT[]
           OR p_payload->>'problem_id' IS DISTINCT FROM p_subject_id
           OR p_payload->>'problem_transition_id' IS DISTINCT FROM p_transition_id THEN
            RAISE EXCEPTION 'monitoring.publication_problem_contract_shape_mismatch';
        END IF;
    ELSIF p_contract_name='monitoring.health-projection.changed' THEN
        IF p_subject_type<>'monitoring_resource'
           OR v_keys IS DISTINCT FROM ARRAY[
                'health_transition_id','monitoring_resource_id','monitoring_source_id',
                'projection_revision','source_instance_generation'
           ]::TEXT[]
           OR p_payload->>'monitoring_resource_id' IS DISTINCT FROM p_subject_id
           OR p_payload->>'health_transition_id' IS DISTINCT FROM p_transition_id THEN
            RAISE EXCEPTION 'monitoring.publication_health_contract_shape_mismatch';
        END IF;
    ELSE
        RAISE EXCEPTION 'monitoring.publication_contract_not_authorized';
    END IF;

    -- Stable compact identities. md5 is used only as deterministic compaction;
    -- full immutable equivalence is checked below, so a compaction collision with
    -- different meaning fails closed rather than becoming duplicate success.
    v_producer_scope := 'monitoring:tenant:' || md5(p_tenant_id);
    v_message_id := p_contract_name || '@1:' || md5(p_tenant_id || chr(31) || p_transition_id);
    v_correlation_id := 'monitoring-correlation:' || md5(p_tenant_id || chr(31) || p_transition_id);
    v_causation_id := 'monitoring-transition:' || md5(
        p_contract_name || chr(31) || p_tenant_id || chr(31) || p_transition_id
    );

    IF v_message_id=v_correlation_id OR v_message_id=v_causation_id OR v_correlation_id=v_causation_id THEN
        RAISE EXCEPTION 'monitoring.publication_envelope_identity_collision';
    END IF;

    v_payload_bytes := convert_to(p_payload::TEXT, 'UTF8');
    IF octet_length(v_payload_bytes)>16384 THEN
        RAISE EXCEPTION 'monitoring.publication_payload_overbound';
    END IF;

    v_equivalence_bytes := convert_to(jsonb_build_object(
        'message_class','integration_event',
        'contract_name',p_contract_name,
        'contract_version','1',
        'producer','Monitoring',
        'tenant_id',p_tenant_id,
        'subject_type',p_subject_type,
        'subject_id',p_subject_id,
        'message_id',v_message_id,
        'occurred_at_epoch',extract(epoch FROM p_occurred_at),
        'correlation_id',v_correlation_id,
        'causation_id',v_causation_id,
        'data_classification','confidential_tenant',
        'payload',p_payload
    )::TEXT, 'UTF8');

    INSERT INTO system.async_outbox_message(
        producer_message_scope,message_id,message_class,contract_name,contract_version,
        producer,producer_generation,scope_class,tenant_id,subject_type,subject_id,
        occurred_at,created_at,operation_id,not_before,deadline,correlation_id,causation_id,
        data_classification,serialization_profile_id,encoded_payload,
        comparison_profile_id,comparison_profile_version,comparison_evidence_form,
        comparison_verifier_generation,comparison_evidence
    ) VALUES (
        v_producer_scope,v_message_id,'integration_event',p_contract_name,'1',
        'Monitoring',NULL,'tenant',p_tenant_id,p_subject_type,p_subject_id,
        p_occurred_at,NULL,NULL,NULL,NULL,v_correlation_id,v_causation_id,
        'confidential_tenant','jsonb-text-utf8@1',v_payload_bytes,
        'monitoring-invalidation-equivalence','1','canonical-jsonb-envelope-payload',
        NULL,v_equivalence_bytes
    )
    ON CONFLICT (producer_message_scope,message_id) DO NOTHING
    RETURNING outbox_record_id INTO v_outbox_id;

    IF v_outbox_id IS NULL THEN
        SELECT * INTO v_existing
          FROM system.async_outbox_message
         WHERE producer_message_scope=v_producer_scope
           AND message_id=v_message_id;

        IF NOT FOUND
           OR v_existing.message_class IS DISTINCT FROM 'integration_event'
           OR v_existing.contract_name IS DISTINCT FROM p_contract_name
           OR v_existing.contract_version IS DISTINCT FROM '1'
           OR v_existing.producer IS DISTINCT FROM 'Monitoring'
           OR v_existing.producer_generation IS NOT NULL
           OR v_existing.scope_class IS DISTINCT FROM 'tenant'
           OR v_existing.tenant_id IS DISTINCT FROM p_tenant_id
           OR v_existing.subject_type IS DISTINCT FROM p_subject_type
           OR v_existing.subject_id IS DISTINCT FROM p_subject_id
           OR v_existing.occurred_at IS DISTINCT FROM p_occurred_at
           OR v_existing.created_at IS NOT NULL
           OR v_existing.operation_id IS NOT NULL
           OR v_existing.not_before IS NOT NULL
           OR v_existing.deadline IS NOT NULL
           OR v_existing.correlation_id IS DISTINCT FROM v_correlation_id
           OR v_existing.causation_id IS DISTINCT FROM v_causation_id
           OR v_existing.data_classification IS DISTINCT FROM 'confidential_tenant'
           OR v_existing.serialization_profile_id IS DISTINCT FROM 'jsonb-text-utf8@1'
           OR v_existing.encoded_payload IS DISTINCT FROM v_payload_bytes
           OR v_existing.comparison_profile_id IS DISTINCT FROM 'monitoring-invalidation-equivalence'
           OR v_existing.comparison_profile_version IS DISTINCT FROM '1'
           OR v_existing.comparison_evidence_form IS DISTINCT FROM 'canonical-jsonb-envelope-payload'
           OR v_existing.comparison_verifier_generation IS NOT NULL
           OR v_existing.comparison_evidence IS DISTINCT FROM v_equivalence_bytes THEN
            RAISE EXCEPTION 'monitoring.publication_identity_conflict';
        END IF;
        v_outbox_id := v_existing.outbox_record_id;
    END IF;

    -- Dispatch bookkeeping is recoverable. The Wave 2 AFTER INSERT trigger normally
    -- creates this row atomically; this insert repairs missing restored bookkeeping
    -- without changing the immutable logical message or resetting existing state.
    INSERT INTO system.async_outbox_dispatch(outbox_record_id)
    VALUES (v_outbox_id)
    ON CONFLICT (outbox_record_id) DO NOTHING;

    RETURN v_outbox_id;
END;
$$;
ALTER FUNCTION monitoring.wave4_ensure_monitoring_invalidation(TEXT,TEXT,TEXT,TEXT,TEXT,TIMESTAMPTZ,JSONB)
    OWNER TO jlmirror_wave4_monitoring_publication_executor;
REVOKE ALL ON FUNCTION monitoring.wave4_ensure_monitoring_invalidation(TEXT,TEXT,TEXT,TEXT,TEXT,TIMESTAMPTZ,JSONB)
    FROM PUBLIC;

CREATE OR REPLACE FUNCTION monitoring.wave4_publish_problem_transition()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, monitoring, system
AS $$
BEGIN
    PERFORM monitoring.wave4_ensure_monitoring_invalidation(
        NEW.tenant_id,
        'monitoring.problem-state.changed',
        'monitoring_problem',
        NEW.problem_id,
        NEW.problem_transition_id,
        NEW.occurred_at,
        jsonb_build_object(
            'problem_id',NEW.problem_id,
            'monitoring_source_id',NEW.monitoring_source_id,
            'source_instance_generation',NEW.source_instance_generation,
            'monitoring_resource_id',NEW.monitoring_resource_id,
            'projection_revision',NEW.projection_revision,
            'problem_transition_id',NEW.problem_transition_id
        )
    );
    RETURN NEW;
END;
$$;
ALTER FUNCTION monitoring.wave4_publish_problem_transition()
    OWNER TO jlmirror_wave4_monitoring_publication_executor;
REVOKE ALL ON FUNCTION monitoring.wave4_publish_problem_transition() FROM PUBLIC;

CREATE OR REPLACE FUNCTION monitoring.wave4_publish_health_transition()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, monitoring, system
AS $$
BEGIN
    PERFORM monitoring.wave4_ensure_monitoring_invalidation(
        NEW.tenant_id,
        'monitoring.health-projection.changed',
        'monitoring_resource',
        NEW.monitoring_resource_id,
        NEW.health_transition_id,
        NEW.occurred_at,
        jsonb_build_object(
            'monitoring_source_id',NEW.monitoring_source_id,
            'source_instance_generation',NEW.source_instance_generation,
            'monitoring_resource_id',NEW.monitoring_resource_id,
            'projection_revision',NEW.projection_revision,
            'health_transition_id',NEW.health_transition_id
        )
    );
    RETURN NEW;
END;
$$;
ALTER FUNCTION monitoring.wave4_publish_health_transition()
    OWNER TO jlmirror_wave4_monitoring_publication_executor;
REVOKE ALL ON FUNCTION monitoring.wave4_publish_health_transition() FROM PUBLIC;

CREATE TRIGGER monitoring_problem_transition_outbox
AFTER INSERT ON monitoring.monitoring_problem_transition
FOR EACH ROW EXECUTE FUNCTION monitoring.wave4_publish_problem_transition();

CREATE TRIGGER health_projection_transition_outbox
AFTER INSERT ON monitoring.health_projection_transition
FOR EACH ROW EXECUTE FUNCTION monitoring.wave4_publish_health_transition();

CREATE OR REPLACE FUNCTION monitoring.recover_problem_state_publication(
    p_tenant_id TEXT,
    p_problem_transition_id TEXT
) RETURNS BIGINT
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, monitoring, system
AS $$
DECLARE
    v_transition monitoring.monitoring_problem_transition%ROWTYPE;
BEGIN
    IF p_tenant_id IS NULL OR p_tenant_id='' OR p_problem_transition_id IS NULL OR p_problem_transition_id='' THEN
        RAISE EXCEPTION 'monitoring.publication_invalid_recovery_input';
    END IF;
    PERFORM set_config('jlmirror.tenant_id',p_tenant_id,true);
    SELECT * INTO v_transition
      FROM monitoring.monitoring_problem_transition
     WHERE tenant_id=p_tenant_id
       AND problem_transition_id=p_problem_transition_id;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'monitoring.publication_problem_transition_not_found';
    END IF;
    RETURN monitoring.wave4_ensure_monitoring_invalidation(
        v_transition.tenant_id,
        'monitoring.problem-state.changed',
        'monitoring_problem',
        v_transition.problem_id,
        v_transition.problem_transition_id,
        v_transition.occurred_at,
        jsonb_build_object(
            'problem_id',v_transition.problem_id,
            'monitoring_source_id',v_transition.monitoring_source_id,
            'source_instance_generation',v_transition.source_instance_generation,
            'monitoring_resource_id',v_transition.monitoring_resource_id,
            'projection_revision',v_transition.projection_revision,
            'problem_transition_id',v_transition.problem_transition_id
        )
    );
END;
$$;
ALTER FUNCTION monitoring.recover_problem_state_publication(TEXT,TEXT)
    OWNER TO jlmirror_wave4_monitoring_publication_executor;
REVOKE ALL ON FUNCTION monitoring.recover_problem_state_publication(TEXT,TEXT) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION monitoring.recover_problem_state_publication(TEXT,TEXT)
    TO jlmirror_wave4_recovery_authority;

CREATE OR REPLACE FUNCTION monitoring.recover_health_projection_publication(
    p_tenant_id TEXT,
    p_health_transition_id TEXT
) RETURNS BIGINT
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, monitoring, system
AS $$
DECLARE
    v_transition monitoring.health_projection_transition%ROWTYPE;
BEGIN
    IF p_tenant_id IS NULL OR p_tenant_id='' OR p_health_transition_id IS NULL OR p_health_transition_id='' THEN
        RAISE EXCEPTION 'monitoring.publication_invalid_recovery_input';
    END IF;
    PERFORM set_config('jlmirror.tenant_id',p_tenant_id,true);
    SELECT * INTO v_transition
      FROM monitoring.health_projection_transition
     WHERE tenant_id=p_tenant_id
       AND health_transition_id=p_health_transition_id;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'monitoring.publication_health_transition_not_found';
    END IF;
    RETURN monitoring.wave4_ensure_monitoring_invalidation(
        v_transition.tenant_id,
        'monitoring.health-projection.changed',
        'monitoring_resource',
        v_transition.monitoring_resource_id,
        v_transition.health_transition_id,
        v_transition.occurred_at,
        jsonb_build_object(
            'monitoring_source_id',v_transition.monitoring_source_id,
            'source_instance_generation',v_transition.source_instance_generation,
            'monitoring_resource_id',v_transition.monitoring_resource_id,
            'projection_revision',v_transition.projection_revision,
            'health_transition_id',v_transition.health_transition_id
        )
    );
END;
$$;
ALTER FUNCTION monitoring.recover_health_projection_publication(TEXT,TEXT)
    OWNER TO jlmirror_wave4_monitoring_publication_executor;
REVOKE ALL ON FUNCTION monitoring.recover_health_projection_publication(TEXT,TEXT) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION monitoring.recover_health_projection_publication(TEXT,TEXT)
    TO jlmirror_wave4_recovery_authority;

-- A first-time CREATE FUNCTION can inherit named EXECUTE grants from the
-- installer role's ALTER DEFAULT PRIVILEGES. Preflight cannot see a function
-- that does not exist yet, so verify the effective installed ACL for every
-- privileged function before this transaction is allowed to commit.
DO $$
DECLARE
    v_executor_oid OID;
    v_recovery_oid OID;
    v_row RECORD;
    v_proc_oid OID;
BEGIN
    SELECT oid INTO v_executor_oid
      FROM pg_roles
     WHERE rolname='jlmirror_wave4_monitoring_publication_executor';
    SELECT oid INTO v_recovery_oid
      FROM pg_roles
     WHERE rolname='jlmirror_wave4_recovery_authority';

    FOR v_row IN
        SELECT *
          FROM (VALUES
              ('monitoring.wave4_ensure_monitoring_invalidation(text,text,text,text,text,timestamptz,jsonb)', false),
              ('monitoring.wave4_publish_problem_transition()', false),
              ('monitoring.wave4_publish_health_transition()', false),
              ('monitoring.recover_problem_state_publication(text,text)', true),
              ('monitoring.recover_health_projection_publication(text,text)', true)
          ) AS guarded(signature, allow_recovery_authority)
    LOOP
        v_proc_oid := to_regprocedure(v_row.signature);
        IF v_proc_oid IS NULL THEN
            RAISE EXCEPTION 'monitoring.publication_installed_function_missing:%', v_row.signature;
        END IF;

        IF EXISTS (
            SELECT 1
              FROM pg_proc p
             WHERE p.oid=v_proc_oid
               AND (p.proowner<>v_executor_oid OR NOT p.prosecdef)
        ) THEN
            RAISE EXCEPTION 'monitoring.publication_installed_function_definition_unsafe:%', v_row.signature;
        END IF;

        IF EXISTS (
            SELECT 1
              FROM pg_proc p,
                   LATERAL aclexplode(COALESCE(p.proacl, acldefault('f', p.proowner))) a
             WHERE p.oid=v_proc_oid
               AND a.privilege_type='EXECUTE'
               AND (
                    a.grantee=0
                    OR (
                        a.grantee<>p.proowner
                        AND (
                            NOT v_row.allow_recovery_authority
                            OR a.grantee<>v_recovery_oid
                            OR a.is_grantable
                        )
                    )
               )
        ) THEN
            RAISE EXCEPTION 'monitoring.publication_installed_function_acl_unsafe:%', v_row.signature;
        END IF;
    END LOOP;
END;
$$;

COMMIT;