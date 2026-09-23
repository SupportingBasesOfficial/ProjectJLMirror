-- G8 Human Operations golden path.
-- Authority: g8.human-operations@1.

BEGIN;

CREATE SCHEMA IF NOT EXISTS human_operations;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='jlmirror_g8_human_operations_executor') THEN
        CREATE ROLE jlmirror_g8_human_operations_executor
            NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='jlmirror_g8_human_operations_invoker') THEN
        CREATE ROLE jlmirror_g8_human_operations_invoker
            NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS;
    END IF;
END;
$$;

DO $$
DECLARE
    v_executor_oid OID;
    v_unexpected TEXT;
BEGIN
    SELECT oid INTO v_executor_oid
      FROM pg_roles
     WHERE rolname='jlmirror_g8_human_operations_executor';

    IF EXISTS (
        SELECT 1 FROM pg_roles
        WHERE oid=v_executor_oid
          AND (rolcanlogin OR rolsuper OR rolcreatedb OR rolcreaterole
               OR rolinherit OR rolreplication OR rolbypassrls)
    ) THEN
        RAISE EXCEPTION 'g8.executor_unsafe_attributes';
    END IF;

    IF EXISTS (
        SELECT 1 FROM pg_auth_members
        WHERE roleid=v_executor_oid OR member=v_executor_oid
    ) THEN
        RAISE EXCEPTION 'g8.executor_unsafe_membership';
    END IF;

    WITH allowed_proc_oids AS (
        SELECT to_regprocedure(signature) AS proc_oid
        FROM (VALUES
          ('human_operations.g8_validate_authority(text,text,jsonb)'),
          ('human_operations.g8_assign_resource_responsibility(text,text,text,text,text,text,text,jsonb)'),
          ('human_operations.g8_end_resource_responsibility(text,text,text,text,jsonb)'),
          ('human_operations.g8_assign_alert_action(text,text,text,text,text,text,jsonb)'),
          ('human_operations.g8_acknowledge_alert(text,text,text,text,text,jsonb)'),
          ('human_operations.g8_create_visibility_requirement(text,text,text,text,text,text,text,text,jsonb)'),
          ('human_operations.g8_record_visibility_receipt(text,text,text,text,jsonb,jsonb)'),
          ('human_operations.g8_alert_human_operations(text,text)'),
          ('human_operations.g8_resource_responsibilities(text,text)')
        ) AS allowed(signature)
    )
    SELECT format('class=%s,objid=%s,dbid=%s',d.classid::regclass::TEXT,d.objid,d.dbid)
      INTO v_unexpected
      FROM pg_shdepend d
     WHERE d.refclassid='pg_authid'::regclass
       AND d.refobjid=v_executor_oid
       AND d.deptype='o'
       AND NOT (
         d.classid='pg_proc'::regclass
         AND d.objid IN (SELECT proc_oid FROM allowed_proc_oids WHERE proc_oid IS NOT NULL)
       )
     ORDER BY d.dbid,d.classid,d.objid
     LIMIT 1;

    IF v_unexpected IS NOT NULL THEN
        RAISE EXCEPTION 'g8.executor_unexpected_owned_object:%',v_unexpected;
    END IF;
END;
$$;

GRANT USAGE ON SCHEMA human_operations, monitoring, alerting TO jlmirror_g8_human_operations_executor;
GRANT USAGE ON SCHEMA human_operations TO jlmirror_g8_human_operations_invoker;
REVOKE CREATE ON SCHEMA human_operations, monitoring, alerting
FROM jlmirror_g8_human_operations_executor, jlmirror_g8_human_operations_invoker;

CREATE TABLE human_operations.resource_responsibility_assignment (
    tenant_id TEXT NOT NULL,
    responsibility_assignment_id TEXT NOT NULL,
    monitoring_resource_id TEXT NOT NULL,
    principal_id TEXT NOT NULL,
    responsibility_role TEXT NOT NULL CHECK (
        responsibility_role IN ('technical_responsible','service_owner','operator','customer_responsible')
    ),
    assignment_source TEXT NOT NULL CHECK (assignment_source IN ('manual','configured')),
    logical_action_id TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    assigned_by_principal_id TEXT NOT NULL,
    authority_snapshot JSONB NOT NULL,
    effective_from TIMESTAMPTZ NOT NULL DEFAULT transaction_timestamp(),
    effective_until TIMESTAMPTZ NULL,
    ended_by_principal_id TEXT NULL,
    end_reason TEXT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT transaction_timestamp(),
    PRIMARY KEY (tenant_id,responsibility_assignment_id),
    UNIQUE (tenant_id,logical_action_id),
    FOREIGN KEY (tenant_id,monitoring_resource_id)
        REFERENCES monitoring.monitoring_resource(tenant_id,monitoring_resource_id),
    CHECK (tenant_id<>'' AND monitoring_resource_id<>'' AND principal_id<>''),
    CHECK (logical_action_id<>'' AND content_hash<>''),
    CHECK (jsonb_typeof(authority_snapshot)='object'),
    CHECK (
      (effective_until IS NULL AND ended_by_principal_id IS NULL AND end_reason IS NULL)
      OR
      (effective_until IS NOT NULL AND ended_by_principal_id IS NOT NULL AND end_reason IS NOT NULL)
    )
);

CREATE TABLE human_operations.alert_action_assignment (
    tenant_id TEXT NOT NULL,
    action_assignment_id TEXT NOT NULL,
    alert_id TEXT NOT NULL,
    owner_principal_id TEXT NOT NULL,
    action_kind TEXT NOT NULL CHECK (
        action_kind IN ('investigate_alert','acknowledge_alert','review_alert','customer_review_required')
    ),
    logical_action_id TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    assigned_by_principal_id TEXT NOT NULL,
    authority_snapshot JSONB NOT NULL,
    effective_from TIMESTAMPTZ NOT NULL DEFAULT transaction_timestamp(),
    effective_until TIMESTAMPTZ NULL,
    ended_by_principal_id TEXT NULL,
    end_reason TEXT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT transaction_timestamp(),
    PRIMARY KEY (tenant_id,action_assignment_id),
    UNIQUE (tenant_id,logical_action_id),
    FOREIGN KEY (tenant_id,alert_id) REFERENCES alerting.alert(tenant_id,alert_id),
    CHECK (tenant_id<>'' AND alert_id<>'' AND owner_principal_id<>''),
    CHECK (logical_action_id<>'' AND content_hash<>''),
    CHECK (jsonb_typeof(authority_snapshot)='object'),
    CHECK (
      (effective_until IS NULL AND ended_by_principal_id IS NULL AND end_reason IS NULL)
      OR
      (effective_until IS NOT NULL AND ended_by_principal_id IS NOT NULL AND end_reason IS NOT NULL)
    )
);

