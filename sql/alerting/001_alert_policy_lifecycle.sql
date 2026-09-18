-- G7 Alert Policy + Lifecycle golden path.
-- Authority: g7.alert-policy-lifecycle@1.
-- Current Monitoring truth is reread before every effectful decision.

BEGIN;

CREATE SCHEMA IF NOT EXISTS alerting;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='jlmirror_g7_alerting_executor') THEN
        CREATE ROLE jlmirror_g7_alerting_executor
            NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='jlmirror_g7_alerting_invoker') THEN
        CREATE ROLE jlmirror_g7_alerting_invoker
            NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS;
    END IF;
END;
$$;

-- The executor is a dedicated NOLOGIN capability owner. Before any G7
-- storage authority is granted, reject unsafe attributes, memberships or
-- unrelated persistent objects already owned by that role.
DO $
DECLARE
    v_executor_oid OID;
    v_unexpected TEXT;
BEGIN
    SELECT oid INTO v_executor_oid
      FROM pg_roles
     WHERE rolname='jlmirror_g7_alerting_executor';

    IF EXISTS (
        SELECT 1
          FROM pg_roles
         WHERE oid=v_executor_oid
           AND (
               rolcanlogin OR rolsuper OR rolcreatedb OR rolcreaterole
               OR rolinherit OR rolreplication OR rolbypassrls
           )
    ) THEN
        RAISE EXCEPTION 'g7.executor_unsafe_attributes';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM pg_auth_members
         WHERE roleid=v_executor_oid OR member=v_executor_oid
    ) THEN
        RAISE EXCEPTION 'g7.executor_unsafe_membership';
    END IF;

    WITH allowed_proc_oids AS (
        SELECT to_regprocedure(signature) AS proc_oid
          FROM (VALUES
              ('alerting.g7_create_policy_version(text,text,bigint,text,text,text[],text,text)'),
              ('alerting.g7_set_effective_policy_version(text,text,bigint,boolean)'),
              ('alerting.g7_apply_current_evaluation(text,text,bigint,text)'),
              ('alerting.g7_list_alerts(text,integer)'),
              ('alerting.g7_get_alert(text,text)')
          ) AS allowed(signature)
    )
    SELECT format(
               'class=%s,objid=%s,dbid=%s',
               d.classid::regclass::TEXT,d.objid,d.dbid
           )
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
        RAISE EXCEPTION 'g7.executor_unexpected_owned_object:%',v_unexpected;
    END IF;
END;
$;

GRANT USAGE ON SCHEMA alerting, monitoring TO jlmirror_g7_alerting_executor;
GRANT USAGE ON SCHEMA alerting TO jlmirror_g7_alerting_invoker;
REVOKE CREATE ON SCHEMA alerting, monitoring FROM jlmirror_g7_alerting_executor, jlmirror_g7_alerting_invoker;

CREATE TABLE alerting.alert_policy (
    tenant_id TEXT NOT NULL,
    policy_id TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT transaction_timestamp(),
    PRIMARY KEY (tenant_id, policy_id),
    CHECK (tenant_id <> '' AND length(tenant_id) <= 512),
    CHECK (policy_id <> '' AND length(policy_id) <= 512)
);

CREATE TABLE alerting.alert_policy_version (
    tenant_id TEXT NOT NULL,
    policy_id TEXT NOT NULL,
    policy_version BIGINT NOT NULL CHECK (policy_version > 0),
    source_kind TEXT NOT NULL CHECK (source_kind IN ('monitoring_problem','monitoring_health_projection')),
    problem_min_severity TEXT NULL
        CHECK (problem_min_severity IS NULL OR problem_min_severity IN ('unknown','informational','warning','degraded','critical')),
    health_classes TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],
    monitoring_source_id TEXT NULL,
    monitoring_resource_id TEXT NULL,
    content_hash TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT transaction_timestamp(),
    superseded_at TIMESTAMPTZ NULL,
    PRIMARY KEY (tenant_id, policy_id, policy_version),
    FOREIGN KEY (tenant_id, policy_id)
        REFERENCES alerting.alert_policy(tenant_id, policy_id),
    CHECK (content_hash <> '' AND length(content_hash) <= 128),
    CHECK (
        (source_kind='monitoring_problem'
         AND problem_min_severity IS NOT NULL
         AND cardinality(health_classes)=0)
        OR
        (source_kind='monitoring_health_projection'
         AND problem_min_severity IS NULL
         AND cardinality(health_classes)>0
         AND health_classes <@ ARRAY['unknown','healthy','degraded','unhealthy']::TEXT[])
    ),
    CHECK (monitoring_source_id IS NULL OR (monitoring_source_id <> '' AND length(monitoring_source_id) <= 512)),
    CHECK (monitoring_resource_id IS NULL OR (monitoring_resource_id <> '' AND length(monitoring_resource_id) <= 512))
);

CREATE TABLE alerting.alert_policy_effective_version (
    tenant_id TEXT NOT NULL,
    policy_id TEXT NOT NULL,
    policy_version BIGINT NOT NULL,
    enabled BOOLEAN NOT NULL,
    effective_at TIMESTAMPTZ NOT NULL DEFAULT transaction_timestamp(),
    PRIMARY KEY (tenant_id, policy_id),
    FOREIGN KEY (tenant_id, policy_id, policy_version)
        REFERENCES alerting.alert_policy_version(tenant_id, policy_id, policy_version)
);

