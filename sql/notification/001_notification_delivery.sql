-- G9 Notification + Delivery golden path.
-- Authority: g9.notification-delivery@1.
-- One admitted transport channel: whatsapp_business@1.

BEGIN;

CREATE SCHEMA IF NOT EXISTS notification;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='jlmirror_g9_notification_executor') THEN
        CREATE ROLE jlmirror_g9_notification_executor
          NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='jlmirror_g9_notification_app_invoker') THEN
        CREATE ROLE jlmirror_g9_notification_app_invoker
          NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='jlmirror_g9_notification_worker_invoker') THEN
        CREATE ROLE jlmirror_g9_notification_worker_invoker
          NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='jlmirror_g9_notification_callback_invoker') THEN
        CREATE ROLE jlmirror_g9_notification_callback_invoker
          NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS;
    END IF;
END;
$$;

DO $$
DECLARE
    v_role RECORD;
BEGIN
    FOR v_role IN
      SELECT * FROM pg_roles
      WHERE rolname IN (
        'jlmirror_g9_notification_executor',
        'jlmirror_g9_notification_app_invoker',
        'jlmirror_g9_notification_worker_invoker',
        'jlmirror_g9_notification_callback_invoker'
      )
    LOOP
      IF v_role.rolcanlogin OR v_role.rolsuper OR v_role.rolcreatedb OR v_role.rolcreaterole
         OR v_role.rolinherit OR v_role.rolreplication OR v_role.rolbypassrls THEN
        RAISE EXCEPTION 'g9.role_unsafe_attributes:%',v_role.rolname;
      END IF;
      IF EXISTS (
        SELECT 1 FROM pg_auth_members
        WHERE roleid=v_role.oid OR member=v_role.oid
      ) THEN
        RAISE EXCEPTION 'g9.role_unsafe_membership:%',v_role.rolname;
      END IF;
    END LOOP;
END;
$;

DO $
DECLARE
  v_executor_oid OID;
  v_unexpected TEXT;