CREATE UNIQUE INDEX human_operations_one_current_action_owner
ON human_operations.alert_action_assignment(tenant_id,alert_id)
WHERE effective_until IS NULL;

CREATE TABLE human_operations.alert_acknowledgement (
    tenant_id TEXT NOT NULL,
    acknowledgement_id TEXT NOT NULL,
    alert_id TEXT NOT NULL,
    principal_id TEXT NOT NULL,
    logical_action_id TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    authority_snapshot JSONB NOT NULL,
    note TEXT NULL,
    acknowledged_at TIMESTAMPTZ NOT NULL DEFAULT transaction_timestamp(),
    PRIMARY KEY (tenant_id,acknowledgement_id),
    UNIQUE (tenant_id,logical_action_id),
    FOREIGN KEY (tenant_id,alert_id) REFERENCES alerting.alert(tenant_id,alert_id),
    CHECK (tenant_id<>'' AND alert_id<>'' AND principal_id<>''),
    CHECK (logical_action_id<>'' AND content_hash<>''),
    CHECK (jsonb_typeof(authority_snapshot)='object'),
    CHECK (note IS NULL OR length(note)<=1024)
);

CREATE TABLE human_operations.visibility_requirement (
    tenant_id TEXT NOT NULL,
    visibility_requirement_id TEXT NOT NULL,
    alert_id TEXT NOT NULL,
    required_viewer_principal_id TEXT NOT NULL,
    viewer_side TEXT NOT NULL CHECK (viewer_side IN ('internal','customer')),
    capability_class TEXT NOT NULL CHECK (capability_class='platform_native_authenticated_view@1'),
    presentation_ref TEXT NOT NULL,
    logical_action_id TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    created_by_principal_id TEXT NOT NULL,
    authority_snapshot JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT transaction_timestamp(),
    PRIMARY KEY (tenant_id,visibility_requirement_id),
    UNIQUE (tenant_id,logical_action_id),
    FOREIGN KEY (tenant_id,alert_id) REFERENCES alerting.alert(tenant_id,alert_id),
    CHECK (tenant_id<>'' AND alert_id<>'' AND required_viewer_principal_id<>''),
    CHECK (presentation_ref<>'' AND length(presentation_ref)<=1024),
    CHECK (logical_action_id<>'' AND content_hash<>''),
    CHECK (jsonb_typeof(authority_snapshot)='object')
);

CREATE TABLE human_operations.visibility_receipt (
    tenant_id TEXT NOT NULL,
    visibility_receipt_id TEXT NOT NULL,
    visibility_requirement_id TEXT NOT NULL,
    viewer_principal_id TEXT NOT NULL,
    logical_action_id TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    authority_snapshot JSONB NOT NULL,
    session_evidence JSONB NOT NULL,
    observed_at TIMESTAMPTZ NOT NULL DEFAULT transaction_timestamp(),
    PRIMARY KEY (tenant_id,visibility_receipt_id),
    UNIQUE (tenant_id,logical_action_id),
    FOREIGN KEY (tenant_id,visibility_requirement_id)
        REFERENCES human_operations.visibility_requirement(tenant_id,visibility_requirement_id),
    CHECK (tenant_id<>'' AND viewer_principal_id<>''),
    CHECK (logical_action_id<>'' AND content_hash<>''),
    CHECK (jsonb_typeof(authority_snapshot)='object'),
    CHECK (jsonb_typeof(session_evidence)='object')
);

CREATE TABLE human_operations.current_action_projection (
    tenant_id TEXT NOT NULL,
    alert_id TEXT NOT NULL,
    action_assignment_id TEXT NULL,
    owner_principal_id TEXT NULL,
    current_action TEXT NOT NULL CHECK (
        current_action IN (
            'investigate_alert','acknowledge_alert','review_alert',
            'customer_review_required','no_human_action_required'
        )
    ),
    projection_revision BIGINT NOT NULL CHECK (projection_revision>0),
    projected_at TIMESTAMPTZ NOT NULL DEFAULT transaction_timestamp(),
    PRIMARY KEY (tenant_id,alert_id),
    FOREIGN KEY (tenant_id,alert_id) REFERENCES alerting.alert(tenant_id,alert_id),
    CHECK (
      (current_action='no_human_action_required' AND action_assignment_id IS NULL AND owner_principal_id IS NULL)
      OR
      (current_action<>'no_human_action_required' AND action_assignment_id IS NOT NULL AND owner_principal_id IS NOT NULL)
    )
);

ALTER TABLE human_operations.resource_responsibility_assignment ENABLE ROW LEVEL SECURITY;
ALTER TABLE human_operations.resource_responsibility_assignment FORCE ROW LEVEL SECURITY;
ALTER TABLE human_operations.alert_action_assignment ENABLE ROW LEVEL SECURITY;
ALTER TABLE human_operations.alert_action_assignment FORCE ROW LEVEL SECURITY;
ALTER TABLE human_operations.alert_acknowledgement ENABLE ROW LEVEL SECURITY;
ALTER TABLE human_operations.alert_acknowledgement FORCE ROW LEVEL SECURITY;
ALTER TABLE human_operations.visibility_requirement ENABLE ROW LEVEL SECURITY;
ALTER TABLE human_operations.visibility_requirement FORCE ROW LEVEL SECURITY;
ALTER TABLE human_operations.visibility_receipt ENABLE ROW LEVEL SECURITY;
ALTER TABLE human_operations.visibility_receipt FORCE ROW LEVEL SECURITY;
ALTER TABLE human_operations.current_action_projection ENABLE ROW LEVEL SECURITY;
ALTER TABLE human_operations.current_action_projection FORCE ROW LEVEL SECURITY;