CREATE TABLE alerting.alert (
    tenant_id TEXT NOT NULL,
    alert_id TEXT NOT NULL,
    policy_id TEXT NOT NULL,
    policy_version BIGINT NOT NULL,
    source_kind TEXT NOT NULL CHECK (source_kind IN ('monitoring_problem','monitoring_health_projection')),
    source_subject_id TEXT NOT NULL,
    monitoring_source_id TEXT NOT NULL,
    monitoring_resource_id TEXT NOT NULL,
    source_instance_generation TEXT NOT NULL,
    source_occurrence_revision BIGINT NOT NULL CHECK (source_occurrence_revision > 0),
    current_source_revision BIGINT NOT NULL CHECK (current_source_revision >= source_occurrence_revision),
    lifecycle_state TEXT NOT NULL CHECK (lifecycle_state IN ('active','resolved')),
    source_evidence_summary JSONB NOT NULL,
    opened_at TIMESTAMPTZ NOT NULL DEFAULT transaction_timestamp(),
    resolved_at TIMESTAMPTZ NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT transaction_timestamp(),
    PRIMARY KEY (tenant_id, alert_id),
    FOREIGN KEY (tenant_id, policy_id, policy_version)
        REFERENCES alerting.alert_policy_version(tenant_id, policy_id, policy_version),
    CHECK (alert_id <> '' AND length(alert_id) <= 256),
    CHECK (source_subject_id <> '' AND length(source_subject_id) <= 512),
    CHECK (monitoring_source_id <> '' AND length(monitoring_source_id) <= 512),
    CHECK (monitoring_resource_id <> '' AND length(monitoring_resource_id) <= 512),
    CHECK (source_instance_generation <> '' AND length(source_instance_generation) <= 512),
    CHECK (jsonb_typeof(source_evidence_summary)='object'),
    CHECK (
        (lifecycle_state='active' AND resolved_at IS NULL)
        OR (lifecycle_state='resolved' AND resolved_at IS NOT NULL)
    )
);

CREATE UNIQUE INDEX alert_one_active_occurrence
ON alerting.alert(
    tenant_id,policy_id,source_kind,source_subject_id
)
WHERE lifecycle_state='active';

CREATE TABLE alerting.alert_transition (
    tenant_id TEXT NOT NULL,
    alert_transition_id TEXT NOT NULL,
    alert_id TEXT NOT NULL,
    policy_id TEXT NOT NULL,
    policy_version BIGINT NOT NULL,
    from_lifecycle_state TEXT NULL CHECK (from_lifecycle_state IS NULL OR from_lifecycle_state='active'),
    to_lifecycle_state TEXT NOT NULL CHECK (to_lifecycle_state IN ('active','resolved')),
    source_revision BIGINT NOT NULL CHECK (source_revision > 0),
    source_evidence_summary JSONB NOT NULL,
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT transaction_timestamp(),
    PRIMARY KEY (tenant_id, alert_transition_id),
    FOREIGN KEY (tenant_id, alert_id)
        REFERENCES alerting.alert(tenant_id, alert_id),
    FOREIGN KEY (tenant_id, policy_id, policy_version)
        REFERENCES alerting.alert_policy_version(tenant_id, policy_id, policy_version),
    CHECK (
        (from_lifecycle_state IS NULL AND to_lifecycle_state='active')
        OR (from_lifecycle_state='active' AND to_lifecycle_state='resolved')
    ),
    CHECK (jsonb_typeof(source_evidence_summary)='object')
);

CREATE TABLE alerting.alert_decision (
    tenant_id TEXT NOT NULL,
    decision_id TEXT NOT NULL,
    decision_hash TEXT NOT NULL,
    policy_id TEXT NOT NULL,
    policy_version BIGINT NOT NULL,
    source_kind TEXT NOT NULL CHECK (source_kind IN ('monitoring_problem','monitoring_health_projection')),
    source_subject_id TEXT NOT NULL,
    source_revision BIGINT NOT NULL CHECK (source_revision > 0),
    effect_kind TEXT NOT NULL CHECK (effect_kind IN ('create','resolve')),
    alert_id TEXT NOT NULL,
    decided_at TIMESTAMPTZ NOT NULL DEFAULT transaction_timestamp(),
    PRIMARY KEY (tenant_id, decision_id),
    FOREIGN KEY (tenant_id, alert_id)
        REFERENCES alerting.alert(tenant_id, alert_id),
    FOREIGN KEY (tenant_id, policy_id, policy_version)
        REFERENCES alerting.alert_policy_version(tenant_id, policy_id, policy_version),
    CHECK (decision_id <> '' AND length(decision_id) <= 256),
    CHECK (decision_hash <> '' AND length(decision_hash) <= 128)
);

ALTER TABLE alerting.alert_policy ENABLE ROW LEVEL SECURITY;
ALTER TABLE alerting.alert_policy FORCE ROW LEVEL SECURITY;
ALTER TABLE alerting.alert_policy_version ENABLE ROW LEVEL SECURITY;
ALTER TABLE alerting.alert_policy_version FORCE ROW LEVEL SECURITY;
ALTER TABLE alerting.alert_policy_effective_version ENABLE ROW LEVEL SECURITY;
ALTER TABLE alerting.alert_policy_effective_version FORCE ROW LEVEL SECURITY;
ALTER TABLE alerting.alert ENABLE ROW LEVEL SECURITY;
ALTER TABLE alerting.alert FORCE ROW LEVEL SECURITY;
ALTER TABLE alerting.alert_transition ENABLE ROW LEVEL SECURITY;
ALTER TABLE alerting.alert_transition FORCE ROW LEVEL SECURITY;
ALTER TABLE alerting.alert_decision ENABLE ROW LEVEL SECURITY;
ALTER TABLE alerting.alert_decision FORCE ROW LEVEL SECURITY;

CREATE POLICY alert_policy_tenant_policy ON alerting.alert_policy
USING (tenant_id=NULLIF(current_setting('jlmirror.tenant_id',true),''))
WITH CHECK (tenant_id=NULLIF(current_setting('jlmirror.tenant_id',true),''));
CREATE POLICY alert_policy_version_tenant_policy ON alerting.alert_policy_version
USING (tenant_id=NULLIF(current_setting('jlmirror.tenant_id',true),''))
WITH CHECK (tenant_id=NULLIF(current_setting('jlmirror.tenant_id',true),''));
CREATE POLICY alert_policy_effective_version_tenant_policy ON alerting.alert_policy_effective_version
USING (tenant_id=NULLIF(current_setting('jlmirror.tenant_id',true),''))
WITH CHECK (tenant_id=NULLIF(current_setting('jlmirror.tenant_id',true),''));
CREATE POLICY alert_tenant_policy ON alerting.alert
USING (tenant_id=NULLIF(current_setting('jlmirror.tenant_id',true),''))
WITH CHECK (tenant_id=NULLIF(current_setting('jlmirror.tenant_id',true),''));
CREATE POLICY alert_transition_tenant_policy ON alerting.alert_transition
USING (tenant_id=NULLIF(current_setting('jlmirror.tenant_id',true),''))
WITH CHECK (tenant_id=NULLIF(current_setting('jlmirror.tenant_id',true),''));
CREATE POLICY alert_decision_tenant_policy ON alerting.alert_decision
USING (tenant_id=NULLIF(current_setting('jlmirror.tenant_id',true),''))
WITH CHECK (tenant_id=NULLIF(current_setting('jlmirror.tenant_id',true),''));

