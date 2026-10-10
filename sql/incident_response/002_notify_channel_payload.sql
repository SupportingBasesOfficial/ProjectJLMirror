BEGIN;

-- Add payload column to store per-action channel configuration for notify actions.
ALTER TABLE incident_response.action_request
    ADD COLUMN IF NOT EXISTS payload JSONB NULL;

-- Replace 3-arg enqueue function with 4-arg version; DEFAULT NULL preserves callers
-- that omit the payload.
DROP FUNCTION IF EXISTS incident_response.g11_enqueue_action(TEXT,TEXT,TEXT);

CREATE OR REPLACE FUNCTION incident_response.g11_enqueue_action(
  p_tenant_id   TEXT,
  p_event_id    TEXT,
  p_action_kind TEXT,
  p_payload     JSONB DEFAULT NULL
) RETURNS JSONB
LANGUAGE plpgsql SECURITY DEFINER AS $$
DECLARE
  v_id TEXT := 'req:' || encode(sha256(
    (p_tenant_id||E'\x1f'||p_event_id||E'\x1f'||p_action_kind||E'\x1f'||
     coalesce(p_payload::text,'')||E'\x1f'||
     to_char(now(),'YYYYMMDDHH24MISSUS'))::bytea),'hex');
BEGIN
  INSERT INTO incident_response.action_request
    (request_id,tenant_id,event_id,action_kind,payload)
  VALUES (v_id,p_tenant_id,p_event_id,p_action_kind,p_payload);
  RETURN jsonb_build_object('request_id',v_id,'action_kind',p_action_kind,'status','pending');
END;
$$;

-- Update next_pending_action to return payload so workers can route notify actions
-- to the correct channel without a secondary policy lookup.
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
    'attempts',v_req.attempts,'event',to_jsonb(v_evt),
    'payload',v_req.payload
  );
END;
$$;

-- Grant the new enqueue signature to the app invoker role.
GRANT EXECUTE ON FUNCTION
  incident_response.g11_enqueue_action(TEXT,TEXT,TEXT,JSONB)
TO jlmirror_g11_ir_app_invoker;

COMMIT;