CREATE POLICY g8_resource_responsibility_tenant ON human_operations.resource_responsibility_assignment
USING (tenant_id=NULLIF(current_setting('jlmirror.tenant_id',true),''))
WITH CHECK (tenant_id=NULLIF(current_setting('jlmirror.tenant_id',true),''));
CREATE POLICY g8_action_assignment_tenant ON human_operations.alert_action_assignment
USING (tenant_id=NULLIF(current_setting('jlmirror.tenant_id',true),''))
WITH CHECK (tenant_id=NULLIF(current_setting('jlmirror.tenant_id',true),''));
CREATE POLICY g8_ack_tenant ON human_operations.alert_acknowledgement
USING (tenant_id=NULLIF(current_setting('jlmirror.tenant_id',true),''))
WITH CHECK (tenant_id=NULLIF(current_setting('jlmirror.tenant_id',true),''));
CREATE POLICY g8_visibility_requirement_tenant ON human_operations.visibility_requirement
USING (tenant_id=NULLIF(current_setting('jlmirror.tenant_id',true),''))
WITH CHECK (tenant_id=NULLIF(current_setting('jlmirror.tenant_id',true),''));
CREATE POLICY g8_visibility_receipt_tenant ON human_operations.visibility_receipt
USING (tenant_id=NULLIF(current_setting('jlmirror.tenant_id',true),''))
WITH CHECK (tenant_id=NULLIF(current_setting('jlmirror.tenant_id',true),''));
CREATE POLICY g8_current_action_tenant ON human_operations.current_action_projection
USING (tenant_id=NULLIF(current_setting('jlmirror.tenant_id',true),''))
WITH CHECK (tenant_id=NULLIF(current_setting('jlmirror.tenant_id',true),''));

REVOKE ALL ON
    human_operations.resource_responsibility_assignment,
    human_operations.alert_action_assignment,
    human_operations.alert_acknowledgement,
    human_operations.visibility_requirement,
    human_operations.visibility_receipt,
    human_operations.current_action_projection
FROM PUBLIC, jlmirror_g8_human_operations_invoker;

GRANT SELECT,INSERT,UPDATE ON
    human_operations.resource_responsibility_assignment,
    human_operations.alert_action_assignment,
    human_operations.current_action_projection
TO jlmirror_g8_human_operations_executor;
GRANT SELECT,INSERT ON
    human_operations.alert_acknowledgement,
    human_operations.visibility_requirement,
    human_operations.visibility_receipt
TO jlmirror_g8_human_operations_executor;
GRANT SELECT ON monitoring.monitoring_resource,alerting.alert
TO jlmirror_g8_human_operations_executor;

CREATE OR REPLACE FUNCTION human_operations.g8_reject_immutable_mutation()
RETURNS trigger
LANGUAGE plpgsql SECURITY INVOKER
SET search_path=pg_catalog,human_operations
AS $$
BEGIN
    RAISE EXCEPTION 'g8.immutable_fact';
END;
$$;

CREATE OR REPLACE FUNCTION human_operations.g8_guard_responsibility_closure()
RETURNS trigger
LANGUAGE plpgsql SECURITY INVOKER
SET search_path=pg_catalog,human_operations
AS $$
BEGIN
    IF TG_OP='DELETE' THEN
        RAISE EXCEPTION 'g8.responsibility_delete_forbidden';
    END IF;
    IF OLD.effective_until IS NOT NULL THEN
        RAISE EXCEPTION 'g8.responsibility_closed_terminal';
    END IF;
    IF NEW.tenant_id IS DISTINCT FROM OLD.tenant_id
       OR NEW.responsibility_assignment_id IS DISTINCT FROM OLD.responsibility_assignment_id
       OR NEW.monitoring_resource_id IS DISTINCT FROM OLD.monitoring_resource_id
       OR NEW.principal_id IS DISTINCT FROM OLD.principal_id
       OR NEW.responsibility_role IS DISTINCT FROM OLD.responsibility_role
       OR NEW.assignment_source IS DISTINCT FROM OLD.assignment_source
       OR NEW.logical_action_id IS DISTINCT FROM OLD.logical_action_id
       OR NEW.content_hash IS DISTINCT FROM OLD.content_hash
       OR NEW.assigned_by_principal_id IS DISTINCT FROM OLD.assigned_by_principal_id
       OR NEW.authority_snapshot IS DISTINCT FROM OLD.authority_snapshot
       OR NEW.effective_from IS DISTINCT FROM OLD.effective_from
       OR NEW.created_at IS DISTINCT FROM OLD.created_at
       OR NEW.effective_until IS NULL
       OR NEW.ended_by_principal_id IS NULL
       OR NEW.end_reason IS NULL THEN
        RAISE EXCEPTION 'g8.responsibility_closure_invalid';
    END IF;
    RETURN NEW;
END;
$$;

CREATE OR REPLACE FUNCTION human_operations.g8_guard_action_closure()
RETURNS trigger
LANGUAGE plpgsql SECURITY INVOKER
SET search_path=pg_catalog,human_operations
AS $$
BEGIN
    IF TG_OP='DELETE' THEN
        RAISE EXCEPTION 'g8.action_delete_forbidden';
    END IF;
    IF OLD.effective_until IS NOT NULL THEN
        RAISE EXCEPTION 'g8.action_closed_terminal';
    END IF;
    IF NEW.tenant_id IS DISTINCT FROM OLD.tenant_id
       OR NEW.action_assignment_id IS DISTINCT FROM OLD.action_assignment_id
       OR NEW.alert_id IS DISTINCT FROM OLD.alert_id
       OR NEW.owner_principal_id IS DISTINCT FROM OLD.owner_principal_id
       OR NEW.action_kind IS DISTINCT FROM OLD.action_kind
       OR NEW.logical_action_id IS DISTINCT FROM OLD.logical_action_id
       OR NEW.content_hash IS DISTINCT FROM OLD.content_hash
       OR NEW.assigned_by_principal_id IS DISTINCT FROM OLD.assigned_by_principal_id
       OR NEW.authority_snapshot IS DISTINCT FROM OLD.authority_snapshot
       OR NEW.effective_from IS DISTINCT FROM OLD.effective_from
       OR NEW.created_at IS DISTINCT FROM OLD.created_at
       OR NEW.effective_until IS NULL
       OR NEW.ended_by_principal_id IS NULL
       OR NEW.end_reason IS NULL THEN
        RAISE EXCEPTION 'g8.action_closure_invalid';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER g8_resource_responsibility_guard
BEFORE UPDATE OR DELETE ON human_operations.resource_responsibility_assignment
FOR EACH ROW EXECUTE FUNCTION human_operations.g8_guard_responsibility_closure();

CREATE TRIGGER g8_action_assignment_guard
BEFORE UPDATE OR DELETE ON human_operations.alert_action_assignment
FOR EACH ROW EXECUTE FUNCTION human_operations.g8_guard_action_closure();

CREATE TRIGGER g8_ack_immutable
BEFORE UPDATE OR DELETE ON human_operations.alert_acknowledgement
FOR EACH ROW EXECUTE FUNCTION human_operations.g8_reject_immutable_mutation();