REVOKE ALL ON
    alerting.alert_policy,
    alerting.alert_policy_version,
    alerting.alert_policy_effective_version,
    alerting.alert,
    alerting.alert_transition,
    alerting.alert_decision
FROM PUBLIC, jlmirror_g7_alerting_invoker;

GRANT SELECT, INSERT ON alerting.alert_policy TO jlmirror_g7_alerting_executor;
GRANT SELECT, INSERT, UPDATE ON alerting.alert_policy_version TO jlmirror_g7_alerting_executor;
GRANT SELECT, INSERT, UPDATE ON alerting.alert_policy_effective_version TO jlmirror_g7_alerting_executor;
GRANT SELECT, INSERT, UPDATE ON alerting.alert TO jlmirror_g7_alerting_executor;
GRANT SELECT, INSERT ON alerting.alert_transition, alerting.alert_decision TO jlmirror_g7_alerting_executor;
GRANT SELECT ON
    monitoring.monitoring_source,
    monitoring.monitoring_problem,
    monitoring.health_projection
TO jlmirror_g7_alerting_executor;

CREATE OR REPLACE FUNCTION alerting.g7_reject_immutable_row_mutation()
RETURNS trigger
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path=pg_catalog,alerting
AS $$
BEGIN
    RAISE EXCEPTION 'g7.immutable_row';
END;
$$;

CREATE TRIGGER alert_policy_immutable
BEFORE UPDATE OR DELETE ON alerting.alert_policy
FOR EACH ROW EXECUTE FUNCTION alerting.g7_reject_immutable_row_mutation();

CREATE TRIGGER alert_transition_immutable
BEFORE UPDATE OR DELETE ON alerting.alert_transition
FOR EACH ROW EXECUTE FUNCTION alerting.g7_reject_immutable_row_mutation();

CREATE TRIGGER alert_decision_immutable
BEFORE UPDATE OR DELETE ON alerting.alert_decision
FOR EACH ROW EXECUTE FUNCTION alerting.g7_reject_immutable_row_mutation();

CREATE OR REPLACE FUNCTION alerting.g7_guard_policy_version_mutation()
RETURNS trigger
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path=pg_catalog,alerting
AS $$
BEGIN
    IF TG_OP='DELETE' THEN
        RAISE EXCEPTION 'g7.policy_version_delete_forbidden';
    END IF;
    IF NEW.tenant_id IS DISTINCT FROM OLD.tenant_id
       OR NEW.policy_id IS DISTINCT FROM OLD.policy_id
       OR NEW.policy_version IS DISTINCT FROM OLD.policy_version
       OR NEW.source_kind IS DISTINCT FROM OLD.source_kind
       OR NEW.problem_min_severity IS DISTINCT FROM OLD.problem_min_severity
       OR NEW.health_classes IS DISTINCT FROM OLD.health_classes
       OR NEW.monitoring_source_id IS DISTINCT FROM OLD.monitoring_source_id
       OR NEW.monitoring_resource_id IS DISTINCT FROM OLD.monitoring_resource_id
       OR NEW.content_hash IS DISTINCT FROM OLD.content_hash
       OR NEW.created_at IS DISTINCT FROM OLD.created_at THEN
        RAISE EXCEPTION 'g7.policy_version_content_immutable';
    END IF;
    IF OLD.superseded_at IS NOT NULL
       OR NEW.superseded_at IS NULL
       OR NEW.superseded_at < OLD.created_at THEN
        RAISE EXCEPTION 'g7.policy_version_supersession_invalid';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER alert_policy_version_guard
BEFORE UPDATE OR DELETE ON alerting.alert_policy_version
FOR EACH ROW EXECUTE FUNCTION alerting.g7_guard_policy_version_mutation();

CREATE OR REPLACE FUNCTION alerting.g7_guard_alert_mutation()
RETURNS trigger
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path=pg_catalog,alerting
AS $$
BEGIN
    IF TG_OP='DELETE' THEN
        RAISE EXCEPTION 'g7.alert_delete_forbidden';
    END IF;
    IF NEW.tenant_id IS DISTINCT FROM OLD.tenant_id
       OR NEW.alert_id IS DISTINCT FROM OLD.alert_id
       OR NEW.policy_id IS DISTINCT FROM OLD.policy_id
       OR NEW.policy_version IS DISTINCT FROM OLD.policy_version
       OR NEW.source_kind IS DISTINCT FROM OLD.source_kind
       OR NEW.source_subject_id IS DISTINCT FROM OLD.source_subject_id
       OR NEW.monitoring_source_id IS DISTINCT FROM OLD.monitoring_source_id
       OR NEW.monitoring_resource_id IS DISTINCT FROM OLD.monitoring_resource_id
       OR NEW.source_instance_generation IS DISTINCT FROM OLD.source_instance_generation
       OR NEW.source_occurrence_revision IS DISTINCT FROM OLD.source_occurrence_revision
       OR NEW.opened_at IS DISTINCT FROM OLD.opened_at THEN
        RAISE EXCEPTION 'g7.alert_identity_immutable';
    END IF;
    IF OLD.lifecycle_state='resolved' THEN
        RAISE EXCEPTION 'g7.resolved_alert_terminal';
    END IF;
    IF NEW.lifecycle_state<>'resolved'
       OR NEW.resolved_at IS NULL
       OR NEW.current_source_revision < OLD.current_source_revision THEN
        RAISE EXCEPTION 'g7.alert_transition_invalid';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER alert_projection_guard
