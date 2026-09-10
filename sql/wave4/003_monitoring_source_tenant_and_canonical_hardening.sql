-- Wave 4 Monitoring source tenant/canonical hardening.
--
-- Successor hardening for the first Monitoring/Zabbix product slice. This
-- migration closes the database trust-boundary gaps identified during the
-- adversarial PR review without expanding product scope.

BEGIN;

CREATE FUNCTION monitoring.wave4_is_canonical_zabbix_base_url(p_url TEXT)
RETURNS BOOLEAN
LANGUAGE plpgsql
IMMUTABLE
STRICT
SET search_path = pg_catalog, monitoring
AS $$
DECLARE
    remainder TEXT;
    authority TEXT;
    path TEXT;
    host TEXT;
    suffix TEXT;
    port_text TEXT;
    closing_bracket INTEGER;
    slash_position INTEGER;
    colon_count INTEGER;
    path_segment TEXT;
BEGIN
    IF p_url = ''
       OR length(p_url) > 2048
       OR p_url <> btrim(p_url)
       OR octet_length(p_url) <> length(p_url)
       OR p_url !~ '^https://'
       OR p_url ~ '[[:cntrl:][:space:]]'
       OR position('?' IN p_url) > 0
       OR position('#' IN p_url) > 0
       OR position('@' IN p_url) > 0
       OR position(E'\\' IN p_url) > 0 THEN
        RETURN FALSE;
    END IF;

    remainder := substr(p_url, 9);
    slash_position := position('/' IN remainder);
    IF slash_position = 0 THEN
        authority := remainder;
        path := '';
    ELSE
        authority := substr(remainder, 1, slash_position - 1);
        path := substr(remainder, slash_position);
    END IF;

    IF authority = '' THEN
        RETURN FALSE;
    END IF;

    IF left(authority, 1) = '[' THEN
        closing_bracket := position(']' IN authority);
        IF closing_bracket <= 2 THEN
            RETURN FALSE;
        END IF;
        host := substr(authority, 2, closing_bracket - 2);
        suffix := substr(authority, closing_bracket + 1);
        IF host <> lower(host) OR host !~ '^[0-9a-f:.]+$' THEN
            RETURN FALSE;
        END IF;
        BEGIN
            IF family(host::inet) <> 6 THEN
                RETURN FALSE;
            END IF;
        EXCEPTION WHEN invalid_text_representation THEN
            RETURN FALSE;
        END;
        IF suffix <> '' THEN
            IF suffix !~ '^:[0-9]{1,5}$' THEN
                RETURN FALSE;
            END IF;
            port_text := substr(suffix, 2);
            IF port_text <> (port_text::INTEGER)::TEXT
               OR port_text::INTEGER > 65535 THEN
                RETURN FALSE;
            END IF;
        END IF;
    ELSE
        colon_count := length(authority) - length(replace(authority, ':', ''));
        IF colon_count > 1 THEN
            RETURN FALSE;
        END IF;
        IF colon_count = 1 THEN
            host := split_part(authority, ':', 1);
            port_text := split_part(authority, ':', 2);
            IF port_text !~ '^[0-9]{1,5}$'
               OR port_text <> (port_text::INTEGER)::TEXT
               OR port_text::INTEGER > 65535 THEN
                RETURN FALSE;
            END IF;
        ELSE
            host := authority;
        END IF;
        IF host = ''
           OR host <> lower(host)
           OR right(host, 1) = '.'
           OR host ~ '[/:\[\]]' THEN
            RETURN FALSE;
        END IF;
    END IF;

    IF path <> '' THEN
        FOREACH path_segment IN ARRAY string_to_array(path, '/') LOOP
            IF path_segment IN ('.', '..') THEN
                RETURN FALSE;
            END IF;
        END LOOP;
    END IF;

    RETURN TRUE;
END;
$$;

COMMENT ON FUNCTION monitoring.wave4_is_canonical_zabbix_base_url(TEXT) IS
'Deterministic, network-free SQL boundary validator for the canonical HTTPS Zabbix endpoint representation accepted by the Monitoring source domain.';

ALTER TABLE monitoring.monitoring_source_generation
    ADD CONSTRAINT monitoring_source_generation_canonical_base_url
    CHECK (monitoring.wave4_is_canonical_zabbix_base_url(provider_base_url))
    NOT VALID;