CREATE TRIGGER g8_visibility_requirement_immutable
BEFORE UPDATE OR DELETE ON human_operations.visibility_requirement
FOR EACH ROW EXECUTE FUNCTION human_operations.g8_reject_immutable_mutation();

CREATE TRIGGER g8_visibility_receipt_immutable
BEFORE UPDATE OR DELETE ON human_operations.visibility_receipt
FOR EACH ROW EXECUTE FUNCTION human_operations.g8_reject_immutable_mutation();

DO $$
DECLARE
    v_executor_oid OID;
    v_invoker_oid OID;
    v_row RECORD;
    v_proc_oid OID;
BEGIN
    SELECT oid INTO v_executor_oid FROM pg_roles WHERE rolname='jlmirror_g8_human_operations_executor';
    SELECT oid INTO v_invoker_oid FROM pg_roles WHERE rolname='jlmirror_g8_human_operations_invoker';

    FOR v_row IN
        SELECT signature FROM (VALUES
          ('human_operations.g8_validate_authority(text,text,jsonb)'),
          ('human_operations.g8_assign_resource_responsibility(text,text,text,text,text,text,text,jsonb)'),
          ('human_operations.g8_end_resource_responsibility(text,text,text,text,jsonb)'),
          ('human_operations.g8_assign_alert_action(text,text,text,text,text,text,jsonb)'),
          ('human_operations.g8_acknowledge_alert(text,text,text,text,text,jsonb)'),
          ('human_operations.g8_create_visibility_requirement(text,text,text,text,text,text,text,text,jsonb)'),
          ('human_operations.g8_record_visibility_receipt(text,text,text,text,jsonb,jsonb)'),
          ('human_operations.g8_alert_human_operations(text,text)'),
          ('human_operations.g8_resource_responsibilities(text,text)')
        ) AS guarded(signature)
    LOOP
        v_proc_oid:=to_regprocedure(v_row.signature);
        IF v_proc_oid IS NULL THEN CONTINUE; END IF;

        IF EXISTS (
          SELECT 1
          FROM pg_proc p,
               LATERAL aclexplode(COALESCE(p.proacl,acldefault('f',p.proowner))) a
          WHERE p.oid=v_proc_oid
            AND a.privilege_type='EXECUTE'
            AND (
              a.grantee=0
              OR (a.grantee<>p.proowner AND (a.grantee<>v_invoker_oid OR a.is_grantable))
            )
        ) THEN
          RAISE EXCEPTION 'g8.existing_function_acl_unsafe:%',v_row.signature;
        END IF;
    END LOOP;
END;
$$;

CREATE OR REPLACE FUNCTION human_operations.g8_validate_authority(
    p_tenant_id TEXT,p_actor_principal_id TEXT,p_authority_snapshot JSONB
) RETURNS VOID
LANGUAGE plpgsql SECURITY INVOKER
SET search_path=pg_catalog,human_operations
AS $$
BEGIN
    IF jsonb_typeof(p_authority_snapshot)<>'object'
       OR COALESCE((p_authority_snapshot->>'current')::BOOLEAN,false) IS NOT TRUE
       OR p_authority_snapshot->>'tenant_id' IS DISTINCT FROM p_tenant_id
       OR p_authority_snapshot->>'principal_id' IS DISTINCT FROM p_actor_principal_id
       OR COALESCE(p_authority_snapshot->>'action','')=''
       OR COALESCE(p_authority_snapshot->>'policy_revision','')='' THEN
        RAISE EXCEPTION 'g8.current_authority_required';
    END IF;
END;
$$;

CREATE OR REPLACE FUNCTION human_operations.g8_assign_resource_responsibility(
    p_tenant_id TEXT,p_resource_id TEXT,p_responsible_principal_id TEXT,
    p_responsibility_role TEXT,p_assignment_source TEXT,p_actor_principal_id TEXT,
    p_logical_action_id TEXT,p_authority_snapshot JSONB
) RETURNS JSONB
LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,human_operations,monitoring
AS $$
DECLARE
    v_id TEXT;
    v_hash TEXT;
    v_existing human_operations.resource_responsibility_assignment%ROWTYPE;
BEGIN
    PERFORM human_operations.g8_validate_authority(p_tenant_id,p_actor_principal_id,p_authority_snapshot);
    IF p_responsibility_role NOT IN ('technical_responsible','service_owner','operator','customer_responsible')
       OR p_assignment_source NOT IN ('manual','configured')
       OR COALESCE(p_responsible_principal_id,'')=''
       OR COALESCE(p_logical_action_id,'')='' THEN
        RAISE EXCEPTION 'g8.resource_responsibility_input_invalid';
    END IF;
    PERFORM set_config('jlmirror.tenant_id',p_tenant_id,true);
    PERFORM 1 FROM monitoring.monitoring_resource
     WHERE tenant_id=p_tenant_id AND monitoring_resource_id=p_resource_id;
    IF NOT FOUND THEN RAISE EXCEPTION 'g8.current_resource_missing'; END IF;

    v_hash:=md5(concat_ws(chr(31),p_resource_id,p_responsible_principal_id,p_responsibility_role,p_assignment_source,p_actor_principal_id));
    v_id:='g8-responsibility:'||md5(p_tenant_id||chr(31)||p_logical_action_id);

    SELECT * INTO v_existing FROM human_operations.resource_responsibility_assignment
     WHERE tenant_id=p_tenant_id AND logical_action_id=p_logical_action_id;
    IF FOUND THEN
      IF v_existing.content_hash<>v_hash THEN RAISE EXCEPTION 'g8.responsibility_equivalence_conflict'; END IF;
      RETURN jsonb_build_object('responsibility_assignment_id',v_existing.responsibility_assignment_id,'duplicate',true);
    END IF;

    INSERT INTO human_operations.resource_responsibility_assignment(
      tenant_id,responsibility_assignment_id,monitoring_resource_id,principal_id,
      responsibility_role,assignment_source,logical_action_id,content_hash,
      assigned_by_principal_id,authority_snapshot
    ) VALUES (
      p_tenant_id,v_id,p_resource_id,p_responsible_principal_id,
      p_responsibility_role,p_assignment_source,p_logical_action_id,v_hash,
      p_actor_principal_id,p_authority_snapshot
    );
    RETURN jsonb_build_object('responsibility_assignment_id',v_id,'duplicate',false);
END;
$$;