BEFORE UPDATE OR DELETE ON alerting.alert
FOR EACH ROW EXECUTE FUNCTION alerting.g7_guard_alert_mutation();

-- CREATE OR REPLACE preserves function OIDs and ACLs. Reject poisoned
-- canonical entry points before replacing their bodies or elevating them under
-- the dedicated executor.
DO $
DECLARE
    v_executor_oid OID;
    v_invoker_oid OID;
    v_row RECORD;
    v_proc_oid OID;
    v_dependency TEXT;
BEGIN
    SELECT oid INTO v_executor_oid
      FROM pg_roles
     WHERE rolname='jlmirror_g7_alerting_executor';
    SELECT oid INTO v_invoker_oid
      FROM pg_roles
     WHERE rolname='jlmirror_g7_alerting_invoker';

    FOR v_row IN
        SELECT signature
          FROM (VALUES
              ('alerting.g7_create_policy_version(text,text,bigint,text,text,text[],text,text)'),
              ('alerting.g7_set_effective_policy_version(text,text,bigint,boolean)'),
              ('alerting.g7_apply_current_evaluation(text,text,bigint,text)'),
              ('alerting.g7_list_alerts(text,integer)'),
              ('alerting.g7_get_alert(text,text)')
          ) AS guarded(signature)
    LOOP
        v_proc_oid := to_regprocedure(v_row.signature);
        IF v_proc_oid IS NULL THEN
            CONTINUE;
        END IF;

        IF EXISTS (
            SELECT 1
              FROM pg_proc p,
                   LATERAL aclexplode(
                       COALESCE(p.proacl,acldefault('f',p.proowner))
                   ) a
             WHERE p.oid=v_proc_oid
               AND a.privilege_type='EXECUTE'
               AND (
                   a.grantee=0
                   OR (
                       a.grantee<>p.proowner
                       AND (
                           a.grantee<>v_invoker_oid
                           OR a.is_grantable
                       )
                   )
               )
        ) THEN
            RAISE EXCEPTION 'g7.existing_function_acl_unsafe:%',v_row.signature;
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
            RAISE EXCEPTION 'g7.existing_function_dependency_unsafe:%:%',
                v_row.signature,v_dependency;
        END IF;
    END LOOP;
END;
$;

CREATE OR REPLACE FUNCTION alerting.g7_create_policy_version(
    p_tenant_id TEXT,
    p_policy_id TEXT,
    p_policy_version BIGINT,
    p_source_kind TEXT,
    p_problem_min_severity TEXT,
    p_health_classes TEXT[],
    p_monitoring_source_id TEXT,
    p_monitoring_resource_id TEXT
) RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path=pg_catalog,alerting
AS $$
DECLARE
    v_health TEXT[];
    v_hash TEXT;
    v_existing alerting.alert_policy_version%ROWTYPE;
BEGIN
    IF p_tenant_id IS NULL OR p_tenant_id='' OR length(p_tenant_id)>512
       OR p_policy_id IS NULL OR p_policy_id='' OR length(p_policy_id)>512
       OR p_policy_version IS NULL OR p_policy_version<=0
       OR p_source_kind NOT IN ('monitoring_problem','monitoring_health_projection') THEN
        RAISE EXCEPTION 'g7.policy_identity_invalid';
    END IF;

    SELECT COALESCE(array_agg(DISTINCT x ORDER BY x),ARRAY[]::TEXT[])
      INTO v_health
      FROM unnest(COALESCE(p_health_classes,ARRAY[]::TEXT[])) AS h(x);

    IF p_source_kind='monitoring_problem' THEN
        IF p_problem_min_severity NOT IN ('unknown','informational','warning','degraded','critical')
           OR cardinality(v_health)<>0 THEN
            RAISE EXCEPTION 'g7.problem_policy_invalid';
        END IF;
    ELSE
        IF p_problem_min_severity IS NOT NULL
           OR cardinality(v_health)=0
           OR NOT (v_health <@ ARRAY['unknown','healthy','degraded','unhealthy']::TEXT[]) THEN
            RAISE EXCEPTION 'g7.health_policy_invalid';
        END IF;
    END IF;

    PERFORM set_config('jlmirror.tenant_id',p_tenant_id,true);

    v_hash := md5(jsonb_build_object(
        'source_kind',p_source_kind,
        'problem_min_severity',p_problem_min_severity,
        'health_classes',to_jsonb(v_health),
        'monitoring_source_id',p_monitoring_source_id,
        'monitoring_resource_id',p_monitoring_resource_id
    )::TEXT);

    INSERT INTO alerting.alert_policy(tenant_id,policy_id)
    VALUES (p_tenant_id,p_policy_id)
    ON CONFLICT (tenant_id,policy_id) DO NOTHING;

    SELECT * INTO v_existing
      FROM alerting.alert_policy_version
     WHERE tenant_id=p_tenant_id
       AND policy_id=p_policy_id
       AND policy_version=p_policy_version;

    IF FOUND THEN
        IF v_existing.content_hash IS DISTINCT FROM v_hash
           OR v_existing.source_kind IS DISTINCT FROM p_source_kind
           OR v_existing.problem_min_severity IS DISTINCT FROM p_problem_min_severity
           OR v_existing.health_classes IS DISTINCT FROM v_health
           OR v_existing.monitoring_source_id IS DISTINCT FROM p_monitoring_source_id
           OR v_existing.monitoring_resource_id IS DISTINCT FROM p_monitoring_resource_id THEN
            RAISE EXCEPTION 'g7.policy_version_equivalence_conflict';
        END IF;
        RETURN jsonb_build_object(
            'policy_id',v_existing.policy_id,
            'policy_version',v_existing.policy_version,
            'content_hash',v_existing.content_hash,
            'duplicate',true
        );
    END IF;

    INSERT INTO alerting.alert_policy_version(
        tenant_id,policy_id,policy_version,source_kind,
        problem_min_severity,health_classes,
        monitoring_source_id,monitoring_resource_id,content_hash
    ) VALUES (
        p_tenant_id,p_policy_id,p_policy_version,p_source_kind,
        p_problem_min_severity,v_health,
        p_monitoring_source_id,p_monitoring_resource_id,v_hash
    );

    RETURN jsonb_build_object(
        'policy_id',p_policy_id,
        'policy_version',p_policy_version,
        'content_hash',v_hash,
        'duplicate',false
    );