BEGIN
  SELECT oid INTO v_executor_oid
  FROM pg_roles WHERE rolname='jlmirror_g9_notification_executor';

  WITH allowed_proc_oids AS (
    SELECT to_regprocedure(signature) AS proc_oid
    FROM (VALUES
      ('notification.g9_reject_immutable_mutation()'),
      ('notification.g9_guard_attempt_terminal_transition()'),
      ('notification.g9_validate_authority(text,text,jsonb)'),
      ('notification.g9_refresh_projection(text,text)'),
      ('notification.g9_create_intent(text,text,text,text,text,text,text,text,text,text,text,jsonb)'),
      ('notification.g9_next_dispatch_candidate(text)'),
      ('notification.g9_claim_dispatch(text,text,text,integer,text,jsonb)'),
      ('notification.g9_complete_dispatch(text,text,text,text,text,text)'),
      ('notification.g9_reconcile_dispatch_claim(text,text)'),
      ('notification.g9_schedule_retry(text,text)'),
      ('notification.g9_record_provider_callback(text,text,text,text,text,jsonb,jsonb,timestamp with time zone)'),
      ('notification.g9_get_intent(text,text)'),
      ('notification.g9_list_alert_intents(text,text)')
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
       AND d.objid IN (
         SELECT proc_oid FROM allowed_proc_oids WHERE proc_oid IS NOT NULL
       )
     )
   ORDER BY d.dbid,d.classid,d.objid
   LIMIT 1;

  IF v_unexpected IS NOT NULL THEN
    RAISE EXCEPTION 'g9.executor_unexpected_owned_object:%',v_unexpected;
  END IF;
END;
$;

GRANT USAGE ON SCHEMA notification,alerting,human_operations TO jlmirror_g9_notification_executor;
GRANT USAGE ON SCHEMA notification TO
  jlmirror_g9_notification_app_invoker,
  jlmirror_g9_notification_worker_invoker,
  jlmirror_g9_notification_callback_invoker;
REVOKE CREATE ON SCHEMA notification,alerting,human_operations FROM
  jlmirror_g9_notification_executor,
  jlmirror_g9_notification_app_invoker,
  jlmirror_g9_notification_worker_invoker,
  jlmirror_g9_notification_callback_invoker;

CREATE TABLE notification.notification_intent (
    tenant_id TEXT NOT NULL,
    notification_intent_id TEXT NOT NULL,
    alert_id TEXT NOT NULL,
    recipient_principal_id TEXT NULL,
    destination_ref TEXT NOT NULL,
    channel_class TEXT NOT NULL CHECK (channel_class='whatsapp_business@1'),
    reason TEXT NOT NULL CHECK (
      reason IN ('alert_requires_attention','alert_action_requested','customer_awareness_required')
    ),
    payload_ref TEXT NOT NULL,
    payload_hash TEXT NOT NULL,
    visibility_requirement_id TEXT NULL,
    logical_action_id TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    created_by_principal_id TEXT NOT NULL,
    authority_snapshot JSONB NOT NULL,
    max_attempts INTEGER NOT NULL DEFAULT 3 CHECK (max_attempts BETWEEN 1 AND 3),
    created_at TIMESTAMPTZ NOT NULL DEFAULT transaction_timestamp(),
    PRIMARY KEY (tenant_id,notification_intent_id),
    UNIQUE (tenant_id,logical_action_id),
    FOREIGN KEY (tenant_id,alert_id) REFERENCES alerting.alert(tenant_id,alert_id),
    FOREIGN KEY (tenant_id,visibility_requirement_id)
      REFERENCES human_operations.visibility_requirement(tenant_id,visibility_requirement_id),
    CHECK (tenant_id<>'' AND alert_id<>''),
    CHECK (destination_ref<>'' AND length(destination_ref)<=512),
    CHECK (payload_ref<>'' AND length(payload_ref)<=512),
    CHECK (payload_hash<>'' AND length(payload_hash)<=128),
    CHECK (logical_action_id<>'' AND content_hash<>''),
    CHECK (created_by_principal_id<>''),
    CHECK (jsonb_typeof(authority_snapshot)='object')
);

CREATE TABLE notification.notification_attempt (
    tenant_id TEXT NOT NULL,
    notification_attempt_id TEXT NOT NULL,
    notification_intent_id TEXT NOT NULL,
    attempt_number INTEGER NOT NULL CHECK (attempt_number BETWEEN 1 AND 3),
    dispatch_identity TEXT NOT NULL,
    adapter_version TEXT NOT NULL,
    request_evidence JSONB NOT NULL,
    attempt_state TEXT NOT NULL CHECK (
      attempt_state IN ('dispatching','sent','provider_accepted','delivered','failed','unknown')
    ),
    provider_message_ref TEXT NULL,
    failure_class TEXT NULL,
    started_at TIMESTAMPTZ NOT NULL DEFAULT transaction_timestamp(),
    completed_at TIMESTAMPTZ NULL,
    PRIMARY KEY (tenant_id,notification_attempt_id),
    UNIQUE (tenant_id,notification_intent_id,attempt_number),
    UNIQUE (tenant_id,dispatch_identity),
    FOREIGN KEY (tenant_id,notification_intent_id)
      REFERENCES notification.notification_intent(tenant_id,notification_intent_id),
    CHECK (dispatch_identity<>'' AND adapter_version<>''),
    CHECK (jsonb_typeof(request_evidence)='object'),
    CHECK (
      (attempt_state='dispatching' AND completed_at IS NULL AND failure_class IS NULL)
      OR
      (attempt_state IN ('sent','provider_accepted','delivered') AND completed_at IS NOT NULL AND failure_class IS NULL)
      OR
      (attempt_state IN ('failed','unknown') AND completed_at IS NOT NULL)
    )
);

CREATE TABLE notification.notification_provider_evidence (
    tenant_id TEXT NOT NULL,
    provider_evidence_id TEXT NOT NULL,
    notification_intent_id TEXT NOT NULL,
    notification_attempt_id TEXT NULL,
    evidence_kind TEXT NOT NULL CHECK (
      evidence_kind IN ('provider_accepted','delivered','external_read_observed','failed','unknown')
    ),
    provider_message_ref TEXT NULL,
    provider_callback_ref TEXT NULL,
    evidence_envelope JSONB NOT NULL,
    provider_observed_at TIMESTAMPTZ NULL,
    observed_at TIMESTAMPTZ NOT NULL DEFAULT transaction_timestamp(),
    PRIMARY KEY (tenant_id,provider_evidence_id),
    FOREIGN KEY (tenant_id,notification_intent_id)
      REFERENCES notification.notification_intent(tenant_id,notification_intent_id),
    FOREIGN KEY (tenant_id,notification_attempt_id)
      REFERENCES notification.notification_attempt(tenant_id,notification_attempt_id),
    CHECK (jsonb_typeof(evidence_envelope)='object')
);

CREATE TABLE notification.notification_projection (
    tenant_id TEXT NOT NULL,
    notification_intent_id TEXT NOT NULL,
    delivery_state TEXT NOT NULL CHECK (
      delivery_state IN ('unknown','dispatching','sent','provider_accepted','delivered','failed')
    ),
    latest_attempt_id TEXT NULL,
    latest_provider_evidence_id TEXT NULL,
    external_read_observed BOOLEAN NOT NULL DEFAULT FALSE,
    retry_required BOOLEAN NOT NULL DEFAULT FALSE,
    reconciliation_required BOOLEAN NOT NULL DEFAULT FALSE,
    fallback_action_required BOOLEAN NOT NULL DEFAULT FALSE,
    fallback_reason TEXT NULL CHECK (
      fallback_reason IS NULL OR fallback_reason IN (
        'retry_budget_exhausted','authoritative_awareness_missing'
      )
    ),
    projection_revision BIGINT NOT NULL CHECK (projection_revision>0),
    projected_at TIMESTAMPTZ NOT NULL DEFAULT transaction_timestamp(),
    PRIMARY KEY (tenant_id,notification_intent_id),
    FOREIGN KEY (tenant_id,notification_intent_id)
      REFERENCES notification.notification_intent(tenant_id,notification_intent_id)
);

CREATE TABLE notification.notification_dispatch_outbox (
    tenant_id TEXT NOT NULL,
    dispatch_outbox_id TEXT NOT NULL,
    notification_intent_id TEXT NOT NULL,
    attempt_number INTEGER NOT NULL CHECK (attempt_number BETWEEN 1 AND 3),
    state TEXT NOT NULL CHECK (
      state IN ('admitted','processing','succeeded','failed','reconciliation_required')
    ),
    available_at TIMESTAMPTZ NOT NULL DEFAULT transaction_timestamp(),
    executor_id TEXT NULL,
    claim_expires_at TIMESTAMPTZ NULL,
    execution_generation BIGINT NOT NULL DEFAULT 0 CHECK (execution_generation>=0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT transaction_timestamp(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT transaction_timestamp(),
    PRIMARY KEY (tenant_id,dispatch_outbox_id),
    UNIQUE (tenant_id,notification_intent_id,attempt_number),
    FOREIGN KEY (tenant_id,notification_intent_id)
      REFERENCES notification.notification_intent(tenant_id,notification_intent_id),
    CHECK (
      (state='processing' AND executor_id IS NOT NULL AND claim_expires_at IS NOT NULL)
      OR
      (state<>'processing' AND claim_expires_at IS NULL)
    )
);

CREATE TABLE notification.notification_callback_inbox (
    tenant_id TEXT NOT NULL,
    callback_inbox_id TEXT NOT NULL,
    provider_callback_ref TEXT NOT NULL,
    provider_message_ref TEXT NOT NULL,
    payload_hash TEXT NOT NULL,
    evidence_kind TEXT NOT NULL CHECK (
      evidence_kind IN ('provider_accepted','delivered','external_read_observed','failed','unknown')
    ),
    authentication_evidence JSONB NOT NULL,
    bounded_payload JSONB NOT NULL,
    provider_observed_at TIMESTAMPTZ NULL,
    received_at TIMESTAMPTZ NOT NULL DEFAULT transaction_timestamp(),
    processed_at TIMESTAMPTZ NULL,
    state TEXT NOT NULL CHECK (state IN ('admitted','processed','quarantined')),
    quarantine_reason TEXT NULL,
    PRIMARY KEY (tenant_id,callback_inbox_id),
    UNIQUE (tenant_id,provider_callback_ref),
    CHECK (provider_callback_ref<>'' AND provider_message_ref<>''),
    CHECK (payload_hash<>'' AND length(payload_hash)<=128),
    CHECK (jsonb_typeof(authentication_evidence)='object'),
    CHECK (jsonb_typeof(bounded_payload)='object'),
    CHECK (
      (state='admitted' AND processed_at IS NULL AND quarantine_reason IS NULL)
      OR
      (state='processed' AND processed_at IS NOT NULL AND quarantine_reason IS NULL)
      OR
      (state='quarantined' AND processed_at IS NOT NULL AND quarantine_reason IS NOT NULL)
    )
);

ALTER TABLE notification.notification_intent ENABLE ROW LEVEL SECURITY;
ALTER TABLE notification.notification_intent FORCE ROW LEVEL SECURITY;
ALTER TABLE notification.notification_attempt ENABLE ROW LEVEL SECURITY;
ALTER TABLE notification.notification_attempt FORCE ROW LEVEL SECURITY;
ALTER TABLE notification.notification_provider_evidence ENABLE ROW LEVEL SECURITY;
ALTER TABLE notification.notification_provider_evidence FORCE ROW LEVEL SECURITY;
ALTER TABLE notification.notification_projection ENABLE ROW LEVEL SECURITY;
ALTER TABLE notification.notification_projection FORCE ROW LEVEL SECURITY;
ALTER TABLE notification.notification_dispatch_outbox ENABLE ROW LEVEL SECURITY;
ALTER TABLE notification.notification_dispatch_outbox FORCE ROW LEVEL SECURITY;
ALTER TABLE notification.notification_callback_inbox ENABLE ROW LEVEL SECURITY;
ALTER TABLE notification.notification_callback_inbox FORCE ROW LEVEL SECURITY;

CREATE POLICY g9_intent_tenant ON notification.notification_intent
USING (tenant_id=NULLIF(current_setting('jlmirror.tenant_id',true),''))
WITH CHECK (tenant_id=NULLIF(current_setting('jlmirror.tenant_id',true),''));
CREATE POLICY g9_attempt_tenant ON notification.notification_attempt
USING (tenant_id=NULLIF(current_setting('jlmirror.tenant_id',true),''))
WITH CHECK (tenant_id=NULLIF(current_setting('jlmirror.tenant_id',true),''));
CREATE POLICY g9_provider_evidence_tenant ON notification.notification_provider_evidence
USING (tenant_id=NULLIF(current_setting('jlmirror.tenant_id',true),''))
WITH CHECK (tenant_id=NULLIF(current_setting('jlmirror.tenant_id',true),''));
CREATE POLICY g9_projection_tenant ON notification.notification_projection
USING (tenant_id=NULLIF(current_setting('jlmirror.tenant_id',true),''))
WITH CHECK (tenant_id=NULLIF(current_setting('jlmirror.tenant_id',true),''));
CREATE POLICY g9_dispatch_outbox_tenant ON notification.notification_dispatch_outbox
USING (tenant_id=NULLIF(current_setting('jlmirror.tenant_id',true),''))
WITH CHECK (tenant_id=NULLIF(current_setting('jlmirror.tenant_id',true),''));
CREATE POLICY g9_callback_inbox_tenant ON notification.notification_callback_inbox
USING (tenant_id=NULLIF(current_setting('jlmirror.tenant_id',true),''))
WITH CHECK (tenant_id=NULLIF(current_setting('jlmirror.tenant_id',true),''));

REVOKE ALL ON
  notification.notification_intent,
  notification.notification_attempt,
  notification.notification_provider_evidence,
  notification.notification_projection,
  notification.notification_dispatch_outbox,
  notification.notification_callback_inbox
FROM PUBLIC,
  jlmirror_g9_notification_app_invoker,
  jlmirror_g9_notification_worker_invoker,
  jlmirror_g9_notification_callback_invoker;

GRANT SELECT,INSERT ON notification.notification_intent TO jlmirror_g9_notification_executor;
GRANT SELECT,INSERT,UPDATE ON notification.notification_attempt TO jlmirror_g9_notification_executor;
GRANT SELECT,INSERT ON notification.notification_provider_evidence TO jlmirror_g9_notification_executor;
GRANT SELECT,INSERT,UPDATE ON notification.notification_projection TO jlmirror_g9_notification_executor;
GRANT SELECT,INSERT,UPDATE ON notification.notification_dispatch_outbox TO jlmirror_g9_notification_executor;
GRANT SELECT,INSERT,UPDATE ON notification.notification_callback_inbox TO jlmirror_g9_notification_executor;
GRANT SELECT ON alerting.alert TO jlmirror_g9_notification_executor;
GRANT SELECT ON human_operations.visibility_requirement,human_operations.visibility_receipt
TO jlmirror_g9_notification_executor;

CREATE OR REPLACE FUNCTION notification.g9_reject_immutable_mutation()
RETURNS trigger
LANGUAGE plpgsql SECURITY INVOKER
SET search_path=pg_catalog,notification
AS $$
BEGIN
  RAISE EXCEPTION 'g9.immutable_fact';
END;
$$;

CREATE TRIGGER g9_intent_immutable
BEFORE UPDATE OR DELETE ON notification.notification_intent
FOR EACH ROW EXECUTE FUNCTION notification.g9_reject_immutable_mutation();

CREATE TRIGGER g9_provider_evidence_immutable
BEFORE UPDATE OR DELETE ON notification.notification_provider_evidence
FOR EACH ROW EXECUTE FUNCTION notification.g9_reject_immutable_mutation();

CREATE OR REPLACE FUNCTION notification.g9_guard_attempt_terminal_transition()
RETURNS trigger
LANGUAGE plpgsql SECURITY INVOKER
SET search_path=pg_catalog,notification
AS $$
BEGIN
  IF TG_OP='DELETE' THEN RAISE EXCEPTION 'g9.attempt_delete_forbidden'; END IF;
  IF OLD.attempt_state<>'dispatching' THEN
    RAISE EXCEPTION 'g9.attempt_terminal';
  END IF;
  IF NEW.tenant_id IS DISTINCT FROM OLD.tenant_id
     OR NEW.notification_attempt_id IS DISTINCT FROM OLD.notification_attempt_id
     OR NEW.notification_intent_id IS DISTINCT FROM OLD.notification_intent_id
     OR NEW.attempt_number IS DISTINCT FROM OLD.attempt_number
     OR NEW.dispatch_identity IS DISTINCT FROM OLD.dispatch_identity
     OR NEW.adapter_version IS DISTINCT FROM OLD.adapter_version
     OR NEW.request_evidence IS DISTINCT FROM OLD.request_evidence
     OR NEW.started_at IS DISTINCT FROM OLD.started_at
     OR NEW.attempt_state='dispatching'
     OR NEW.completed_at IS NULL THEN
    RAISE EXCEPTION 'g9.attempt_transition_invalid';
  END IF;
  RETURN NEW;
END;
$$;

CREATE TRIGGER g9_attempt_guard
BEFORE UPDATE OR DELETE ON notification.notification_attempt
FOR EACH ROW EXECUTE FUNCTION notification.g9_guard_attempt_terminal_transition();

CREATE OR REPLACE FUNCTION notification.g9_validate_authority(
  p_tenant_id TEXT,p_actor_principal_id TEXT,p_authority_snapshot JSONB
) RETURNS VOID
LANGUAGE plpgsql SECURITY INVOKER
SET search_path=pg_catalog,notification
AS $$
BEGIN
  IF jsonb_typeof(p_authority_snapshot)<>'object'
     OR COALESCE((p_authority_snapshot->>'current')::BOOLEAN,FALSE) IS NOT TRUE
     OR p_authority_snapshot->>'tenant_id' IS DISTINCT FROM p_tenant_id
     OR p_authority_snapshot->>'principal_id' IS DISTINCT FROM p_actor_principal_id
     OR COALESCE(p_authority_snapshot->>'action','')=''
     OR COALESCE(p_authority_snapshot->>'policy_revision','')='' THEN
    RAISE EXCEPTION 'g9.current_authority_required';
  END IF;
END;
$$;

CREATE OR REPLACE FUNCTION notification.g9_refresh_projection(
  p_tenant_id TEXT,p_intent_id TEXT
) RETURNS VOID
LANGUAGE plpgsql SECURITY INVOKER
SET search_path=pg_catalog,notification,human_operations
AS $$
DECLARE
  v_attempt notification.notification_attempt%ROWTYPE;
  v_evidence notification.notification_provider_evidence%ROWTYPE;
  v_intent notification.notification_intent%ROWTYPE;
  v_state TEXT:='unknown';
  v_external_read BOOLEAN:=FALSE;
  v_retry BOOLEAN:=FALSE;
  v_reconcile BOOLEAN:=FALSE;
  v_fallback BOOLEAN:=FALSE;
  v_fallback_reason TEXT:=NULL;
  v_revision BIGINT;
BEGIN
  SELECT * INTO v_intent FROM notification.notification_intent
   WHERE tenant_id=p_tenant_id AND notification_intent_id=p_intent_id;
  IF NOT FOUND THEN RAISE EXCEPTION 'g9.intent_missing'; END IF;

  SELECT * INTO v_attempt FROM notification.notification_attempt
   WHERE tenant_id=p_tenant_id AND notification_intent_id=p_intent_id
   ORDER BY attempt_number DESC LIMIT 1;

  SELECT * INTO v_evidence FROM notification.notification_provider_evidence
   WHERE tenant_id=p_tenant_id AND notification_intent_id=p_intent_id
   ORDER BY observed_at DESC,provider_evidence_id DESC LIMIT 1;

  SELECT EXISTS(
    SELECT 1 FROM notification.notification_provider_evidence
    WHERE tenant_id=p_tenant_id AND notification_intent_id=p_intent_id
      AND evidence_kind='external_read_observed'
  ) INTO v_external_read;

  IF EXISTS (
    SELECT 1 FROM notification.notification_provider_evidence
    WHERE tenant_id=p_tenant_id AND notification_intent_id=p_intent_id
      AND evidence_kind='delivered'
  ) THEN
    v_state:='delivered';
  ELSIF EXISTS (
    SELECT 1 FROM notification.notification_provider_evidence
    WHERE tenant_id=p_tenant_id AND notification_intent_id=p_intent_id
      AND evidence_kind='provider_accepted'
  ) THEN
    v_state:='provider_accepted';
  ELSIF v_evidence.evidence_kind='failed' THEN
    v_state:='failed';
  ELSIF v_evidence.evidence_kind='unknown' THEN
    v_state:='unknown';
  ELSIF v_attempt.attempt_state IN ('sent','provider_accepted','delivered','failed','unknown','dispatching') THEN
    v_state:=CASE WHEN v_attempt.attempt_state='unknown' THEN 'unknown' ELSE v_attempt.attempt_state END;
  END IF;

  IF v_attempt.notification_attempt_id IS NOT NULL THEN
    v_retry:=v_state IN ('failed','unknown') AND v_attempt.attempt_number<v_intent.max_attempts;
    v_reconcile:=v_state='unknown';
    v_fallback:=(
      v_state IN ('failed','unknown') AND v_attempt.attempt_number>=v_intent.max_attempts
    );
    IF v_fallback THEN
      v_fallback_reason:='retry_budget_exhausted';
    END IF;
  END IF;

  IF v_intent.visibility_requirement_id IS NOT NULL
     AND NOT EXISTS (
       SELECT 1 FROM human_operations.visibility_receipt vr
       WHERE vr.tenant_id=p_tenant_id
         AND vr.visibility_requirement_id=v_intent.visibility_requirement_id
     ) AND v_state='delivered' THEN
    v_fallback:=TRUE;
    v_fallback_reason:='authoritative_awareness_missing';
  END IF;

  SELECT COALESCE(projection_revision,0)+1 INTO v_revision
  FROM notification.notification_projection
  WHERE tenant_id=p_tenant_id AND notification_intent_id=p_intent_id;
  v_revision:=COALESCE(v_revision,1);

  INSERT INTO notification.notification_projection(
    tenant_id,notification_intent_id,delivery_state,latest_attempt_id,
    latest_provider_evidence_id,external_read_observed,retry_required,
    reconciliation_required,fallback_action_required,fallback_reason,
    projection_revision,projected_at
  ) VALUES (
    p_tenant_id,p_intent_id,v_state,v_attempt.notification_attempt_id,
    v_evidence.provider_evidence_id,v_external_read,v_retry,
    v_reconcile,v_fallback,v_fallback_reason,v_revision,transaction_timestamp()
  )
  ON CONFLICT (tenant_id,notification_intent_id) DO UPDATE SET
    delivery_state=EXCLUDED.delivery_state,
    latest_attempt_id=EXCLUDED.latest_attempt_id,
    latest_provider_evidence_id=EXCLUDED.latest_provider_evidence_id,
    external_read_observed=EXCLUDED.external_read_observed,
    retry_required=EXCLUDED.retry_required,
    reconciliation_required=EXCLUDED.reconciliation_required,
    fallback_action_required=EXCLUDED.fallback_action_required,
    fallback_reason=EXCLUDED.fallback_reason,
    projection_revision=EXCLUDED.projection_revision,
    projected_at=EXCLUDED.projected_at;
END;
$$;

CREATE OR REPLACE FUNCTION notification.g9_create_intent(
  p_tenant_id TEXT,p_alert_id TEXT,p_recipient_principal_id TEXT,
  p_destination_ref TEXT,p_channel_class TEXT,p_reason TEXT,
  p_payload_ref TEXT,p_payload_hash TEXT,p_visibility_requirement_id TEXT,
  p_actor_principal_id TEXT,p_logical_action_id TEXT,p_authority_snapshot JSONB
) RETURNS JSONB
LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,notification,alerting,human_operations
AS $$
DECLARE
  v_id TEXT;
  v_hash TEXT;
  v_existing notification.notification_intent%ROWTYPE;
  v_outbox_id TEXT;
BEGIN
  PERFORM notification.g9_validate_authority(p_tenant_id,p_actor_principal_id,p_authority_snapshot);
  IF p_channel_class<>'whatsapp_business@1'
     OR p_reason NOT IN ('alert_requires_attention','alert_action_requested','customer_awareness_required')
     OR COALESCE(p_destination_ref,'')='' OR length(p_destination_ref)>512
     OR COALESCE(p_payload_ref,'')='' OR length(p_payload_ref)>512
     OR COALESCE(p_payload_hash,'')='' OR length(p_payload_hash)>128
     OR COALESCE(p_logical_action_id,'')='' THEN
    RAISE EXCEPTION 'g9.intent_input_invalid';
  END IF;

  PERFORM set_config('jlmirror.tenant_id',p_tenant_id,true);
  PERFORM 1 FROM alerting.alert
   WHERE tenant_id=p_tenant_id AND alert_id=p_alert_id AND lifecycle_state='active';
  IF NOT FOUND THEN RAISE EXCEPTION 'g9.active_alert_required'; END IF;

  IF p_visibility_requirement_id IS NOT NULL THEN
    PERFORM 1 FROM human_operations.visibility_requirement
     WHERE tenant_id=p_tenant_id
       AND visibility_requirement_id=p_visibility_requirement_id
       AND alert_id=p_alert_id;
    IF NOT FOUND THEN RAISE EXCEPTION 'g9.visibility_requirement_binding_invalid'; END IF;
  END IF;

  v_hash:=md5(concat_ws(chr(31),p_alert_id,COALESCE(p_recipient_principal_id,''),
    p_destination_ref,p_channel_class,p_reason,p_payload_ref,p_payload_hash,
    COALESCE(p_visibility_requirement_id,''),p_actor_principal_id));
  v_id:='g9-intent:'||md5(p_tenant_id||chr(31)||p_logical_action_id);

  SELECT * INTO v_existing FROM notification.notification_intent
   WHERE tenant_id=p_tenant_id AND logical_action_id=p_logical_action_id;
  IF FOUND THEN
    IF v_existing.content_hash<>v_hash THEN RAISE EXCEPTION 'g9.intent_equivalence_conflict'; END IF;
    RETURN jsonb_build_object('notification_intent_id',v_existing.notification_intent_id,'duplicate',TRUE);
  END IF;

  INSERT INTO notification.notification_intent(
    tenant_id,notification_intent_id,alert_id,recipient_principal_id,destination_ref,
    channel_class,reason,payload_ref,payload_hash,visibility_requirement_id,
    logical_action_id,content_hash,created_by_principal_id,authority_snapshot
  ) VALUES (
    p_tenant_id,v_id,p_alert_id,p_recipient_principal_id,p_destination_ref,
    p_channel_class,p_reason,p_payload_ref,p_payload_hash,p_visibility_requirement_id,
    p_logical_action_id,v_hash,p_actor_principal_id,p_authority_snapshot
  );

  v_outbox_id:='g9-outbox:'||md5(p_tenant_id||chr(31)||v_id||chr(31)||'1');
  INSERT INTO notification.notification_dispatch_outbox(
    tenant_id,dispatch_outbox_id,notification_intent_id,attempt_number,state
  ) VALUES (p_tenant_id,v_outbox_id,v_id,1,'admitted');

  PERFORM notification.g9_refresh_projection(p_tenant_id,v_id);
  RETURN jsonb_build_object('notification_intent_id',v_id,'duplicate',FALSE);
END;
$$;

CREATE OR REPLACE FUNCTION notification.g9_next_dispatch_candidate(
  p_tenant_id TEXT
) RETURNS JSONB
LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,notification
AS $
DECLARE v_result JSONB;
BEGIN
  PERFORM set_config('jlmirror.tenant_id',p_tenant_id,true);
  SELECT to_jsonb(x) INTO v_result FROM (
    SELECT o.dispatch_outbox_id,o.notification_intent_id,o.attempt_number,
           i.alert_id,i.recipient_principal_id,i.destination_ref,i.channel_class,
           i.reason,i.payload_ref,i.payload_hash,i.visibility_requirement_id
    FROM notification.notification_dispatch_outbox o
    JOIN notification.notification_intent i
      ON i.tenant_id=o.tenant_id
     AND i.notification_intent_id=o.notification_intent_id
    WHERE o.tenant_id=p_tenant_id
      AND o.state='admitted'
      AND o.available_at<=transaction_timestamp()
    ORDER BY o.available_at,o.created_at,o.dispatch_outbox_id
    LIMIT 1
  ) x;
  RETURN v_result;
END;
$;

CREATE OR REPLACE FUNCTION notification.g9_claim_dispatch(
  p_tenant_id TEXT,p_outbox_id TEXT,p_executor_id TEXT,p_claim_seconds INTEGER,
  p_adapter_version TEXT,p_request_evidence JSONB
) RETURNS JSONB
LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,notification
AS $$
DECLARE
  v_outbox notification.notification_dispatch_outbox%ROWTYPE;
  v_attempt notification.notification_attempt%ROWTYPE;
  v_attempt_id TEXT;
  v_dispatch_identity TEXT;
BEGIN
  IF COALESCE(p_executor_id,'')='' OR p_claim_seconds<1 OR p_claim_seconds>300
     OR COALESCE(p_adapter_version,'')=''
     OR jsonb_typeof(p_request_evidence)<>'object' THEN
    RAISE EXCEPTION 'g9.dispatch_claim_input_invalid';
  END IF;
  PERFORM set_config('jlmirror.tenant_id',p_tenant_id,true);

  SELECT * INTO v_outbox FROM notification.notification_dispatch_outbox
   WHERE tenant_id=p_tenant_id AND dispatch_outbox_id=p_outbox_id
   FOR UPDATE;
  IF NOT FOUND THEN RAISE EXCEPTION 'g9.dispatch_outbox_missing'; END IF;

  IF v_outbox.state='processing' AND v_outbox.claim_expires_at<=transaction_timestamp() THEN
    UPDATE notification.notification_dispatch_outbox
       SET state='reconciliation_required',executor_id=NULL,claim_expires_at=NULL,
           updated_at=transaction_timestamp()
     WHERE tenant_id=p_tenant_id AND dispatch_outbox_id=p_outbox_id;
    RETURN jsonb_build_object('state','reconciliation_required','duplicate',FALSE);
  END IF;

  IF v_outbox.state IN ('processing','succeeded','failed') THEN
    SELECT * INTO v_attempt FROM notification.notification_attempt
     WHERE tenant_id=p_tenant_id
       AND notification_intent_id=v_outbox.notification_intent_id
       AND attempt_number=v_outbox.attempt_number;
    IF FOUND AND (
      v_attempt.adapter_version IS DISTINCT FROM p_adapter_version
      OR v_attempt.request_evidence IS DISTINCT FROM p_request_evidence
    ) THEN
      RAISE EXCEPTION 'g9.dispatch_claim_equivalence_conflict';
    END IF;
    RETURN jsonb_build_object('state',v_outbox.state,'duplicate',TRUE);
  END IF;
  IF v_outbox.state<>'admitted' THEN
    RETURN jsonb_build_object('state',v_outbox.state,'duplicate',TRUE);
  END IF;
  IF v_outbox.available_at>transaction_timestamp() THEN
    RETURN jsonb_build_object('state','not_ready','duplicate',TRUE);
  END IF;

  v_attempt_id:='g9-attempt:'||md5(
    p_tenant_id||chr(31)||v_outbox.notification_intent_id||chr(31)||v_outbox.attempt_number::TEXT
  );
  v_dispatch_identity:='g9-dispatch:'||md5(
    p_tenant_id||chr(31)||v_outbox.notification_intent_id||chr(31)||v_outbox.attempt_number::TEXT
  );

  INSERT INTO notification.notification_attempt(
    tenant_id,notification_attempt_id,notification_intent_id,attempt_number,
    dispatch_identity,adapter_version,request_evidence,attempt_state
  ) VALUES (
    p_tenant_id,v_attempt_id,v_outbox.notification_intent_id,v_outbox.attempt_number,
    v_dispatch_identity,p_adapter_version,p_request_evidence,'dispatching'
  )
  ON CONFLICT (tenant_id,notification_intent_id,attempt_number) DO NOTHING;

  UPDATE notification.notification_dispatch_outbox
     SET state='processing',executor_id=p_executor_id,
         claim_expires_at=transaction_timestamp()+make_interval(secs=>p_claim_seconds),
         execution_generation=execution_generation+1,updated_at=transaction_timestamp()
   WHERE tenant_id=p_tenant_id AND dispatch_outbox_id=p_outbox_id;

  PERFORM notification.g9_refresh_projection(p_tenant_id,v_outbox.notification_intent_id);
  RETURN jsonb_build_object(
    'state','processing','notification_attempt_id',v_attempt_id,
    'notification_intent_id',v_outbox.notification_intent_id,
    'attempt_number',v_outbox.attempt_number,'duplicate',FALSE
  );
END;
$$;

CREATE OR REPLACE FUNCTION notification.g9_complete_dispatch(
  p_tenant_id TEXT,p_outbox_id TEXT,p_executor_id TEXT,
  p_attempt_state TEXT,p_provider_message_ref TEXT,p_failure_class TEXT
) RETURNS JSONB
LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,notification
AS $$
DECLARE
  v_outbox notification.notification_dispatch_outbox%ROWTYPE;
  v_attempt notification.notification_attempt%ROWTYPE;
BEGIN
  IF p_attempt_state NOT IN ('sent','provider_accepted','delivered','failed','unknown') THEN
    RAISE EXCEPTION 'g9.dispatch_completion_state_invalid';
  END IF;
  IF p_attempt_state IN ('sent','provider_accepted','delivered') AND p_failure_class IS NOT NULL THEN
    RAISE EXCEPTION 'g9.dispatch_failure_class_invalid';
  END IF;
  PERFORM set_config('jlmirror.tenant_id',p_tenant_id,true);

  SELECT * INTO v_outbox FROM notification.notification_dispatch_outbox
   WHERE tenant_id=p_tenant_id AND dispatch_outbox_id=p_outbox_id
   FOR UPDATE;
  IF NOT FOUND THEN RAISE EXCEPTION 'g9.dispatch_outbox_missing'; END IF;
  IF v_outbox.state='succeeded' OR v_outbox.state='failed' THEN
    SELECT * INTO v_attempt FROM notification.notification_attempt
     WHERE tenant_id=p_tenant_id
       AND notification_intent_id=v_outbox.notification_intent_id
       AND attempt_number=v_outbox.attempt_number;
    IF NOT FOUND
       OR v_attempt.attempt_state IS DISTINCT FROM p_attempt_state
       OR v_attempt.provider_message_ref IS DISTINCT FROM p_provider_message_ref
       OR v_attempt.failure_class IS DISTINCT FROM p_failure_class THEN
      RAISE EXCEPTION 'g9.dispatch_completion_equivalence_conflict';
    END IF;
    RETURN jsonb_build_object('state',v_outbox.state,'duplicate',TRUE);
  END IF;
  IF v_outbox.state<>'processing' OR v_outbox.executor_id<>p_executor_id
     OR v_outbox.claim_expires_at<=transaction_timestamp() THEN
    RAISE EXCEPTION 'g9.dispatch_claim_lost';
  END IF;

  SELECT * INTO v_attempt FROM notification.notification_attempt
   WHERE tenant_id=p_tenant_id
     AND notification_intent_id=v_outbox.notification_intent_id
     AND attempt_number=v_outbox.attempt_number
   FOR UPDATE;
  IF NOT FOUND OR v_attempt.attempt_state<>'dispatching' THEN
    RAISE EXCEPTION 'g9.dispatch_attempt_missing_or_terminal';
  END IF;

  UPDATE notification.notification_attempt
     SET attempt_state=p_attempt_state,provider_message_ref=p_provider_message_ref,
         failure_class=p_failure_class,completed_at=transaction_timestamp()
   WHERE tenant_id=p_tenant_id AND notification_attempt_id=v_attempt.notification_attempt_id;

  UPDATE notification.notification_dispatch_outbox
     SET state=CASE WHEN p_attempt_state IN ('failed','unknown') THEN 'failed' ELSE 'succeeded' END,
         executor_id=NULL,claim_expires_at=NULL,updated_at=transaction_timestamp()
   WHERE tenant_id=p_tenant_id AND dispatch_outbox_id=p_outbox_id;

  PERFORM notification.g9_refresh_projection(p_tenant_id,v_outbox.notification_intent_id);
  RETURN jsonb_build_object(
    'state',p_attempt_state,'notification_attempt_id',v_attempt.notification_attempt_id,
    'duplicate',FALSE
  );
END;
$$;

CREATE OR REPLACE FUNCTION notification.g9_record_provider_callback(
  p_tenant_id TEXT,p_callback_ref TEXT,p_provider_message_ref TEXT,
  p_payload_hash TEXT,p_evidence_kind TEXT,p_authentication_evidence JSONB,
  p_bounded_payload JSONB,p_provider_observed_at TIMESTAMPTZ
) RETURNS JSONB
LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,notification
AS $$
DECLARE
  v_attempt notification.notification_attempt%ROWTYPE;
  v_callback_id TEXT;
  v_evidence_id TEXT;
  v_existing notification.notification_callback_inbox%ROWTYPE;
BEGIN
  IF p_evidence_kind NOT IN ('provider_accepted','delivered','external_read_observed','failed','unknown')
     OR COALESCE(p_callback_ref,'')='' OR COALESCE(p_provider_message_ref,'')=''
     OR COALESCE(p_payload_hash,'')='' OR length(p_payload_hash)>128
     OR jsonb_typeof(p_authentication_evidence)<>'object'
     OR COALESCE((p_authentication_evidence->>'verified')::BOOLEAN,FALSE) IS NOT TRUE
     OR COALESCE(p_authentication_evidence->>'trusted_route_ref','')=''
     OR jsonb_typeof(p_bounded_payload)<>'object'
     OR octet_length(convert_to(p_bounded_payload::TEXT,'UTF8'))>16384 THEN
    RAISE EXCEPTION 'g9.callback_admission_invalid';
  END IF;

  PERFORM set_config('jlmirror.tenant_id',p_tenant_id,true);
  v_callback_id:='g9-callback:'||md5(p_tenant_id||chr(31)||p_callback_ref);

  SELECT * INTO v_existing FROM notification.notification_callback_inbox
   WHERE tenant_id=p_tenant_id AND provider_callback_ref=p_callback_ref;
  IF FOUND THEN
    IF v_existing.payload_hash<>p_payload_hash
       OR v_existing.provider_message_ref<>p_provider_message_ref
       OR v_existing.evidence_kind<>p_evidence_kind THEN
      RAISE EXCEPTION 'g9.callback_equivalence_conflict';
    END IF;
    RETURN jsonb_build_object('callback_inbox_id',v_existing.callback_inbox_id,'duplicate',TRUE);
  END IF;

  SELECT * INTO v_attempt FROM notification.notification_attempt
   WHERE tenant_id=p_tenant_id AND provider_message_ref=p_provider_message_ref
   ORDER BY attempt_number DESC LIMIT 1;
  IF NOT FOUND THEN
    INSERT INTO notification.notification_callback_inbox(
      tenant_id,callback_inbox_id,provider_callback_ref,provider_message_ref,payload_hash,
      evidence_kind,authentication_evidence,bounded_payload,provider_observed_at,
      processed_at,state,quarantine_reason
    ) VALUES (
      p_tenant_id,v_callback_id,p_callback_ref,p_provider_message_ref,p_payload_hash,
      p_evidence_kind,p_authentication_evidence,p_bounded_payload,p_provider_observed_at,
      transaction_timestamp(),'quarantined','provider_message_unbound'
    );
    RETURN jsonb_build_object('callback_inbox_id',v_callback_id,'state','quarantined','duplicate',FALSE);
  END IF;

  INSERT INTO notification.notification_callback_inbox(
    tenant_id,callback_inbox_id,provider_callback_ref,provider_message_ref,payload_hash,
    evidence_kind,authentication_evidence,bounded_payload,provider_observed_at,
    processed_at,state
  ) VALUES (
    p_tenant_id,v_callback_id,p_callback_ref,p_provider_message_ref,p_payload_hash,
    p_evidence_kind,p_authentication_evidence,p_bounded_payload,p_provider_observed_at,
    transaction_timestamp(),'processed'
  );

  v_evidence_id:='g9-provider-evidence:'||md5(p_tenant_id||chr(31)||p_callback_ref);
  INSERT INTO notification.notification_provider_evidence(
    tenant_id,provider_evidence_id,notification_intent_id,notification_attempt_id,
    evidence_kind,provider_message_ref,provider_callback_ref,evidence_envelope,
    provider_observed_at
  ) VALUES (
    p_tenant_id,v_evidence_id,v_attempt.notification_intent_id,v_attempt.notification_attempt_id,
    p_evidence_kind,p_provider_message_ref,p_callback_ref,
    jsonb_build_object(
      'authentication',p_authentication_evidence,
      'payload_hash',p_payload_hash,
      'bounded_payload',p_bounded_payload
    ),
    p_provider_observed_at
  );

  PERFORM notification.g9_refresh_projection(p_tenant_id,v_attempt.notification_intent_id);
  RETURN jsonb_build_object(
    'callback_inbox_id',v_callback_id,'provider_evidence_id',v_evidence_id,
    'state','processed','duplicate',FALSE
  );
END;
$$;

CREATE OR REPLACE FUNCTION notification.g9_reconcile_dispatch_claim(
  p_tenant_id TEXT,p_outbox_id TEXT
) RETURNS JSONB
LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,notification
AS $
DECLARE
  v_outbox notification.notification_dispatch_outbox%ROWTYPE;
  v_attempt notification.notification_attempt%ROWTYPE;
BEGIN
  PERFORM set_config('jlmirror.tenant_id',p_tenant_id,true);

  SELECT * INTO v_outbox FROM notification.notification_dispatch_outbox
   WHERE tenant_id=p_tenant_id AND dispatch_outbox_id=p_outbox_id
   FOR UPDATE;
  IF NOT FOUND THEN RAISE EXCEPTION 'g9.dispatch_outbox_missing'; END IF;

  IF v_outbox.state<>'reconciliation_required' THEN
    RETURN jsonb_build_object('reconciled',FALSE,'state',v_outbox.state);
  END IF;

  SELECT * INTO v_attempt FROM notification.notification_attempt
   WHERE tenant_id=p_tenant_id
     AND notification_intent_id=v_outbox.notification_intent_id
     AND attempt_number=v_outbox.attempt_number
   FOR UPDATE;
  IF NOT FOUND THEN
    RAISE EXCEPTION 'g9.reconciliation_attempt_missing';
  END IF;

  IF v_attempt.attempt_state='dispatching' THEN
    UPDATE notification.notification_attempt
       SET attempt_state='unknown',failure_class='lease_expired_outcome_unknown',
           completed_at=transaction_timestamp()
     WHERE tenant_id=p_tenant_id
       AND notification_attempt_id=v_attempt.notification_attempt_id;
  END IF;

  UPDATE notification.notification_dispatch_outbox
     SET state='failed',executor_id=NULL,claim_expires_at=NULL,
         updated_at=transaction_timestamp()
   WHERE tenant_id=p_tenant_id AND dispatch_outbox_id=p_outbox_id;

  PERFORM notification.g9_refresh_projection(p_tenant_id,v_outbox.notification_intent_id);
  RETURN jsonb_build_object(
    'reconciled',TRUE,'state','unknown',
    'notification_intent_id',v_outbox.notification_intent_id
  );
END;
$;

CREATE OR REPLACE FUNCTION notification.g9_schedule_retry(
  p_tenant_id TEXT,p_intent_id TEXT
) RETURNS JSONB
LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,notification
AS $
DECLARE
  v_intent notification.notification_intent%ROWTYPE;
  v_attempt notification.notification_attempt%ROWTYPE;
  v_projection notification.notification_projection%ROWTYPE;
  v_outbox_id TEXT;
BEGIN
  PERFORM set_config('jlmirror.tenant_id',p_tenant_id,true);
  PERFORM pg_advisory_xact_lock(hashtextextended(p_tenant_id||chr(31)||p_intent_id,0));

  SELECT * INTO v_intent FROM notification.notification_intent
   WHERE tenant_id=p_tenant_id AND notification_intent_id=p_intent_id;
  IF NOT FOUND THEN RAISE EXCEPTION 'g9.intent_missing'; END IF;

  SELECT * INTO v_attempt FROM notification.notification_attempt
   WHERE tenant_id=p_tenant_id AND notification_intent_id=p_intent_id
   ORDER BY attempt_number DESC LIMIT 1;
  IF NOT FOUND THEN RAISE EXCEPTION 'g9.retry_attempt_missing'; END IF;

  SELECT * INTO v_projection FROM notification.notification_projection
   WHERE tenant_id=p_tenant_id AND notification_intent_id=p_intent_id;
  IF NOT FOUND OR v_projection.retry_required IS NOT TRUE THEN
    RETURN jsonb_build_object('scheduled',FALSE,'reason','retry_not_required');
  END IF;

  IF v_attempt.attempt_number>=v_intent.max_attempts THEN
    RETURN jsonb_build_object('scheduled',FALSE,'reason','retry_budget_exhausted');
  END IF;

  IF EXISTS (
    SELECT 1 FROM notification.notification_provider_evidence
    WHERE tenant_id=p_tenant_id AND notification_intent_id=p_intent_id
      AND evidence_kind='delivered'
  ) THEN
    PERFORM notification.g9_refresh_projection(p_tenant_id,p_intent_id);
    RETURN jsonb_build_object('scheduled',FALSE,'reason','delivery_already_proven');
  END IF;

  v_outbox_id:='g9-outbox:'||md5(
    p_tenant_id||chr(31)||p_intent_id||chr(31)||(v_attempt.attempt_number+1)::TEXT
  );
  INSERT INTO notification.notification_dispatch_outbox(
    tenant_id,dispatch_outbox_id,notification_intent_id,attempt_number,state,available_at
  ) VALUES (
    p_tenant_id,v_outbox_id,p_intent_id,v_attempt.attempt_number+1,
    'admitted',transaction_timestamp()+make_interval(secs=>LEAST(300,5*(2^v_attempt.attempt_number)::INTEGER))
  )
  ON CONFLICT (tenant_id,notification_intent_id,attempt_number) DO NOTHING;

  RETURN jsonb_build_object(
    'scheduled',TRUE,'dispatch_outbox_id',v_outbox_id,
    'attempt_number',v_attempt.attempt_number+1
  );
END;
$;

CREATE OR REPLACE FUNCTION notification.g9_get_intent(
  p_tenant_id TEXT,p_intent_id TEXT
) RETURNS JSONB
LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,notification,human_operations
AS $$
DECLARE
  v_intent JSONB;
  v_projection JSONB;
  v_attempts JSONB;
  v_evidence JSONB;
  v_native_state TEXT:='not_linked';
  v_fallback_reason TEXT;
BEGIN
  PERFORM set_config('jlmirror.tenant_id',p_tenant_id,true);
  SELECT to_jsonb(x) INTO v_intent FROM (
    SELECT notification_intent_id,alert_id,recipient_principal_id,destination_ref,
           channel_class,reason,payload_ref,payload_hash,visibility_requirement_id,created_at
    FROM notification.notification_intent
    WHERE tenant_id=p_tenant_id AND notification_intent_id=p_intent_id
  ) x;
  IF v_intent IS NULL THEN RAISE EXCEPTION 'g9.intent_missing'; END IF;

  IF v_intent->>'visibility_requirement_id' IS NOT NULL THEN
    IF EXISTS (
      SELECT 1 FROM human_operations.visibility_receipt
      WHERE tenant_id=p_tenant_id
        AND visibility_requirement_id=v_intent->>'visibility_requirement_id'
    ) THEN v_native_state:='viewed';
    ELSE v_native_state:='not_viewed_yet';
    END IF;
  END IF;

  SELECT COALESCE(to_jsonb(x),'{}'::jsonb) INTO v_projection FROM (
    SELECT delivery_state,latest_attempt_id,latest_provider_evidence_id,
           external_read_observed,retry_required,reconciliation_required,
           fallback_action_required,fallback_reason,projection_revision,projected_at
    FROM notification.notification_projection
    WHERE tenant_id=p_tenant_id AND notification_intent_id=p_intent_id
  ) x;
  v_fallback_reason:=v_projection->>'fallback_reason';
  IF v_fallback_reason='authoritative_awareness_missing' AND v_native_state='viewed' THEN
    v_projection:=v_projection||jsonb_build_object(
      'fallback_action_required',FALSE,
      'fallback_reason',NULL
    );
  END IF;
  v_projection:=v_projection||jsonb_build_object('native_visibility_state',v_native_state);

  SELECT COALESCE(jsonb_agg(to_jsonb(x) ORDER BY attempt_number),'[]'::jsonb) INTO v_attempts FROM (
    SELECT notification_attempt_id,attempt_number,attempt_state,provider_message_ref,
           failure_class,started_at,completed_at
    FROM notification.notification_attempt
    WHERE tenant_id=p_tenant_id AND notification_intent_id=p_intent_id
  ) x;

  SELECT COALESCE(jsonb_agg(to_jsonb(x) ORDER BY observed_at),'[]'::jsonb) INTO v_evidence FROM (
    SELECT provider_evidence_id,evidence_kind,provider_message_ref,
           provider_callback_ref,provider_observed_at,observed_at
    FROM notification.notification_provider_evidence
    WHERE tenant_id=p_tenant_id AND notification_intent_id=p_intent_id
  ) x;

  RETURN v_intent||jsonb_build_object(
    'projection',v_projection,'attempts',v_attempts,'provider_evidence',v_evidence
  );
END;
$$;

CREATE OR REPLACE FUNCTION notification.g9_list_alert_intents(
  p_tenant_id TEXT,p_alert_id TEXT
) RETURNS JSONB
LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,notification
AS $$
DECLARE v_result JSONB;
BEGIN
  PERFORM set_config('jlmirror.tenant_id',p_tenant_id,true);
  SELECT COALESCE(jsonb_agg(to_jsonb(x) ORDER BY created_at DESC),'[]'::jsonb) INTO v_result FROM (
    SELECT i.notification_intent_id,i.recipient_principal_id,i.destination_ref,i.channel_class,
           i.reason,i.created_at,p.delivery_state,p.external_read_observed,
           p.retry_required,p.reconciliation_required,p.fallback_action_required,p.fallback_reason
    FROM notification.notification_intent i
    LEFT JOIN notification.notification_projection p
      ON p.tenant_id=i.tenant_id AND p.notification_intent_id=i.notification_intent_id
    WHERE i.tenant_id=p_tenant_id AND i.alert_id=p_alert_id
  ) x;
  RETURN v_result;
END;
$$;

ALTER FUNCTION notification.g9_reject_immutable_mutation() OWNER TO jlmirror_g9_notification_executor;
ALTER FUNCTION notification.g9_guard_attempt_terminal_transition() OWNER TO jlmirror_g9_notification_executor;
ALTER FUNCTION notification.g9_validate_authority(TEXT,TEXT,JSONB) OWNER TO jlmirror_g9_notification_executor;
ALTER FUNCTION notification.g9_refresh_projection(TEXT,TEXT) OWNER TO jlmirror_g9_notification_executor;
ALTER FUNCTION notification.g9_create_intent(TEXT,TEXT,TEXT,TEXT,TEXT,TEXT,TEXT,TEXT,TEXT,TEXT,TEXT,JSONB)
OWNER TO jlmirror_g9_notification_executor;
ALTER FUNCTION notification.g9_next_dispatch_candidate(TEXT)
OWNER TO jlmirror_g9_notification_executor;
ALTER FUNCTION notification.g9_claim_dispatch(TEXT,TEXT,TEXT,INTEGER,TEXT,JSONB)
OWNER TO jlmirror_g9_notification_executor;
ALTER FUNCTION notification.g9_complete_dispatch(TEXT,TEXT,TEXT,TEXT,TEXT,TEXT)
OWNER TO jlmirror_g9_notification_executor;
ALTER FUNCTION notification.g9_record_provider_callback(TEXT,TEXT,TEXT,TEXT,TEXT,JSONB,JSONB,TIMESTAMPTZ)
OWNER TO jlmirror_g9_notification_executor;
ALTER FUNCTION notification.g9_reconcile_dispatch_claim(TEXT,TEXT)
OWNER TO jlmirror_g9_notification_executor;
ALTER FUNCTION notification.g9_schedule_retry(TEXT,TEXT)
OWNER TO jlmirror_g9_notification_executor;
ALTER FUNCTION notification.g9_get_intent(TEXT,TEXT) OWNER TO jlmirror_g9_notification_executor;
ALTER FUNCTION notification.g9_list_alert_intents(TEXT,TEXT) OWNER TO jlmirror_g9_notification_executor;

REVOKE ALL ON ALL FUNCTIONS IN SCHEMA notification FROM PUBLIC;

GRANT EXECUTE ON FUNCTION notification.g9_create_intent(TEXT,TEXT,TEXT,TEXT,TEXT,TEXT,TEXT,TEXT,TEXT,TEXT,TEXT,JSONB)
TO jlmirror_g9_notification_app_invoker;
GRANT EXECUTE ON FUNCTION notification.g9_get_intent(TEXT,TEXT)
TO jlmirror_g9_notification_app_invoker;
GRANT EXECUTE ON FUNCTION notification.g9_list_alert_intents(TEXT,TEXT)
TO jlmirror_g9_notification_app_invoker;

GRANT EXECUTE ON FUNCTION notification.g9_next_dispatch_candidate(TEXT)
TO jlmirror_g9_notification_worker_invoker;
GRANT EXECUTE ON FUNCTION notification.g9_claim_dispatch(TEXT,TEXT,TEXT,INTEGER,TEXT,JSONB)
TO jlmirror_g9_notification_worker_invoker;
GRANT EXECUTE ON FUNCTION notification.g9_complete_dispatch(TEXT,TEXT,TEXT,TEXT,TEXT,TEXT)
TO jlmirror_g9_notification_worker_invoker;
GRANT EXECUTE ON FUNCTION notification.g9_reconcile_dispatch_claim(TEXT,TEXT)
TO jlmirror_g9_notification_worker_invoker;
GRANT EXECUTE ON FUNCTION notification.g9_schedule_retry(TEXT,TEXT)
TO jlmirror_g9_notification_worker_invoker;
GRANT EXECUTE ON FUNCTION notification.g9_get_intent(TEXT,TEXT)
TO jlmirror_g9_notification_worker_invoker;

GRANT EXECUTE ON FUNCTION notification.g9_record_provider_callback(TEXT,TEXT,TEXT,TEXT,TEXT,JSONB,JSONB,TIMESTAMPTZ)
TO jlmirror_g9_notification_callback_invoker;

DO $
DECLARE
  v_executor OID;
  v_app OID;
  v_worker OID;
  v_callback OID;
  v_row RECORD;
  v_oid OID;
  v_expected_grantee OID;
BEGIN
  SELECT oid INTO v_executor FROM pg_roles WHERE rolname='jlmirror_g9_notification_executor';
  SELECT oid INTO v_app FROM pg_roles WHERE rolname='jlmirror_g9_notification_app_invoker';
  SELECT oid INTO v_worker FROM pg_roles WHERE rolname='jlmirror_g9_notification_worker_invoker';
  SELECT oid INTO v_callback FROM pg_roles WHERE rolname='jlmirror_g9_notification_callback_invoker';

  FOR v_row IN
    SELECT signature,exposure FROM (VALUES
      ('notification.g9_reject_immutable_mutation()','internal'),
      ('notification.g9_guard_attempt_terminal_transition()','internal'),
      ('notification.g9_validate_authority(text,text,jsonb)','internal'),
      ('notification.g9_refresh_projection(text,text)','internal'),
      ('notification.g9_create_intent(text,text,text,text,text,text,text,text,text,text,text,jsonb)','app'),
      ('notification.g9_next_dispatch_candidate(text)','worker'),
      ('notification.g9_claim_dispatch(text,text,text,integer,text,jsonb)','worker'),
      ('notification.g9_complete_dispatch(text,text,text,text,text,text)','worker'),
      ('notification.g9_reconcile_dispatch_claim(text,text)','worker'),
      ('notification.g9_schedule_retry(text,text)','worker'),
      ('notification.g9_record_provider_callback(text,text,text,text,text,jsonb,jsonb,timestamp with time zone)','callback'),
      ('notification.g9_get_intent(text,text)','shared_read'),
      ('notification.g9_list_alert_intents(text,text)','app')
    ) AS x(signature,exposure)
  LOOP
    v_oid:=to_regprocedure(v_row.signature);
    IF v_oid IS NULL THEN
      RAISE EXCEPTION 'g9.function_missing:%',v_row.signature;
    END IF;

    IF EXISTS (
      SELECT 1 FROM pg_proc p
      WHERE p.oid=v_oid AND p.proowner<>v_executor
    ) THEN
      RAISE EXCEPTION 'g9.function_owner_unsafe:%',v_row.signature;
    END IF;

    IF v_row.exposure<>'internal' AND EXISTS (
      SELECT 1 FROM pg_proc p
      WHERE p.oid=v_oid AND p.prosecdef IS NOT TRUE
    ) THEN
      RAISE EXCEPTION 'g9.exposed_function_not_security_definer:%',v_row.signature;
    END IF;

    FOR v_expected_grantee IN
      SELECT CASE v_row.exposure
        WHEN 'app' THEN v_app
        WHEN 'worker' THEN v_worker
        WHEN 'callback' THEN v_callback
        ELSE NULL
      END
    LOOP
      NULL;
    END LOOP;

    IF EXISTS (
      SELECT 1
      FROM pg_proc p,
           LATERAL aclexplode(COALESCE(p.proacl,acldefault('f',p.proowner))) a
      WHERE p.oid=v_oid
        AND a.privilege_type='EXECUTE'
        AND a.grantee<>p.proowner
        AND (
          v_row.exposure='internal'
          OR (v_row.exposure='app' AND a.grantee<>v_app)
          OR (v_row.exposure='worker' AND a.grantee<>v_worker)
          OR (v_row.exposure='callback' AND a.grantee<>v_callback)
          OR (v_row.exposure='shared_read' AND a.grantee NOT IN (v_app,v_worker))
          OR a.is_grantable
        )
    ) THEN
      RAISE EXCEPTION 'g9.function_acl_unsafe:%',v_row.signature;
    END IF;

    IF EXISTS (
      SELECT 1
      FROM pg_proc p,
           LATERAL aclexplode(COALESCE(p.proacl,acldefault('f',p.proowner))) a
      WHERE p.oid=v_oid AND a.privilege_type='EXECUTE' AND a.grantee=0
    ) THEN
      RAISE EXCEPTION 'g9.public_execute_unsafe:%',v_row.signature;
    END IF;
  END LOOP;
END;
$;

COMMIT;