CREATE OR REPLACE FUNCTION human_operations.g8_end_resource_responsibility(
    p_tenant_id TEXT,p_assignment_id TEXT,p_actor_principal_id TEXT,
    p_end_reason TEXT,p_authority_snapshot JSONB
) RETURNS JSONB
LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,human_operations
AS $$
DECLARE v_row human_operations.resource_responsibility_assignment%ROWTYPE;
BEGIN
    PERFORM human_operations.g8_validate_authority(p_tenant_id,p_actor_principal_id,p_authority_snapshot);
    IF COALESCE(p_end_reason,'')='' OR length(p_end_reason)>256 THEN
        RAISE EXCEPTION 'g8.responsibility_end_reason_invalid';
    END IF;
    PERFORM set_config('jlmirror.tenant_id',p_tenant_id,true);
    SELECT * INTO v_row FROM human_operations.resource_responsibility_assignment
     WHERE tenant_id=p_tenant_id AND responsibility_assignment_id=p_assignment_id FOR UPDATE;
    IF NOT FOUND THEN RAISE EXCEPTION 'g8.responsibility_assignment_missing'; END IF;
    IF v_row.effective_until IS NOT NULL THEN
      RETURN jsonb_build_object('responsibility_assignment_id',p_assignment_id,'duplicate',true);
    END IF;
    UPDATE human_operations.resource_responsibility_assignment
       SET effective_until=transaction_timestamp(),
           ended_by_principal_id=p_actor_principal_id,end_reason=p_end_reason
     WHERE tenant_id=p_tenant_id AND responsibility_assignment_id=p_assignment_id;
    RETURN jsonb_build_object('responsibility_assignment_id',p_assignment_id,'duplicate',false);
END;
$$;

CREATE OR REPLACE FUNCTION human_operations.g8_assign_alert_action(
    p_tenant_id TEXT,p_alert_id TEXT,p_owner_principal_id TEXT,p_action_kind TEXT,
    p_actor_principal_id TEXT,p_logical_action_id TEXT,p_authority_snapshot JSONB
) RETURNS JSONB
LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,human_operations,alerting
AS $$
DECLARE
    v_id TEXT; v_hash TEXT;
    v_existing human_operations.alert_action_assignment%ROWTYPE;
    v_current human_operations.alert_action_assignment%ROWTYPE;
    v_revision BIGINT;
BEGIN
    PERFORM human_operations.g8_validate_authority(p_tenant_id,p_actor_principal_id,p_authority_snapshot);
    IF p_action_kind NOT IN ('investigate_alert','acknowledge_alert','review_alert','customer_review_required')
       OR COALESCE(p_owner_principal_id,'')='' OR COALESCE(p_logical_action_id,'')='' THEN
      RAISE EXCEPTION 'g8.action_assignment_input_invalid';
    END IF;
    PERFORM set_config('jlmirror.tenant_id',p_tenant_id,true);
    PERFORM pg_advisory_xact_lock(hashtextextended(p_tenant_id||chr(31)||p_alert_id,0));
    PERFORM 1 FROM alerting.alert
     WHERE tenant_id=p_tenant_id AND alert_id=p_alert_id AND lifecycle_state='active';
    IF NOT FOUND THEN RAISE EXCEPTION 'g8.active_alert_required'; END IF;

    v_hash:=md5(concat_ws(chr(31),p_alert_id,p_owner_principal_id,p_action_kind,p_actor_principal_id));
    v_id:='g8-action:'||md5(p_tenant_id||chr(31)||p_logical_action_id);

    SELECT * INTO v_existing FROM human_operations.alert_action_assignment
     WHERE tenant_id=p_tenant_id AND logical_action_id=p_logical_action_id;
    IF FOUND THEN
      IF v_existing.content_hash<>v_hash THEN RAISE EXCEPTION 'g8.action_equivalence_conflict'; END IF;
      RETURN jsonb_build_object('action_assignment_id',v_existing.action_assignment_id,'duplicate',true);
    END IF;

    SELECT * INTO v_current FROM human_operations.alert_action_assignment
     WHERE tenant_id=p_tenant_id AND alert_id=p_alert_id AND effective_until IS NULL
     FOR UPDATE;
    IF FOUND THEN
      UPDATE human_operations.alert_action_assignment
         SET effective_until=transaction_timestamp(),
             ended_by_principal_id=p_actor_principal_id,
             end_reason='reassigned'
       WHERE tenant_id=p_tenant_id AND action_assignment_id=v_current.action_assignment_id;
    END IF;

    INSERT INTO human_operations.alert_action_assignment(
      tenant_id,action_assignment_id,alert_id,owner_principal_id,action_kind,
      logical_action_id,content_hash,assigned_by_principal_id,authority_snapshot
    ) VALUES (
      p_tenant_id,v_id,p_alert_id,p_owner_principal_id,p_action_kind,
      p_logical_action_id,v_hash,p_actor_principal_id,p_authority_snapshot
    );

    SELECT COALESCE(projection_revision,0)+1 INTO v_revision
      FROM human_operations.current_action_projection
     WHERE tenant_id=p_tenant_id AND alert_id=p_alert_id;
    v_revision:=COALESCE(v_revision,1);

    INSERT INTO human_operations.current_action_projection(
      tenant_id,alert_id,action_assignment_id,owner_principal_id,current_action,projection_revision,projected_at
    ) VALUES (
      p_tenant_id,p_alert_id,v_id,p_owner_principal_id,p_action_kind,v_revision,transaction_timestamp()
    )
    ON CONFLICT (tenant_id,alert_id) DO UPDATE SET
      action_assignment_id=EXCLUDED.action_assignment_id,
      owner_principal_id=EXCLUDED.owner_principal_id,
      current_action=EXCLUDED.current_action,
      projection_revision=EXCLUDED.projection_revision,
      projected_at=EXCLUDED.projected_at;

    RETURN jsonb_build_object('action_assignment_id',v_id,'duplicate',false,'projection_revision',v_revision);
END;
$$;

CREATE OR REPLACE FUNCTION human_operations.g8_acknowledge_alert(
    p_tenant_id TEXT,p_alert_id TEXT,p_actor_principal_id TEXT,
    p_logical_action_id TEXT,p_note TEXT,p_authority_snapshot JSONB
) RETURNS JSONB
LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,human_operations,alerting
AS $$
DECLARE
    v_id TEXT; v_hash TEXT;
    v_existing human_operations.alert_acknowledgement%ROWTYPE;