END;
$$;

CREATE OR REPLACE FUNCTION alerting.g7_set_effective_policy_version(
    p_tenant_id TEXT,
    p_policy_id TEXT,
    p_policy_version BIGINT,
    p_enabled BOOLEAN
) RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path=pg_catalog,alerting
AS $$
DECLARE
    v_old BIGINT;
BEGIN
    IF p_tenant_id IS NULL OR p_tenant_id=''
       OR p_policy_id IS NULL OR p_policy_id=''
       OR p_policy_version IS NULL OR p_policy_version<=0
       OR p_enabled IS NULL THEN
        RAISE EXCEPTION 'g7.policy_effective_input_invalid';
    END IF;

    PERFORM set_config('jlmirror.tenant_id',p_tenant_id,true);
    PERFORM 1 FROM alerting.alert_policy_version
     WHERE tenant_id=p_tenant_id
       AND policy_id=p_policy_id
       AND policy_version=p_policy_version
       AND superseded_at IS NULL;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'g7.policy_version_missing_or_superseded';
    END IF;

    SELECT policy_version INTO v_old
      FROM alerting.alert_policy_effective_version
     WHERE tenant_id=p_tenant_id AND policy_id=p_policy_id
     FOR UPDATE;

    IF FOUND AND v_old<>p_policy_version THEN
        UPDATE alerting.alert_policy_version
           SET superseded_at=COALESCE(superseded_at,transaction_timestamp())
         WHERE tenant_id=p_tenant_id
           AND policy_id=p_policy_id
           AND policy_version=v_old
           AND superseded_at IS NULL;
    END IF;

    INSERT INTO alerting.alert_policy_effective_version(
        tenant_id,policy_id,policy_version,enabled,effective_at
    ) VALUES (
        p_tenant_id,p_policy_id,p_policy_version,p_enabled,transaction_timestamp()
    )
    ON CONFLICT (tenant_id,policy_id)
    DO UPDATE SET
        policy_version=EXCLUDED.policy_version,
        enabled=EXCLUDED.enabled,
        effective_at=EXCLUDED.effective_at;

    RETURN jsonb_build_object(
        'policy_id',p_policy_id,
        'policy_version',p_policy_version,
        'enabled',p_enabled
    );
END;
$$;

CREATE OR REPLACE FUNCTION alerting.g7_apply_current_evaluation(
    p_tenant_id TEXT,
    p_policy_id TEXT,
    p_policy_version BIGINT,
    p_source_subject_id TEXT
) RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path=pg_catalog,alerting,monitoring
AS $$
DECLARE
    v_policy alerting.alert_policy_version%ROWTYPE;
    v_effective BOOLEAN := false;
    v_source_generation TEXT;
    v_source_evidence TEXT;
    v_monitoring_source_id TEXT;
    v_monitoring_resource_id TEXT;
    v_generation TEXT;
    v_projection_evidence TEXT;
    v_revision BIGINT;
    v_match BOOLEAN := false;
    v_summary JSONB;
    v_problem_state TEXT;
    v_severity TEXT;
    v_health TEXT;
    v_active alerting.alert%ROWTYPE;
    v_decision_id TEXT;
    v_decision_hash TEXT;
    v_alert_id TEXT;
    v_transition_id TEXT;
    v_existing alerting.alert_decision%ROWTYPE;
