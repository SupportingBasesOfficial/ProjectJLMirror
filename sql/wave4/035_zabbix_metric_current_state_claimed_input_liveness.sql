-- Totalize claimed Metric Current State completion input and enforce canonical value shape.

BEGIN;

CREATE OR REPLACE FUNCTION monitoring.wave4_current_value_matches_kind(
    p_value_kind TEXT,
    p_value JSONB
) RETURNS BOOLEAN
LANGUAGE sql IMMUTABLE PARALLEL SAFE
SET search_path=pg_catalog,monitoring AS $$
    SELECT CASE p_value_kind
        WHEN 'number' THEN jsonb_typeof(p_value)='number'
        WHEN 'integer' THEN jsonb_typeof(p_value)='number' AND p_value::text ~ '^[0-9]+$'
        WHEN 'boolean' THEN jsonb_typeof(p_value)='boolean'
        WHEN 'string' THEN jsonb_typeof(p_value)='string'
        WHEN 'text' THEN jsonb_typeof(p_value)='string'
        WHEN 'log' THEN jsonb_typeof(p_value)='string'
        ELSE FALSE
    END
$$;

ALTER TABLE monitoring.monitoring_metric_observation_acceptance
    ADD CONSTRAINT monitoring_metric_observation_acceptance_value_shape
    CHECK (monitoring.wave4_current_value_matches_kind(value_kind,canonical_value));
ALTER TABLE monitoring.metric_current_state
    ADD CONSTRAINT metric_current_state_value_shape
    CHECK (monitoring.wave4_current_value_matches_kind(value_kind,canonical_value));

ALTER FUNCTION monitoring.complete_zabbix_metric_current_state(TEXT,TEXT,TEXT,JSONB)
    RENAME TO complete_zabbix_metric_current_state_v031_internal;
REVOKE EXECUTE ON FUNCTION monitoring.complete_zabbix_metric_current_state_v031_internal(TEXT,TEXT,TEXT,JSONB)
    FROM PUBLIC, jlmirror_wave4_metric_current_state_invoker;

CREATE FUNCTION monitoring.complete_zabbix_metric_current_state(
    p_tenant_id TEXT,
    p_monitoring_sync_operation_id TEXT,
    p_claim_token TEXT,
    p_observations JSONB
) RETURNS TEXT
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,monitoring AS $$
DECLARE
    v_operation monitoring.monitoring_sync_operation%ROWTYPE;
    v_invalid BOOLEAN := FALSE;