BEGIN
    PERFORM human_operations.g8_validate_authority(p_tenant_id,p_actor_principal_id,p_authority_snapshot);
    IF COALESCE(p_logical_action_id,'')='' OR (p_note IS NOT NULL AND length(p_note)>1024) THEN
      RAISE EXCEPTION 'g8.ack_input_invalid';
    END IF;
    PERFORM set_config('jlmirror.tenant_id',p_tenant_id,true);
    PERFORM 1 FROM alerting.alert
     WHERE tenant_id=p_tenant_id AND alert_id=p_alert_id AND lifecycle_state='active';
    IF NOT FOUND THEN RAISE EXCEPTION 'g8.active_alert_required'; END IF;

    v_hash:=md5(concat_ws(chr(31),p_alert_id,p_actor_principal_id,COALESCE(p_note,'')));
    v_id:='g8-ack:'||md5(p_tenant_id||chr(31)||p_logical_action_id);
    SELECT * INTO v_existing FROM human_operations.alert_acknowledgement
     WHERE tenant_id=p_tenant_id AND logical_action_id=p_logical_action_id;
    IF FOUND THEN
      IF v_existing.content_hash<>v_hash THEN RAISE EXCEPTION 'g8.ack_equivalence_conflict'; END IF;
      RETURN jsonb_build_object('acknowledgement_id',v_existing.acknowledgement_id,'duplicate',true);
    END IF;

    INSERT INTO human_operations.alert_acknowledgement(
      tenant_id,acknowledgement_id,alert_id,principal_id,logical_action_id,
      content_hash,authority_snapshot,note
    ) VALUES (
      p_tenant_id,v_id,p_alert_id,p_actor_principal_id,p_logical_action_id,
      v_hash,p_authority_snapshot,p_note
    );
    RETURN jsonb_build_object('acknowledgement_id',v_id,'duplicate',false);
END;
$$;

CREATE OR REPLACE FUNCTION human_operations.g8_create_visibility_requirement(
    p_tenant_id TEXT,p_alert_id TEXT,p_viewer_principal_id TEXT,p_viewer_side TEXT,
    p_capability_class TEXT,p_presentation_ref TEXT,p_actor_principal_id TEXT,
    p_logical_action_id TEXT,p_authority_snapshot JSONB
) RETURNS JSONB
LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,human_operations,alerting
AS $$
DECLARE
    v_id TEXT; v_hash TEXT;
    v_existing human_operations.visibility_requirement%ROWTYPE;
BEGIN
    PERFORM human_operations.g8_validate_authority(p_tenant_id,p_actor_principal_id,p_authority_snapshot);
    IF p_viewer_side NOT IN ('internal','customer')
       OR p_capability_class<>'platform_native_authenticated_view@1'
       OR COALESCE(p_viewer_principal_id,'')=''
       OR COALESCE(p_presentation_ref,'')='' OR length(p_presentation_ref)>1024
       OR COALESCE(p_logical_action_id,'')='' THEN
      RAISE EXCEPTION 'g8.visibility_requirement_input_invalid';
    END IF;
    PERFORM set_config('jlmirror.tenant_id',p_tenant_id,true);
    PERFORM 1 FROM alerting.alert
     WHERE tenant_id=p_tenant_id AND alert_id=p_alert_id AND lifecycle_state='active';
    IF NOT FOUND THEN RAISE EXCEPTION 'g8.active_alert_required'; END IF;

    v_hash:=md5(concat_ws(chr(31),p_alert_id,p_viewer_principal_id,p_viewer_side,p_capability_class,p_presentation_ref,p_actor_principal_id));
    v_id:='g8-view-required:'||md5(p_tenant_id||chr(31)||p_logical_action_id);
    SELECT * INTO v_existing FROM human_operations.visibility_requirement
     WHERE tenant_id=p_tenant_id AND logical_action_id=p_logical_action_id;
    IF FOUND THEN
      IF v_existing.content_hash<>v_hash THEN RAISE EXCEPTION 'g8.visibility_requirement_equivalence_conflict'; END IF;
      RETURN jsonb_build_object('visibility_requirement_id',v_existing.visibility_requirement_id,'duplicate',true);
    END IF;

    INSERT INTO human_operations.visibility_requirement(
      tenant_id,visibility_requirement_id,alert_id,required_viewer_principal_id,
      viewer_side,capability_class,presentation_ref,logical_action_id,content_hash,
      created_by_principal_id,authority_snapshot
    ) VALUES (
      p_tenant_id,v_id,p_alert_id,p_viewer_principal_id,
      p_viewer_side,p_capability_class,p_presentation_ref,p_logical_action_id,v_hash,
      p_actor_principal_id,p_authority_snapshot
    );
    RETURN jsonb_build_object('visibility_requirement_id',v_id,'duplicate',false);
END;
$$;

CREATE OR REPLACE FUNCTION human_operations.g8_record_visibility_receipt(
    p_tenant_id TEXT,p_requirement_id TEXT,p_viewer_principal_id TEXT,
    p_logical_action_id TEXT,p_authority_snapshot JSONB,p_session_evidence JSONB
) RETURNS JSONB
LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,human_operations
AS $$
DECLARE
    v_req human_operations.visibility_requirement%ROWTYPE;
    v_id TEXT; v_hash TEXT;
    v_existing human_operations.visibility_receipt%ROWTYPE;
BEGIN
    PERFORM human_operations.g8_validate_authority(p_tenant_id,p_viewer_principal_id,p_authority_snapshot);
    IF COALESCE(p_logical_action_id,'')='' OR jsonb_typeof(p_session_evidence)<>'object' THEN
      RAISE EXCEPTION 'g8.visibility_receipt_input_invalid';
    END IF;
    PERFORM set_config('jlmirror.tenant_id',p_tenant_id,true);
    SELECT * INTO v_req FROM human_operations.visibility_requirement
     WHERE tenant_id=p_tenant_id AND visibility_requirement_id=p_requirement_id;
    IF NOT FOUND THEN RAISE EXCEPTION 'g8.visibility_requirement_missing'; END IF;
    IF v_req.required_viewer_principal_id<>p_viewer_principal_id THEN
      RAISE EXCEPTION 'g8.visibility_viewer_mismatch';
    END IF;

    v_hash:=md5(concat_ws(chr(31),p_requirement_id,p_viewer_principal_id,p_session_evidence::TEXT));
    v_id:='g8-view-receipt:'||md5(p_tenant_id||chr(31)||p_logical_action_id);
    SELECT * INTO v_existing FROM human_operations.visibility_receipt
     WHERE tenant_id=p_tenant_id AND logical_action_id=p_logical_action_id;
    IF FOUND THEN
      IF v_existing.content_hash<>v_hash THEN RAISE EXCEPTION 'g8.visibility_receipt_equivalence_conflict'; END IF;
      RETURN jsonb_build_object('visibility_receipt_id',v_existing.visibility_receipt_id,'duplicate',true);
    END IF;

    INSERT INTO human_operations.visibility_receipt(
      tenant_id,visibility_receipt_id,visibility_requirement_id,viewer_principal_id,
      logical_action_id,content_hash,authority_snapshot,session_evidence
    ) VALUES (
      p_tenant_id,v_id,p_requirement_id,p_viewer_principal_id,
      p_logical_action_id,v_hash,p_authority_snapshot,p_session_evidence
    );
    RETURN jsonb_build_object('visibility_receipt_id',v_id,'duplicate',false);