BEGIN
    IF p_tenant_id IS NULL OR p_tenant_id=''
       OR p_policy_id IS NULL OR p_policy_id=''
       OR p_policy_version IS NULL OR p_policy_version<=0
       OR p_source_subject_id IS NULL OR p_source_subject_id='' THEN
        RAISE EXCEPTION 'g7.evaluation_input_invalid';
    END IF;

    PERFORM set_config('jlmirror.tenant_id',p_tenant_id,true);
    PERFORM pg_advisory_xact_lock(hashtextextended(
        p_tenant_id || chr(31) || p_policy_id || chr(31) || p_policy_version::TEXT
        || chr(31) || p_source_subject_id,0
    ));

    SELECT * INTO v_policy
      FROM alerting.alert_policy_version
     WHERE tenant_id=p_tenant_id
       AND policy_id=p_policy_id
       AND policy_version=p_policy_version;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'g7.policy_version_missing';
    END IF;

    SELECT (e.policy_version=p_policy_version AND e.enabled)
      INTO v_effective
      FROM alerting.alert_policy_effective_version AS e
     WHERE e.tenant_id=p_tenant_id
       AND e.policy_id=p_policy_id;
    v_effective := COALESCE(v_effective,false);

    IF v_policy.source_kind='monitoring_problem' THEN
        SELECT p.monitoring_source_id,p.monitoring_resource_id,p.source_instance_generation,
               p.evidence_state,p.projection_revision,p.problem_state,p.severity_class,
               s.active_source_instance_generation,s.operational_evidence_state
          INTO v_monitoring_source_id,v_monitoring_resource_id,v_generation,
               v_projection_evidence,v_revision,v_problem_state,v_severity,
               v_source_generation,v_source_evidence
          FROM monitoring.monitoring_problem AS p
          JOIN monitoring.monitoring_source AS s
            ON s.tenant_id=p.tenant_id
           AND s.monitoring_source_id=p.monitoring_source_id
         WHERE p.tenant_id=p_tenant_id
           AND p.problem_id=p_source_subject_id;

        IF NOT FOUND THEN
            RETURN jsonb_build_object('effect','none','reason','current_owner_state_missing');
        END IF;

        v_match := (
            v_generation=v_source_generation
            AND v_source_evidence='current'
            AND v_projection_evidence='current'
            AND v_problem_state='active'
            AND CASE v_severity
                WHEN 'unknown' THEN 0
                WHEN 'informational' THEN 1
                WHEN 'warning' THEN 2
                WHEN 'degraded' THEN 3
                WHEN 'critical' THEN 4
                ELSE -1
            END >= CASE v_policy.problem_min_severity
                WHEN 'unknown' THEN 0
                WHEN 'informational' THEN 1
                WHEN 'warning' THEN 2
                WHEN 'degraded' THEN 3
                WHEN 'critical' THEN 4
                ELSE 99
            END
            AND (v_policy.monitoring_source_id IS NULL OR v_policy.monitoring_source_id=v_monitoring_source_id)
            AND (v_policy.monitoring_resource_id IS NULL OR v_policy.monitoring_resource_id=v_monitoring_resource_id)
        );

        v_summary := jsonb_build_object(
            'problem_id',p_source_subject_id,
            'problem_state',v_problem_state,
            'severity_class',v_severity,
            'projection_revision',v_revision,
            'evidence_state',v_projection_evidence
        );
    ELSE
        SELECT h.monitoring_source_id,h.monitoring_resource_id,h.source_instance_generation,
               h.evidence_state,h.projection_revision,h.health_class,
               s.active_source_instance_generation,s.operational_evidence_state
          INTO v_monitoring_source_id,v_monitoring_resource_id,v_generation,
               v_projection_evidence,v_revision,v_health,
               v_source_generation,v_source_evidence
          FROM monitoring.health_projection AS h
          JOIN monitoring.monitoring_source AS s
            ON s.tenant_id=h.tenant_id
           AND s.monitoring_source_id=h.monitoring_source_id
         WHERE h.tenant_id=p_tenant_id
           AND h.monitoring_resource_id=p_source_subject_id
           AND h.source_instance_generation=s.active_source_instance_generation;

        IF NOT FOUND THEN
            RETURN jsonb_build_object('effect','none','reason','current_owner_state_missing');
        END IF;

        v_match := (
            v_generation=v_source_generation
            AND v_source_evidence='current'
            AND v_projection_evidence='current'
            AND v_health=ANY(v_policy.health_classes)
            AND (v_policy.monitoring_source_id IS NULL OR v_policy.monitoring_source_id=v_monitoring_source_id)
            AND (v_policy.monitoring_resource_id IS NULL OR v_policy.monitoring_resource_id=v_monitoring_resource_id)
        );

        v_summary := jsonb_build_object(
            'monitoring_resource_id',p_source_subject_id,
            'health_class',v_health,
            'projection_revision',v_revision,
            'evidence_state',v_projection_evidence
        );
    END IF;

    IF v_generation IS DISTINCT FROM v_source_generation
       OR v_source_evidence IS DISTINCT FROM 'current'
       OR v_projection_evidence IS DISTINCT FROM 'current'
       OR v_revision IS NULL OR v_revision<=0 THEN
        RETURN jsonb_build_object('effect','none','reason','currentness_unproven');
    END IF;

    SELECT * INTO v_active
      FROM alerting.alert
     WHERE tenant_id=p_tenant_id
       AND policy_id=p_policy_id
       AND source_kind=v_policy.source_kind
       AND source_subject_id=p_source_subject_id
       AND lifecycle_state='active'
     FOR UPDATE;

    IF FOUND AND v_active.policy_version<>p_policy_version THEN
        RETURN jsonb_build_object(
            'effect','none',
            'reason','active_occurrence_owned_by_other_policy_version',
            'alert_id',v_active.alert_id,
            'owner_policy_version',v_active.policy_version,
            'source_revision',v_revision
        );
    END IF;

    v_decision_id := 'g7-decision:' || md5(
        p_tenant_id || chr(31) || p_policy_id || chr(31) || p_policy_version::TEXT
        || chr(31) || v_policy.source_kind || chr(31) || p_source_subject_id
        || chr(31) || v_revision::TEXT
    );

    SELECT * INTO v_existing
      FROM alerting.alert_decision
     WHERE tenant_id=p_tenant_id AND decision_id=v_decision_id;

    IF FOUND THEN
        v_decision_hash := CASE v_existing.effect_kind
            WHEN 'create' THEN md5(
                v_decision_id || chr(31) || v_policy.content_hash || chr(31) || 'create'
            )
            WHEN 'resolve' THEN md5(
                v_decision_id || chr(31) || v_policy.content_hash || chr(31)
                || 'resolve' || chr(31) || v_existing.alert_id
            )
            ELSE NULL
        END;
        IF v_decision_hash IS NULL
           OR v_existing.decision_hash IS DISTINCT FROM v_decision_hash
           OR v_existing.policy_id IS DISTINCT FROM p_policy_id
           OR v_existing.policy_version IS DISTINCT FROM p_policy_version
           OR v_existing.source_kind IS DISTINCT FROM v_policy.source_kind
           OR v_existing.source_subject_id IS DISTINCT FROM p_source_subject_id
           OR v_existing.source_revision IS DISTINCT FROM v_revision THEN
            RAISE EXCEPTION 'g7.decision_equivalence_conflict';
        END IF;
        RETURN jsonb_build_object(
            'effect',v_existing.effect_kind,
            'alert_id',v_existing.alert_id,
            'decision_id',v_existing.decision_id,
            'duplicate',true,
            'source_revision',v_existing.source_revision
        );
    END IF;

    IF v_active.alert_id IS NULL AND (NOT v_match OR NOT v_effective) THEN
        RETURN jsonb_build_object('effect','none','reason','no_effect_authority','source_revision',v_revision);
    END IF;

    IF v_active.alert_id IS NOT NULL AND v_match THEN
        RETURN jsonb_build_object(
            'effect','none',
            'reason','active_occurrence_still_matches',
            'alert_id',v_active.alert_id,
            'source_revision',v_revision
        );
    END IF;

    IF v_active.alert_id IS NOT NULL THEN
        v_alert_id := v_active.alert_id;
        v_decision_hash := md5(
            v_decision_id || chr(31) || v_policy.content_hash || chr(31)
            || 'resolve' || chr(31) || v_alert_id
        );
    ELSE
        v_decision_hash := md5(
            v_decision_id || chr(31) || v_policy.content_hash || chr(31) || 'create'
        );
        v_alert_id := 'g7-alert:' || md5(v_decision_id || chr(31) || v_policy.content_hash);
    END IF;

    IF v_active.alert_id IS NOT NULL THEN
        UPDATE alerting.alert
           SET lifecycle_state='resolved',
               resolved_at=transaction_timestamp(),
               current_source_revision=v_revision,
               source_evidence_summary=v_summary,
               updated_at=transaction_timestamp()
         WHERE tenant_id=p_tenant_id
           AND alert_id=v_active.alert_id;

        v_transition_id := 'g7-transition:' || md5(v_decision_id || chr(31) || 'resolved');
        INSERT INTO alerting.alert_transition(
            tenant_id,alert_transition_id,alert_id,policy_id,policy_version,
            from_lifecycle_state,to_lifecycle_state,source_revision,source_evidence_summary
        ) VALUES (
            p_tenant_id,v_transition_id,v_active.alert_id,p_policy_id,p_policy_version,
            'active','resolved',v_revision,v_summary
        );

        INSERT INTO alerting.alert_decision(
            tenant_id,decision_id,decision_hash,policy_id,policy_version,
            source_kind,source_subject_id,source_revision,effect_kind,alert_id
        ) VALUES (
            p_tenant_id,v_decision_id,v_decision_hash,p_policy_id,p_policy_version,
            v_policy.source_kind,p_source_subject_id,v_revision,'resolve',v_active.alert_id
        );

        RETURN jsonb_build_object(
            'effect','resolve','alert_id',v_active.alert_id,
            'decision_id',v_decision_id,'duplicate',false,'source_revision',v_revision
        );
    END IF;

    INSERT INTO alerting.alert(
        tenant_id,alert_id,policy_id,policy_version,source_kind,source_subject_id,
        monitoring_source_id,monitoring_resource_id,source_instance_generation,
        source_occurrence_revision,current_source_revision,lifecycle_state,source_evidence_summary
    ) VALUES (
        p_tenant_id,v_alert_id,p_policy_id,p_policy_version,v_policy.source_kind,p_source_subject_id,
        v_monitoring_source_id,v_monitoring_resource_id,v_generation,
        v_revision,v_revision,'active',v_summary
    );

    v_transition_id := 'g7-transition:' || md5(v_decision_id || chr(31) || 'active');
    INSERT INTO alerting.alert_transition(
        tenant_id,alert_transition_id,alert_id,policy_id,policy_version,
        from_lifecycle_state,to_lifecycle_state,source_revision,source_evidence_summary
    ) VALUES (
        p_tenant_id,v_transition_id,v_alert_id,p_policy_id,p_policy_version,
        NULL,'active',v_revision,v_summary
    );

    INSERT INTO alerting.alert_decision(
        tenant_id,decision_id,decision_hash,policy_id,policy_version,
        source_kind,source_subject_id,source_revision,effect_kind,alert_id
    ) VALUES (
        p_tenant_id,v_decision_id,v_decision_hash,p_policy_id,p_policy_version,
        v_policy.source_kind,p_source_subject_id,v_revision,'create',v_alert_id
    );

    RETURN jsonb_build_object(
        'effect','create','alert_id',v_alert_id,
        'decision_id',v_decision_id,'duplicate',false,'source_revision',v_revision
    );