ALTER TABLE monitoring.monitoring_source_generation
    VALIDATE CONSTRAINT monitoring_source_generation_canonical_base_url;

CREATE OR REPLACE FUNCTION monitoring.wave4_guard_source_identity_update()
RETURNS trigger
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = pg_catalog, monitoring
AS $$
BEGIN
    IF NEW.tenant_id IS DISTINCT FROM OLD.tenant_id
       OR NEW.monitoring_source_id IS DISTINCT FROM OLD.monitoring_source_id
       OR NEW.provider_profile IS DISTINCT FROM OLD.provider_profile THEN
        RAISE EXCEPTION 'Monitoring source tenant/logical identity/provider profile is immutable';
    END IF;
    IF NEW.configuration_revision < OLD.configuration_revision
       OR NEW.scope_revision < OLD.scope_revision THEN
        RAISE EXCEPTION 'Monitoring source revisions cannot regress';
    END IF;
    IF NEW.configured_provider_scope IS DISTINCT FROM OLD.configured_provider_scope
       AND NEW.scope_revision <= OLD.scope_revision THEN
        RAISE EXCEPTION 'Monitoring source scope change requires scope revision advance';
    END IF;
    RETURN NEW;
END;
$$;

ALTER TABLE monitoring.monitoring_source ENABLE ROW LEVEL SECURITY;
ALTER TABLE monitoring.monitoring_source FORCE ROW LEVEL SECURITY;
CREATE POLICY monitoring_source_tenant_policy
ON monitoring.monitoring_source
USING (
    tenant_id = NULLIF(current_setting('jlmirror.tenant_id', true), '')
)
WITH CHECK (
    tenant_id = NULLIF(current_setting('jlmirror.tenant_id', true), '')
);

ALTER TABLE monitoring.monitoring_source_generation ENABLE ROW LEVEL SECURITY;
ALTER TABLE monitoring.monitoring_source_generation FORCE ROW LEVEL SECURITY;
CREATE POLICY monitoring_source_generation_tenant_policy
ON monitoring.monitoring_source_generation
USING (
    tenant_id = NULLIF(current_setting('jlmirror.tenant_id', true), '')
)
WITH CHECK (
    tenant_id = NULLIF(current_setting('jlmirror.tenant_id', true), '')
);

ALTER TABLE monitoring.monitoring_sync_operation ENABLE ROW LEVEL SECURITY;
ALTER TABLE monitoring.monitoring_sync_operation FORCE ROW LEVEL SECURITY;
CREATE POLICY monitoring_sync_operation_tenant_policy
ON monitoring.monitoring_sync_operation
USING (
    tenant_id = NULLIF(current_setting('jlmirror.tenant_id', true), '')
)
WITH CHECK (
    tenant_id = NULLIF(current_setting('jlmirror.tenant_id', true), '')
);

ALTER TABLE monitoring.monitoring_source_create_idempotency ENABLE ROW LEVEL SECURITY;
ALTER TABLE monitoring.monitoring_source_create_idempotency FORCE ROW LEVEL SECURITY;
CREATE POLICY monitoring_source_create_idempotency_tenant_policy
ON monitoring.monitoring_source_create_idempotency
USING (
    tenant_id = NULLIF(current_setting('jlmirror.tenant_id', true), '')
)
WITH CHECK (
    tenant_id = NULLIF(current_setting('jlmirror.tenant_id', true), '')
);

ALTER TABLE monitoring.monitoring_source_audit_evidence ENABLE ROW LEVEL SECURITY;
ALTER TABLE monitoring.monitoring_source_audit_evidence FORCE ROW LEVEL SECURITY;
CREATE POLICY monitoring_source_audit_evidence_tenant_policy
ON monitoring.monitoring_source_audit_evidence
USING (
    tenant_id = NULLIF(current_setting('jlmirror.tenant_id', true), '')
)
WITH CHECK (
    tenant_id = NULLIF(current_setting('jlmirror.tenant_id', true), '')
);

COMMENT ON POLICY monitoring_source_tenant_policy ON monitoring.monitoring_source IS
'Fail-closed pooled-tenant policy for trusted platform-owned SQL. Missing transaction-local tenant context matches no rows.';

COMMIT;