END;
$$;

CREATE OR REPLACE FUNCTION human_operations.g8_alert_human_operations(
    p_tenant_id TEXT,p_alert_id TEXT
) RETURNS JSONB
LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,human_operations,alerting
AS $$
DECLARE
    v_alert_state TEXT;
    v_action JSONB;
    v_acks JSONB;
    v_visibility JSONB;
    v_timeline JSONB;
BEGIN
    PERFORM set_config('jlmirror.tenant_id',p_tenant_id,true);
    SELECT lifecycle_state INTO v_alert_state
      FROM alerting.alert WHERE tenant_id=p_tenant_id AND alert_id=p_alert_id;
    IF NOT FOUND THEN RAISE EXCEPTION 'g8.alert_missing'; END IF;

    IF v_alert_state='active' THEN
      SELECT to_jsonb(x) INTO v_action FROM (
        SELECT owner_principal_id,action_kind,action_assignment_id,effective_from
        FROM human_operations.alert_action_assignment
        WHERE tenant_id=p_tenant_id AND alert_id=p_alert_id AND effective_until IS NULL
      ) x;
      IF v_action IS NULL THEN
        v_action:=jsonb_build_object(
          'owner_principal_id',NULL,
          'action_assignment_id',NULL,
          'action_kind','no_human_action_required'
        );
      END IF;
    ELSE
      v_action:=jsonb_build_object(
        'owner_principal_id',NULL,
        'action_assignment_id',NULL,
        'action_kind','no_human_action_required'
      );
    END IF;

    SELECT COALESCE(jsonb_agg(to_jsonb(x) ORDER BY acknowledged_at),'[]'::jsonb) INTO v_acks FROM (
      SELECT acknowledgement_id,principal_id,acknowledged_at,note
      FROM human_operations.alert_acknowledgement
      WHERE tenant_id=p_tenant_id AND alert_id=p_alert_id
    ) x;

    SELECT COALESCE(jsonb_agg(to_jsonb(x) ORDER BY created_at),'[]'::jsonb) INTO v_visibility FROM (
      SELECT r.visibility_requirement_id,r.required_viewer_principal_id,r.viewer_side,
             CASE WHEN EXISTS (
               SELECT 1 FROM human_operations.visibility_receipt vr
               WHERE vr.tenant_id=r.tenant_id AND vr.visibility_requirement_id=r.visibility_requirement_id
             ) THEN 'viewed' ELSE 'not_viewed_yet' END AS visibility_state,
             r.created_at
      FROM human_operations.visibility_requirement r
      WHERE r.tenant_id=p_tenant_id AND r.alert_id=p_alert_id
    ) x;

    SELECT COALESCE(jsonb_agg(to_jsonb(x) ORDER BY occurred_at,kind),'[]'::jsonb) INTO v_timeline
    FROM (
      SELECT 'action_assigned'::TEXT kind,effective_from occurred_at,action_assignment_id ref
      FROM human_operations.alert_action_assignment WHERE tenant_id=p_tenant_id AND alert_id=p_alert_id
      UNION ALL
      SELECT 'action_ended',effective_until,action_assignment_id
      FROM human_operations.alert_action_assignment WHERE tenant_id=p_tenant_id AND alert_id=p_alert_id AND effective_until IS NOT NULL
      UNION ALL
      SELECT 'acknowledged',acknowledged_at,acknowledgement_id
      FROM human_operations.alert_acknowledgement WHERE tenant_id=p_tenant_id AND alert_id=p_alert_id
      UNION ALL
      SELECT 'visibility_required',created_at,visibility_requirement_id
      FROM human_operations.visibility_requirement WHERE tenant_id=p_tenant_id AND alert_id=p_alert_id
      UNION ALL
      SELECT 'visibility_observed',vr.observed_at,vr.visibility_receipt_id
      FROM human_operations.visibility_receipt vr
      JOIN human_operations.visibility_requirement rq
        ON rq.tenant_id=vr.tenant_id AND rq.visibility_requirement_id=vr.visibility_requirement_id
      WHERE rq.tenant_id=p_tenant_id AND rq.alert_id=p_alert_id
    ) x WHERE occurred_at IS NOT NULL;

    RETURN jsonb_build_object(
      'alert_id',p_alert_id,'alert_lifecycle_state',v_alert_state,
      'current_action',v_action,'acknowledgements',v_acks,
      'visibility',v_visibility,'timeline',v_timeline
    );
END;
$$;

CREATE OR REPLACE FUNCTION human_operations.g8_resource_responsibilities(
    p_tenant_id TEXT,p_resource_id TEXT
) RETURNS JSONB
LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,human_operations,monitoring
AS $$
DECLARE v_result JSONB;
BEGIN
    PERFORM set_config('jlmirror.tenant_id',p_tenant_id,true);
    PERFORM 1 FROM monitoring.monitoring_resource
     WHERE tenant_id=p_tenant_id AND monitoring_resource_id=p_resource_id;
    IF NOT FOUND THEN RAISE EXCEPTION 'g8.current_resource_missing'; END IF;
    SELECT COALESCE(jsonb_agg(to_jsonb(x) ORDER BY effective_from),'[]'::jsonb) INTO v_result
    FROM (
      SELECT responsibility_assignment_id,principal_id,responsibility_role,
             assignment_source,effective_from,effective_until
      FROM human_operations.resource_responsibility_assignment
      WHERE tenant_id=p_tenant_id AND monitoring_resource_id=p_resource_id
    ) x;
    RETURN v_result;
END;
$$;