END;
$$;

CREATE OR REPLACE FUNCTION alerting.g7_list_alerts(
    p_tenant_id TEXT,
    p_limit INTEGER DEFAULT 50
) RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path=pg_catalog,alerting
AS $$
DECLARE
    v_limit INTEGER;
    v_result JSONB;
BEGIN
    IF p_tenant_id IS NULL OR p_tenant_id='' THEN
        RAISE EXCEPTION 'g7.read_tenant_invalid';
    END IF;
    v_limit := LEAST(GREATEST(COALESCE(p_limit,50),1),100);
    PERFORM set_config('jlmirror.tenant_id',p_tenant_id,true);
    SELECT COALESCE(jsonb_agg(to_jsonb(x) ORDER BY x.opened_at DESC,x.alert_id),'[]'::jsonb)
      INTO v_result
      FROM (
        SELECT alert_id,lifecycle_state,source_kind,source_subject_id,
               policy_id,policy_version,opened_at,resolved_at,current_source_revision
          FROM alerting.alert
         WHERE tenant_id=p_tenant_id
         ORDER BY opened_at DESC,alert_id
         LIMIT v_limit
      ) AS x;
    RETURN v_result;
END;
$$;

CREATE OR REPLACE FUNCTION alerting.g7_get_alert(
    p_tenant_id TEXT,
    p_alert_id TEXT
) RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path=pg_catalog,alerting
AS $$
DECLARE
    v_alert JSONB;
    v_transitions JSONB;
BEGIN
    IF p_tenant_id IS NULL OR p_tenant_id=''
       OR p_alert_id IS NULL OR p_alert_id='' THEN
        RAISE EXCEPTION 'g7.read_identity_invalid';
    END IF;
    PERFORM set_config('jlmirror.tenant_id',p_tenant_id,true);
    SELECT to_jsonb(a) INTO v_alert
      FROM (
        SELECT alert_id,lifecycle_state,source_kind,source_subject_id,
               monitoring_source_id,monitoring_resource_id,
               policy_id,policy_version,source_occurrence_revision,
               current_source_revision,source_evidence_summary,
               opened_at,resolved_at
          FROM alerting.alert
         WHERE tenant_id=p_tenant_id AND alert_id=p_alert_id
      ) AS a;
    IF v_alert IS NULL THEN
        RETURN NULL;
    END IF;
    SELECT COALESCE(jsonb_agg(to_jsonb(t) ORDER BY t.occurred_at,t.alert_transition_id),'[]'::jsonb)
      INTO v_transitions
      FROM (
        SELECT alert_transition_id,from_lifecycle_state,to_lifecycle_state,
               source_revision,source_evidence_summary,occurred_at
          FROM alerting.alert_transition
         WHERE tenant_id=p_tenant_id AND alert_id=p_alert_id
      ) AS t;
    RETURN v_alert || jsonb_build_object('transitions',v_transitions);
