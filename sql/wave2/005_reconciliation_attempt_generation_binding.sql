-- Wave 2 reconciliation evidence attempt-generation binding hardening.
-- Applies after migrations 001..004.
--
-- A reconciliation revision is durable evidence about one exact effect attempt.
-- Historical proof that attempt N was absent/confirmed cannot authorize a later
-- ambiguous attempt N+1. The append-only row therefore records the exact
-- attempt_generation observed while the operation is reconciliation_required,
-- and every operation/inbox reconciliation exit must consume evidence from the
-- operation's current ambiguous attempt generation.

BEGIN;

ALTER TABLE system.async_cross_authority_reconciliation
    ADD COLUMN attempt_generation BIGINT NULL
    CHECK (attempt_generation > 0);

DO $wave2_attempt_binding$
BEGIN
    IF EXISTS (SELECT 1 FROM system.async_cross_authority_reconciliation) THEN
        RAISE EXCEPTION
            'Wave 2 attempt-generation hardening cannot infer historical reconciliation attempt binding; reviewed migration required';
    END IF;
END;
$wave2_attempt_binding$;

ALTER TABLE system.async_cross_authority_reconciliation
    ALTER COLUMN attempt_generation SET NOT NULL;

COMMENT ON COLUMN system.async_cross_authority_reconciliation.attempt_generation IS
'Exact cross-authority operation attempt generation whose ambiguity this immutable reconciliation evidence resolves. Prior-attempt evidence is never successor-attempt authority.';

CREATE OR REPLACE FUNCTION system.wave2_guard_reconciliation_insert()
RETURNS trigger
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = pg_catalog, system
AS $$
DECLARE
    op_state TEXT;
    op_attempt_generation BIGINT;
BEGIN
    SELECT state, attempt_generation
      INTO op_state, op_attempt_generation
      FROM system.async_cross_authority_operation
     WHERE operation_id = NEW.operation_id
     FOR UPDATE;

    IF NOT FOUND OR op_state <> 'reconciliation_required' THEN
        RAISE EXCEPTION 'Wave 2 reconciliation evidence requires currently reconciliation-blocked operation';
    END IF;
    IF NEW.attempt_generation IS DISTINCT FROM op_attempt_generation THEN
        RAISE EXCEPTION 'Wave 2 reconciliation evidence must bind the current ambiguous attempt generation';
    END IF;
    IF NEW.attempt_generation < 1 THEN
        RAISE EXCEPTION 'Wave 2 reconciliation evidence requires a concrete positive attempt generation';
    END IF;
    RETURN NEW;
END;
$$;

CREATE FUNCTION system.wave2_guard_operation_reconciliation_attempt_binding()
RETURNS trigger
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = pg_catalog, system
AS $$
DECLARE
    evidence_attempt_generation BIGINT;
BEGIN
    IF OLD.state = 'reconciliation_required'
       AND NEW.state IN ('reconciliation_required', 'prepared', 'completed') THEN
        IF NEW.reconciliation_revision IS NULL THEN
            RAISE EXCEPTION 'Wave 2 reconciliation transition requires a durable evidence revision';
        END IF;
        SELECT attempt_generation
          INTO evidence_attempt_generation
          FROM system.async_cross_authority_reconciliation
         WHERE operation_id = NEW.operation_id
           AND reconciliation_revision = NEW.reconciliation_revision
         FOR SHARE;
        IF NOT FOUND OR evidence_attempt_generation IS DISTINCT FROM OLD.attempt_generation THEN
            RAISE EXCEPTION 'Wave 2 reconciliation evidence belongs to another effect attempt generation';
        END IF;
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER wave2_operation_reconciliation_attempt_binding_guard
BEFORE UPDATE ON system.async_cross_authority_operation
FOR EACH ROW EXECUTE FUNCTION system.wave2_guard_operation_reconciliation_attempt_binding();

CREATE FUNCTION system.wave2_guard_inbox_reconciliation_attempt_binding()
RETURNS trigger
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = pg_catalog, system
AS $$
DECLARE
    op_attempt_generation BIGINT;
    evidence_attempt_generation BIGINT;
BEGIN
    IF OLD.state = 'reconciliation_required' AND NEW.state IN ('admitted', 'completed') THEN
        IF NEW.operation_id IS NULL OR NEW.reconciliation_revision IS NULL THEN
            RAISE EXCEPTION 'Wave 2 inbox reconciliation exit requires bound operation + evidence revision';
        END IF;

        SELECT o.attempt_generation, r.attempt_generation
          INTO op_attempt_generation, evidence_attempt_generation
          FROM system.async_cross_authority_operation AS o
          JOIN system.async_cross_authority_reconciliation AS r
            ON r.operation_id = o.operation_id
           AND r.reconciliation_revision = NEW.reconciliation_revision
         WHERE o.operation_id = NEW.operation_id
         FOR SHARE OF o, r;

        IF NOT FOUND OR evidence_attempt_generation IS DISTINCT FROM op_attempt_generation THEN
            RAISE EXCEPTION 'Wave 2 inbox reconciliation evidence is not bound to the operation current attempt generation';
        END IF;
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER wave2_inbox_reconciliation_attempt_binding_guard
BEFORE UPDATE ON system.async_consumer_inbox
FOR EACH ROW EXECUTE FUNCTION system.wave2_guard_inbox_reconciliation_attempt_binding();

-- No GRANT statements are intentionally present. This hardening changes only
-- correctness invariants; runtime/reconciler privileges remain a separate C2
-- least-privilege mapping and cannot bypass these triggers through direct writes.

COMMIT;