ALTER FUNCTION human_operations.g8_reject_immutable_mutation()
OWNER TO jlmirror_g8_human_operations_executor;
ALTER FUNCTION human_operations.g8_guard_responsibility_closure()
OWNER TO jlmirror_g8_human_operations_executor;
ALTER FUNCTION human_operations.g8_guard_action_closure()
OWNER TO jlmirror_g8_human_operations_executor;
ALTER FUNCTION human_operations.g8_validate_authority(TEXT,TEXT,JSONB)
OWNER TO jlmirror_g8_human_operations_executor;
ALTER FUNCTION human_operations.g8_assign_resource_responsibility(TEXT,TEXT,TEXT,TEXT,TEXT,TEXT,TEXT,JSONB)
OWNER TO jlmirror_g8_human_operations_executor;
ALTER FUNCTION human_operations.g8_end_resource_responsibility(TEXT,TEXT,TEXT,TEXT,JSONB)
OWNER TO jlmirror_g8_human_operations_executor;
ALTER FUNCTION human_operations.g8_assign_alert_action(TEXT,TEXT,TEXT,TEXT,TEXT,TEXT,JSONB)
OWNER TO jlmirror_g8_human_operations_executor;
ALTER FUNCTION human_operations.g8_acknowledge_alert(TEXT,TEXT,TEXT,TEXT,TEXT,JSONB)
OWNER TO jlmirror_g8_human_operations_executor;
ALTER FUNCTION human_operations.g8_create_visibility_requirement(TEXT,TEXT,TEXT,TEXT,TEXT,TEXT,TEXT,TEXT,JSONB)
OWNER TO jlmirror_g8_human_operations_executor;
ALTER FUNCTION human_operations.g8_record_visibility_receipt(TEXT,TEXT,TEXT,TEXT,JSONB,JSONB)
OWNER TO jlmirror_g8_human_operations_executor;
ALTER FUNCTION human_operations.g8_alert_human_operations(TEXT,TEXT)
OWNER TO jlmirror_g8_human_operations_executor;
ALTER FUNCTION human_operations.g8_resource_responsibilities(TEXT,TEXT)
OWNER TO jlmirror_g8_human_operations_executor;

REVOKE ALL ON ALL FUNCTIONS IN SCHEMA human_operations FROM PUBLIC;
GRANT EXECUTE ON FUNCTION human_operations.g8_assign_resource_responsibility(TEXT,TEXT,TEXT,TEXT,TEXT,TEXT,TEXT,JSONB) TO jlmirror_g8_human_operations_invoker;
GRANT EXECUTE ON FUNCTION human_operations.g8_end_resource_responsibility(TEXT,TEXT,TEXT,TEXT,JSONB) TO jlmirror_g8_human_operations_invoker;
GRANT EXECUTE ON FUNCTION human_operations.g8_assign_alert_action(TEXT,TEXT,TEXT,TEXT,TEXT,TEXT,JSONB) TO jlmirror_g8_human_operations_invoker;
GRANT EXECUTE ON FUNCTION human_operations.g8_acknowledge_alert(TEXT,TEXT,TEXT,TEXT,TEXT,JSONB) TO jlmirror_g8_human_operations_invoker;
GRANT EXECUTE ON FUNCTION human_operations.g8_create_visibility_requirement(TEXT,TEXT,TEXT,TEXT,TEXT,TEXT,TEXT,TEXT,JSONB) TO jlmirror_g8_human_operations_invoker;
GRANT EXECUTE ON FUNCTION human_operations.g8_record_visibility_receipt(TEXT,TEXT,TEXT,TEXT,JSONB,JSONB) TO jlmirror_g8_human_operations_invoker;
GRANT EXECUTE ON FUNCTION human_operations.g8_alert_human_operations(TEXT,TEXT) TO jlmirror_g8_human_operations_invoker;
GRANT EXECUTE ON FUNCTION human_operations.g8_resource_responsibilities(TEXT,TEXT) TO jlmirror_g8_human_operations_invoker;

DO $$
DECLARE
    v_executor_oid OID;
    v_invoker_oid OID;
    v_row RECORD;
    v_proc_oid OID;
BEGIN
    SELECT oid INTO v_executor_oid FROM pg_roles WHERE rolname='jlmirror_g8_human_operations_executor';
    SELECT oid INTO v_invoker_oid FROM pg_roles WHERE rolname='jlmirror_g8_human_operations_invoker';

    FOR v_row IN
        SELECT signature,exposed FROM (VALUES
          ('human_operations.g8_validate_authority(text,text,jsonb)',false),
          ('human_operations.g8_assign_resource_responsibility(text,text,text,text,text,text,text,jsonb)',true),
          ('human_operations.g8_end_resource_responsibility(text,text,text,text,jsonb)',true),
          ('human_operations.g8_assign_alert_action(text,text,text,text,text,text,jsonb)',true),
          ('human_operations.g8_acknowledge_alert(text,text,text,text,text,jsonb)',true),
          ('human_operations.g8_create_visibility_requirement(text,text,text,text,text,text,text,text,jsonb)',true),
          ('human_operations.g8_record_visibility_receipt(text,text,text,text,jsonb,jsonb)',true),
          ('human_operations.g8_alert_human_operations(text,text)',true),
          ('human_operations.g8_resource_responsibilities(text,text)',true)
        ) AS guarded(signature,exposed)
    LOOP
        v_proc_oid:=to_regprocedure(v_row.signature);
        IF v_proc_oid IS NULL THEN
          RAISE EXCEPTION 'g8.installed_function_missing:%',v_row.signature;
        END IF;
        IF EXISTS (
          SELECT 1 FROM pg_proc p
          WHERE p.oid=v_proc_oid
            AND (p.proowner<>v_executor_oid OR (v_row.exposed AND NOT p.prosecdef))
        ) THEN
          RAISE EXCEPTION 'g8.installed_function_definition_unsafe:%',v_row.signature;
        END IF;
        IF EXISTS (
          SELECT 1
          FROM pg_proc p,
               LATERAL aclexplode(COALESCE(p.proacl,acldefault('f',p.proowner))) a
          WHERE p.oid=v_proc_oid AND a.privilege_type='EXECUTE'
            AND (
              a.grantee=0
              OR (a.grantee<>p.proowner AND (
                  (NOT v_row.exposed)
                  OR a.grantee<>v_invoker_oid
                  OR a.is_grantable
              ))
            )
        ) THEN
          RAISE EXCEPTION 'g8.installed_function_acl_unsafe:%',v_row.signature;
        END IF;
        IF v_row.exposed AND NOT EXISTS (
          SELECT 1
          FROM pg_proc p,
               LATERAL aclexplode(COALESCE(p.proacl,acldefault('f',p.proowner))) a
          WHERE p.oid=v_proc_oid
            AND a.privilege_type='EXECUTE'
            AND a.grantee=v_invoker_oid
            AND NOT a.is_grantable
        ) THEN
          RAISE EXCEPTION 'g8.installed_invoker_execute_missing:%',v_row.signature;
        END IF;
    END LOOP;
END;
$$;

COMMIT;