END;
$$;

ALTER FUNCTION alerting.g7_create_policy_version(TEXT,TEXT,BIGINT,TEXT,TEXT,TEXT[],TEXT,TEXT)
OWNER TO jlmirror_g7_alerting_executor;
ALTER FUNCTION alerting.g7_set_effective_policy_version(TEXT,TEXT,BIGINT,BOOLEAN)
OWNER TO jlmirror_g7_alerting_executor;
ALTER FUNCTION alerting.g7_apply_current_evaluation(TEXT,TEXT,BIGINT,TEXT)
OWNER TO jlmirror_g7_alerting_executor;
ALTER FUNCTION alerting.g7_list_alerts(TEXT,INTEGER)
OWNER TO jlmirror_g7_alerting_executor;
ALTER FUNCTION alerting.g7_get_alert(TEXT,TEXT)
OWNER TO jlmirror_g7_alerting_executor;

REVOKE ALL ON FUNCTION alerting.g7_create_policy_version(TEXT,TEXT,BIGINT,TEXT,TEXT,TEXT[],TEXT,TEXT) FROM PUBLIC;
REVOKE ALL ON FUNCTION alerting.g7_set_effective_policy_version(TEXT,TEXT,BIGINT,BOOLEAN) FROM PUBLIC;
REVOKE ALL ON FUNCTION alerting.g7_apply_current_evaluation(TEXT,TEXT,BIGINT,TEXT) FROM PUBLIC;
REVOKE ALL ON FUNCTION alerting.g7_list_alerts(TEXT,INTEGER) FROM PUBLIC;
REVOKE ALL ON FUNCTION alerting.g7_get_alert(TEXT,TEXT) FROM PUBLIC;

GRANT EXECUTE ON FUNCTION alerting.g7_create_policy_version(TEXT,TEXT,BIGINT,TEXT,TEXT,TEXT[],TEXT,TEXT)
TO jlmirror_g7_alerting_invoker;
GRANT EXECUTE ON FUNCTION alerting.g7_set_effective_policy_version(TEXT,TEXT,BIGINT,BOOLEAN)
TO jlmirror_g7_alerting_invoker;
GRANT EXECUTE ON FUNCTION alerting.g7_apply_current_evaluation(TEXT,TEXT,BIGINT,TEXT)
TO jlmirror_g7_alerting_invoker;
GRANT EXECUTE ON FUNCTION alerting.g7_list_alerts(TEXT,INTEGER)
TO jlmirror_g7_alerting_invoker;
GRANT EXECUTE ON FUNCTION alerting.g7_get_alert(TEXT,TEXT)
TO jlmirror_g7_alerting_invoker;

-- Final transactional closure: every privileged entry point must be owned by
-- the exact executor, remain SECURITY DEFINER, expose no PUBLIC/named proxy
-- EXECUTE authority, and grant only non-delegable EXECUTE to the canonical
-- invoker. This also detects unsafe installer default function privileges on
-- first creation before the transaction can commit.
DO $
DECLARE
    v_executor_oid OID;
    v_invoker_oid OID;
    v_row RECORD;
    v_proc_oid OID;
BEGIN
    SELECT oid INTO v_executor_oid
      FROM pg_roles
     WHERE rolname='jlmirror_g7_alerting_executor';
    SELECT oid INTO v_invoker_oid
      FROM pg_roles
     WHERE rolname='jlmirror_g7_alerting_invoker';

    FOR v_row IN
        SELECT signature
          FROM (VALUES
              ('alerting.g7_create_policy_version(text,text,bigint,text,text,text[],text,text)'),
              ('alerting.g7_set_effective_policy_version(text,text,bigint,boolean)'),
              ('alerting.g7_apply_current_evaluation(text,text,bigint,text)'),
              ('alerting.g7_list_alerts(text,integer)'),
              ('alerting.g7_get_alert(text,text)')
          ) AS guarded(signature)
    LOOP
        v_proc_oid := to_regprocedure(v_row.signature);
        IF v_proc_oid IS NULL THEN
            RAISE EXCEPTION 'g7.installed_function_missing:%',v_row.signature;
        END IF;

        IF EXISTS (
            SELECT 1
              FROM pg_proc p
             WHERE p.oid=v_proc_oid
               AND (p.proowner<>v_executor_oid OR NOT p.prosecdef)
        ) THEN
            RAISE EXCEPTION 'g7.installed_function_definition_unsafe:%',
                v_row.signature;
        END IF;

        IF EXISTS (
            SELECT 1
              FROM pg_proc p,
                   LATERAL aclexplode(
                       COALESCE(p.proacl,acldefault('f',p.proowner))
                   ) a
             WHERE p.oid=v_proc_oid
               AND a.privilege_type='EXECUTE'
               AND (
                   a.grantee=0
                   OR (
                       a.grantee<>p.proowner
                       AND (
                           a.grantee<>v_invoker_oid
                           OR a.is_grantable
                       )
                   )
               )
        ) THEN
            RAISE EXCEPTION 'g7.installed_function_acl_unsafe:%',
                v_row.signature;
        END IF;

        IF NOT EXISTS (
            SELECT 1
              FROM pg_proc p,
                   LATERAL aclexplode(
                       COALESCE(p.proacl,acldefault('f',p.proowner))
                   ) a
             WHERE p.oid=v_proc_oid
               AND a.privilege_type='EXECUTE'
               AND a.grantee=v_invoker_oid
               AND NOT a.is_grantable
        ) THEN
            RAISE EXCEPTION 'g7.installed_invoker_execute_missing:%',
                v_row.signature;
        END IF;
    END LOOP;
END;
$;

COMMIT;
