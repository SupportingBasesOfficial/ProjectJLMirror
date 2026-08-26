-- Wave 2 inbox-to-operation immutable authority-scope binding hardening.
-- Applies after migrations 001..005.
--
-- The technical operation_id foreign key proves object existence only. It does not
-- prove that the operation belongs to the inbox receipt's tenant or owner contract.
-- Every operation-bound inbox row therefore validates the complete immutable
-- authority tuple before INSERT/UPDATE can become durable.

BEGIN;

CREATE FUNCTION system.wave2_guard_inbox_operation_scope()
RETURNS trigger
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = pg_catalog, system
AS $$
DECLARE
    op_tenant_id TEXT;
    op_owner_contract TEXT;
BEGIN
    IF NEW.operation_id IS NULL THEN
        RETURN NEW;
    END IF;

    SELECT tenant_id, owner_contract
      INTO op_tenant_id, op_owner_contract
      FROM system.async_cross_authority_operation
     WHERE operation_id = NEW.operation_id
     FOR SHARE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Wave 2 inbox operation binding references unknown operation authority';
    END IF;

    IF op_tenant_id IS DISTINCT FROM NEW.tenant_id THEN
        RAISE EXCEPTION 'Wave 2 inbox operation tenant does not match immutable receipt tenant authority';
    END IF;

    IF op_owner_contract IS DISTINCT FROM NEW.consumer_contract THEN
        RAISE EXCEPTION 'Wave 2 inbox operation owner contract does not match immutable receipt consumer authority';
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER wave2_inbox_operation_scope_guard
BEFORE INSERT OR UPDATE ON system.async_consumer_inbox
FOR EACH ROW EXECUTE FUNCTION system.wave2_guard_inbox_operation_scope();

COMMENT ON FUNCTION system.wave2_guard_inbox_operation_scope() IS
'Fails closed unless every operation-bound inbox row preserves exact operation_id + tenant_id + owner_contract authority scope. A foreign-key hit or operation_id alone is never completion/reconciliation authority.';

-- No GRANT statements are intentionally present. The trigger applies regardless
-- of the future least-privilege runtime mapping and does not select an operations,
-- broker, reconciliation or database-role product.

COMMIT;
