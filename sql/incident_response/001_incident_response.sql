BEGIN;

CREATE SCHEMA IF NOT EXISTS incident_response;

-- Roles
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='jlmirror_g11_ir_executor') THEN
    CREATE ROLE jlmirror_g11_ir_executor
      NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='jlmirror_g11_ir_app_invoker') THEN
    CREATE ROLE jlmirror_g11_ir_app_invoker
      NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='jlmirror_g11_ir_worker_invoker') THEN
    CREATE ROLE jlmirror_g11_ir_worker_invoker
      NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS;
  END IF;
END;
$$;

-- Role safety guard
DO $$
DECLARE v_role RECORD;
BEGIN
  FOR v_role IN SELECT * FROM pg_roles
    WHERE rolname IN ('jlmirror_g11_ir_executor','jlmirror_g11_ir_app_invoker','jlmirror_g11_ir_worker_invoker')
  LOOP
    IF v_role.rolcanlogin OR v_role.rolsuper OR v_role.rolcreatedb OR v_role.rolcreaterole
       OR v_role.rolinherit OR v_role.rolreplication OR v_role.rolbypassrls THEN
      RAISE EXCEPTION 'g11.role_unsafe:%',v_role.rolname;
    END IF;
  END LOOP;
END;
$$;

-- Tables
CREATE TABLE IF NOT EXISTS incident_response.policy (
  tenant_id             TEXT        NOT NULL PRIMARY KEY,
  severity_threshold    TEXT        NOT NULL DEFAULT 'HIGH'
                          CHECK (severity_threshold IN ('LOW','MEDIUM','HIGH','CRITICAL')),
  auto_open_ticket      BOOLEAN     NOT NULL DEFAULT FALSE,
  manual_override_only  BOOLEAN     NOT NULL DEFAULT FALSE,
  notify_channels       JSONB       NOT NULL DEFAULT '[]'::jsonb,
  automation_triggers   JSONB       NOT NULL DEFAULT '[]'::jsonb,
  updated_by            TEXT        NOT NULL,
  created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at            TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS incident_response.application_error_event (
  event_id             TEXT        NOT NULL PRIMARY KEY,
  tenant_id            TEXT        NOT NULL,
  application_id       TEXT        NOT NULL,
  error_code           TEXT        NOT NULL,
  error_message        TEXT        NOT NULL,
  occurred_at          TEXT        NOT NULL,
  source_principal_id  TEXT        NOT NULL,
  principal_id         TEXT,
  operation            TEXT,
  session_context      TEXT,
  severity_hint        TEXT        CHECK (severity_hint IN ('LOW','MEDIUM','HIGH','CRITICAL')),
  raw_payload          JSONB,
  received_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
  status               TEXT        NOT NULL DEFAULT 'received'
                         CHECK (status IN ('received','processing','processed','error'))
);

CREATE INDEX IF NOT EXISTS idx_ir_event_tenant_received
  ON incident_response.application_error_event(tenant_id, received_at DESC);

CREATE TABLE IF NOT EXISTS incident_response.dedupe_entry (
  tenant_id       TEXT        NOT NULL,
  application_id  TEXT        NOT NULL,
  error_code      TEXT        NOT NULL,
  bucket_ts       TEXT        NOT NULL,
  claimed_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  expires_at      TIMESTAMPTZ NOT NULL DEFAULT now() + INTERVAL '5 minutes',
  PRIMARY KEY (tenant_id, application_id, error_code, bucket_ts)
);

CREATE INDEX IF NOT EXISTS idx_ir_dedupe_expires
  ON incident_response.dedupe_entry(expires_at);

CREATE TABLE IF NOT EXISTS incident_response.action_request (
  request_id     TEXT        NOT NULL PRIMARY KEY,
  tenant_id      TEXT        NOT NULL,
  event_id       TEXT        NOT NULL REFERENCES incident_response.application_error_event(event_id),
  action_kind    TEXT        NOT NULL CHECK (action_kind IN ('open_ticket','notify','automation')),
  status         TEXT        NOT NULL DEFAULT 'pending'
                   CHECK (status IN ('pending','dispatching','linked','failed','skipped','unknown')),
  attempts       INTEGER     NOT NULL DEFAULT 0,
  claimed_until  TIMESTAMPTZ,
  claimed_by     TEXT,
  provider_ref   TEXT,
  failure_class  TEXT,
  created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_ir_action_pending
  ON incident_response.action_request(tenant_id, status, created_at)
  WHERE status='pending';

-- Functions

CREATE OR REPLACE FUNCTION incident_response.g11_get_policy(
  p_tenant_id TEXT
) RETURNS JSONB
LANGUAGE plpgsql SECURITY DEFINER AS $$
DECLARE v_row incident_response.policy;
BEGIN
  SELECT * INTO v_row FROM incident_response.policy WHERE tenant_id=p_tenant_id;
  IF NOT FOUND THEN RETURN NULL; END IF;
  RETURN jsonb_build_object(
    'tenant_id',v_row.tenant_id,
    'severity_threshold',v_row.severity_threshold,
    'auto_open_ticket',v_row.auto_open_ticket,
    'manual_override_only',v_row.manual_override_only,
    'notify_channels',v_row.notify_channels,
    'automation_triggers',v_row.automation_triggers,
    'updated_by',v_row.updated_by,
    'updated_at',v_row.updated_at
  );
END;
$$;

CREATE OR REPLACE FUNCTION incident_response.g11_upsert_policy(
  p_tenant_id          TEXT,
  p_policy             JSONB,
  p_actor_principal_id TEXT
) RETURNS JSONB
LANGUAGE plpgsql SECURITY DEFINER AS $$
DECLARE
  v_threshold TEXT := COALESCE(p_policy->>'severity_threshold','HIGH');
  v_auto      BOOLEAN := COALESCE((p_policy->>'auto_open_ticket')::boolean, FALSE);
  v_manual    BOOLEAN := COALESCE((p_policy->>'manual_override_only')::boolean, FALSE);
  v_notify    JSONB   := COALESCE(p_policy->'notify_channels','[]'::jsonb);
  v_auto_tr   JSONB   := COALESCE(p_policy->'automation_triggers','[]'::jsonb);
BEGIN
  IF v_threshold NOT IN ('LOW','MEDIUM','HIGH','CRITICAL') THEN
    RAISE EXCEPTION 'g11.invalid_severity_threshold:%',v_threshold;
  END IF;
  INSERT INTO incident_response.policy
    (tenant_id,severity_threshold,auto_open_ticket,manual_override_only,
     notify_channels,automation_triggers,updated_by,updated_at)
  VALUES
    (p_tenant_id,v_threshold,v_auto,v_manual,v_notify,v_auto_tr,p_actor_principal_id,now())
  ON CONFLICT (tenant_id) DO UPDATE SET
    severity_threshold   = EXCLUDED.severity_threshold,
    auto_open_ticket     = EXCLUDED.auto_open_ticket,
    manual_override_only = EXCLUDED.manual_override_only,
    notify_channels      = EXCLUDED.notify_channels,
    automation_triggers  = EXCLUDED.automation_triggers,
    updated_by           = EXCLUDED.updated_by,
    updated_at           = EXCLUDED.updated_at;
  RETURN incident_response.g11_get_policy(p_tenant_id);
END;
$$;

CREATE OR REPLACE FUNCTION incident_response.g11_claim_dedupe(
  p_tenant_id      TEXT,
  p_application_id TEXT,
  p_error_code     TEXT,
  p_bucket_ts      TEXT
) RETURNS BOOLEAN
LANGUAGE plpgsql SECURITY DEFINER AS $$
BEGIN
  DELETE FROM incident_response.dedupe_entry WHERE expires_at < now();
  INSERT INTO incident_response.dedupe_entry
    (tenant_id,application_id,error_code,bucket_ts)
  VALUES (p_tenant_id,p_application_id,p_error_code,p_bucket_ts)
  ON CONFLICT DO NOTHING;
  RETURN FOUND;
END;
$$;

CREATE OR REPLACE FUNCTION incident_response.g11_store_event(
  p_tenant_id           TEXT,
  p_application_id      TEXT,
  p_error_code          TEXT,
  p_error_message       TEXT,
  p_occurred_at         TEXT,
  p_source_principal_id TEXT,
  p_principal_id        TEXT,
  p_operation           TEXT,
  p_session_context     TEXT,
  p_severity_hint       TEXT,
  p_raw_payload         JSONB
) RETURNS JSONB
LANGUAGE plpgsql SECURITY DEFINER AS $$
DECLARE
  v_id TEXT := 'evt:' || encode(sha256(
    (p_tenant_id||E'\x1f'||p_application_id||E'\x1f'||p_error_code||E'\x1f'||
     p_occurred_at||E'\x1f'||p_source_principal_id||E'\x1f'||to_char(now(),'YYYYMMDDHH24MISSUS'))::bytea),
    'hex');
BEGIN
  INSERT INTO incident_response.application_error_event
    (event_id,tenant_id,application_id,error_code,error_message,occurred_at,
     source_principal_id,principal_id,operation,session_context,severity_hint,raw_payload)
  VALUES
    (v_id,p_tenant_id,p_application_id,p_error_code,p_error_message,p_occurred_at,
     p_source_principal_id,p_principal_id,p_operation,p_session_context,p_severity_hint,p_raw_payload);
  RETURN jsonb_build_object('event_id',v_id,'status','received');
END;
$$;

CREATE OR REPLACE FUNCTION incident_response.g11_enqueue_action(
  p_tenant_id  TEXT,
  p_event_id   TEXT,
  p_action_kind TEXT
) RETURNS JSONB
LANGUAGE plpgsql SECURITY DEFINER AS $$
DECLARE
  v_id TEXT := 'req:' || encode(sha256(
    (p_tenant_id||E'\x1f'||p_event_id||E'\x1f'||p_action_kind||E'\x1f'||
     to_char(now(),'YYYYMMDDHH24MISSUS'))::bytea),'hex');
BEGIN
  INSERT INTO incident_response.action_request
    (request_id,tenant_id,event_id,action_kind)
  VALUES (v_id,p_tenant_id,p_event_id,p_action_kind);
  RETURN jsonb_build_object('request_id',v_id,'action_kind',p_action_kind,'status','pending');
END;
$$;

CREATE OR REPLACE FUNCTION incident_response.g11_list_events(
  p_tenant_id TEXT
) RETURNS JSONB
LANGUAGE plpgsql SECURITY DEFINER AS $$
BEGIN
  RETURN (
    SELECT COALESCE(jsonb_agg(jsonb_build_object(
      'event_id',event_id,'application_id',application_id,'error_code',error_code,
      'error_message',error_message,'occurred_at',occurred_at,
      'severity_hint',severity_hint,'status',status,'received_at',received_at
    ) ORDER BY received_at DESC),'[]'::jsonb)
    FROM incident_response.application_error_event
    WHERE tenant_id=p_tenant_id
    LIMIT 100
  );
END;
$$;

CREATE OR REPLACE FUNCTION incident_response.g11_get_event(
  p_tenant_id TEXT,
  p_event_id  TEXT
) RETURNS JSONB
LANGUAGE plpgsql SECURITY DEFINER AS $$
DECLARE v_row incident_response.application_error_event;
BEGIN
  SELECT * INTO v_row
  FROM incident_response.application_error_event
  WHERE tenant_id=p_tenant_id AND event_id=p_event_id;
  IF NOT FOUND THEN RETURN NULL; END IF;
  RETURN to_jsonb(v_row);
END;
$$;

CREATE OR REPLACE FUNCTION incident_response.g11_next_pending_action(
  p_tenant_id TEXT
) RETURNS JSONB
LANGUAGE plpgsql SECURITY DEFINER AS $$
DECLARE
  v_req  incident_response.action_request;
  v_evt  incident_response.application_error_event;
BEGIN
  SELECT r.* INTO v_req
  FROM incident_response.action_request r
  WHERE r.tenant_id=p_tenant_id
    AND r.status='pending'
    AND (r.claimed_until IS NULL OR r.claimed_until < now())
  ORDER BY r.created_at
  LIMIT 1
  FOR UPDATE SKIP LOCKED;
  IF NOT FOUND THEN RETURN NULL; END IF;
  SELECT * INTO v_evt
  FROM incident_response.application_error_event
  WHERE event_id=v_req.event_id AND tenant_id=p_tenant_id;
  RETURN jsonb_build_object(
    'request_id',v_req.request_id,'action_kind',v_req.action_kind,
    'attempts',v_req.attempts,'event',to_jsonb(v_evt)
  );
END;
$$;

CREATE OR REPLACE FUNCTION incident_response.g11_claim_action(
  p_tenant_id   TEXT,
  p_request_id  TEXT,
  p_executor_id TEXT,
  p_claim_secs  INTEGER
) RETURNS JSONB
LANGUAGE plpgsql SECURITY DEFINER AS $$
BEGIN
  UPDATE incident_response.action_request
  SET status='dispatching', claimed_by=p_executor_id,
      claimed_until=now()+make_interval(secs=>p_claim_secs),
      attempts=attempts+1, updated_at=now()
  WHERE request_id=p_request_id AND tenant_id=p_tenant_id
    AND status='pending';
  IF NOT FOUND THEN RETURN jsonb_build_object('state','conflict'); END IF;
  RETURN jsonb_build_object('state','dispatching','request_id',p_request_id);
END;
$$;

CREATE OR REPLACE FUNCTION incident_response.g11_complete_action(
  p_tenant_id    TEXT,
  p_request_id   TEXT,
  p_executor_id  TEXT,
  p_result_state TEXT,
  p_provider_ref TEXT,
  p_failure_class TEXT
) RETURNS JSONB
LANGUAGE plpgsql SECURITY DEFINER AS $$
BEGIN
  UPDATE incident_response.action_request
  SET status=p_result_state, provider_ref=p_provider_ref,
      failure_class=p_failure_class, claimed_until=NULL,
      updated_at=now()
  WHERE request_id=p_request_id AND tenant_id=p_tenant_id
    AND claimed_by=p_executor_id AND status='dispatching';
  IF NOT FOUND THEN RETURN jsonb_build_object('state','conflict'); END IF;
  -- update parent event status if all actions done
  UPDATE incident_response.application_error_event
  SET status='processed', updated_at=now()  -- updated_at added below via trigger
  WHERE event_id=(
    SELECT event_id FROM incident_response.action_request WHERE request_id=p_request_id
  )
  AND NOT EXISTS (
    SELECT 1 FROM incident_response.action_request
    WHERE event_id=(SELECT event_id FROM incident_response.action_request WHERE request_id=p_request_id)
      AND status IN ('pending','dispatching')
  );
  RETURN jsonb_build_object('state',p_result_state,'request_id',p_request_id);
END;
$$;

CREATE OR REPLACE FUNCTION incident_response.g11_record_action_attempt(
  p_tenant_id     TEXT,
  p_request_id    TEXT,
  p_result_state  TEXT,
  p_provider_ref  TEXT,
  p_failure_reason TEXT
) RETURNS VOID
LANGUAGE plpgsql SECURITY DEFINER AS $$
BEGIN
  UPDATE incident_response.action_request
  SET provider_ref=p_provider_ref, failure_class=p_failure_reason,
      status=p_result_state, updated_at=now()
  WHERE request_id=p_request_id AND tenant_id=p_tenant_id;
END;
$$;

-- updated_at trigger for application_error_event
CREATE OR REPLACE FUNCTION incident_response.g11_set_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN NEW.updated_at=now(); RETURN NEW; END;
$$;

DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_trigger WHERE tgname='trg_ir_event_updated_at'
  ) THEN
    ALTER TABLE incident_response.application_error_event ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT now();
    CREATE TRIGGER trg_ir_event_updated_at
      BEFORE UPDATE ON incident_response.application_error_event
      FOR EACH ROW EXECUTE FUNCTION incident_response.g11_set_updated_at();
  END IF;
END; $$;

-- Grants
GRANT USAGE ON SCHEMA incident_response TO jlmirror_g11_ir_executor;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA incident_response TO jlmirror_g11_ir_executor;

GRANT USAGE ON SCHEMA incident_response TO jlmirror_g11_ir_app_invoker;
GRANT EXECUTE ON FUNCTION
  incident_response.g11_get_policy(TEXT),
  incident_response.g11_upsert_policy(TEXT,JSONB,TEXT),
  incident_response.g11_claim_dedupe(TEXT,TEXT,TEXT,TEXT),
  incident_response.g11_store_event(TEXT,TEXT,TEXT,TEXT,TEXT,TEXT,TEXT,TEXT,TEXT,TEXT,JSONB),
  incident_response.g11_enqueue_action(TEXT,TEXT,TEXT),
  incident_response.g11_list_events(TEXT),
  incident_response.g11_get_event(TEXT,TEXT)
TO jlmirror_g11_ir_app_invoker;

GRANT USAGE ON SCHEMA incident_response TO jlmirror_g11_ir_worker_invoker;
GRANT EXECUTE ON FUNCTION
  incident_response.g11_next_pending_action(TEXT),
  incident_response.g11_claim_action(TEXT,TEXT,TEXT,INTEGER),
  incident_response.g11_complete_action(TEXT,TEXT,TEXT,TEXT,TEXT,TEXT),
  incident_response.g11_record_action_attempt(TEXT,TEXT,TEXT,TEXT,TEXT)
TO jlmirror_g11_ir_worker_invoker;

COMMIT;