BEGIN
    -- Resolve the claim first. Once a valid claim exists, malformed provider evidence must
    -- produce a durable terminal outcome rather than strand the operation in running state.
    SELECT o.* INTO v_operation
      FROM monitoring.monitoring_sync_operation AS o
     WHERE o.tenant_id=p_tenant_id
       AND o.monitoring_sync_operation_id=p_monitoring_sync_operation_id
       AND o.responsibility_kind='metric_current_state_sync'
       AND o.state='running'
       AND o.claim_token=p_claim_token
     FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'monitoring.metric_current_state_completion_not_claimed';
    END IF;

    IF p_observations IS NULL OR jsonb_typeof(p_observations)<>'array'
       OR jsonb_array_length(p_observations)>200000 THEN
        v_invalid:=TRUE;
    END IF;

    IF NOT v_invalid AND EXISTS (
        SELECT 1
          FROM jsonb_array_elements(p_observations) AS e(value)
         WHERE jsonb_typeof(e.value)<>'object'
            OR NOT (e.value ?& ARRAY[
                'metric_definition_id','provider_external_ref','observation_id',
                'provider_clock','provider_ns','value_kind','canonical_value'
            ])
            OR EXISTS (
                SELECT 1 FROM jsonb_object_keys(e.value) AS k(key)
                 WHERE k.key <> ALL(ARRAY[
                    'metric_definition_id','provider_external_ref','observation_id',
                    'provider_clock','provider_ns','value_kind','canonical_value'
                 ])
            )
            OR e.value->>'metric_definition_id' IS NULL
            OR e.value->>'metric_definition_id'=''
            OR length(e.value->>'metric_definition_id')>512
            OR e.value->>'provider_external_ref' IS NULL
            OR e.value->>'provider_external_ref'=''
            OR length(e.value->>'provider_external_ref')>256
            OR e.value->>'observation_id' IS NULL
            OR e.value->>'observation_id'=''
            OR length(e.value->>'observation_id')>512
            OR e.value->>'provider_clock' !~ '^[1-9][0-9]{0,18}$'
            OR e.value->>'provider_ns' !~ '^[0-9]{1,9}$'
            OR (e.value->>'provider_ns')::BIGINT>999999999
            OR e.value->>'value_kind' NOT IN ('number','integer','boolean','string','text','log')
            OR NOT monitoring.wave4_current_value_matches_kind(e.value->>'value_kind',e.value->'canonical_value')
            OR octet_length((e.value->'canonical_value')::text)>131072
    ) THEN
        v_invalid:=TRUE;
    END IF;

    IF NOT v_invalid AND EXISTS (
        SELECT 1 FROM (
            SELECT e.value->>'provider_external_ref' AS k,count(*) AS n
              FROM jsonb_array_elements(p_observations) AS e(value)
             GROUP BY 1
        ) AS q WHERE q.n>1
    ) THEN v_invalid:=TRUE; END IF;

    IF NOT v_invalid AND EXISTS (
        SELECT 1 FROM (
            SELECT e.value->>'metric_definition_id' AS k,count(*) AS n
              FROM jsonb_array_elements(p_observations) AS e(value)
             GROUP BY 1
        ) AS q WHERE q.n>1
    ) THEN v_invalid:=TRUE; END IF;

    IF NOT v_invalid AND EXISTS (
        SELECT 1 FROM (
            SELECT e.value->>'observation_id' AS k,count(*) AS n
              FROM jsonb_array_elements(p_observations) AS e(value)
             GROUP BY 1
        ) AS q WHERE q.n>1
    ) THEN v_invalid:=TRUE; END IF;

    -- A platform observation ID is immutable scoped identity. Reuse with different meaning
    -- is an integrity failure, not a duplicate.
    IF NOT v_invalid AND EXISTS (
        SELECT 1
          FROM jsonb_array_elements(p_observations) AS e(value)
          JOIN monitoring.monitoring_metric_observation_acceptance AS a
            ON a.tenant_id=p_tenant_id
           AND a.observation_id=e.value->>'observation_id'
         WHERE a.metric_definition_id IS DISTINCT FROM e.value->>'metric_definition_id'
            OR a.provider_external_ref IS DISTINCT FROM e.value->>'provider_external_ref'
            OR a.provider_clock IS DISTINCT FROM (e.value->>'provider_clock')::BIGINT
            OR a.provider_ns IS DISTINCT FROM (e.value->>'provider_ns')::INTEGER
            OR a.value_kind IS DISTINCT FROM e.value->>'value_kind'
            OR a.canonical_value IS DISTINCT FROM e.value->'canonical_value'
    ) THEN
        v_invalid:=TRUE;
    END IF;

    IF v_invalid THEN
        UPDATE monitoring.monitoring_sync_operation AS o
           SET state='reconciliation_required',completed_at=transaction_timestamp(),
               last_error_class='provider.protocol_invalid',claim_token=NULL
         WHERE o.tenant_id=p_tenant_id
           AND o.monitoring_sync_operation_id=p_monitoring_sync_operation_id;
        RETURN 'reconciliation_required';
    END IF;

    RETURN monitoring.complete_zabbix_metric_current_state_v031_internal(
        p_tenant_id,p_monitoring_sync_operation_id,p_claim_token,p_observations
    );
END;
$$;

ALTER FUNCTION monitoring.complete_zabbix_metric_current_state(TEXT,TEXT,TEXT,JSONB)
    OWNER TO jlmirror_wave4_metric_current_state_executor;
REVOKE EXECUTE ON FUNCTION monitoring.complete_zabbix_metric_current_state(TEXT,TEXT,TEXT,JSONB) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION monitoring.complete_zabbix_metric_current_state(TEXT,TEXT,TEXT,JSONB)
    TO jlmirror_wave4_metric_current_state_invoker;

COMMIT;
