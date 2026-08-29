\set ON_ERROR_STOP on

-- Panoramic edge hardening for provider dataset revision authority.
-- Row-level INSERT/UPDATE/DELETE coverage is not enough: TRUNCATE is a
-- statement-level destructive mutation and must fail closed as well. The
-- reconciliation worker is intentionally not a provider-history writer and
-- cannot administer table triggers.

SET ROLE history_reconcile_owner;

CREATE OR REPLACE FUNCTION history_reconcile_evidence.provider_history_truncate_guard()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, history_reconcile_evidence
AS $$
BEGIN
    RAISE EXCEPTION 'provider history truncate requires explicit gap authority';
END;
$$;

DROP TRIGGER IF EXISTS provider_history_truncate_guard
  ON history_reconcile_evidence.provider_visible_history;
CREATE TRIGGER provider_history_truncate_guard
BEFORE TRUNCATE
ON history_reconcile_evidence.provider_visible_history
FOR EACH STATEMENT
EXECUTE FUNCTION history_reconcile_evidence.provider_history_truncate_guard();

REVOKE ALL ON FUNCTION history_reconcile_evidence.provider_history_truncate_guard()
  FROM PUBLIC, history_reconcile_worker;

RESET ROLE;

-- The worker consumes only governed reconciliation functions. It has no direct
-- provider dataset mutation privilege and no ownership path to disable triggers.
DO $$
DECLARE
    v_direct_mutation boolean;
    v_owner_membership boolean;
BEGIN
    SELECT
        has_table_privilege(
            'history_reconcile_worker',
            'history_reconcile_evidence.provider_visible_history',
            'INSERT'
        )
        OR has_table_privilege(
            'history_reconcile_worker',
            'history_reconcile_evidence.provider_visible_history',
            'UPDATE'
        )
        OR has_table_privilege(
            'history_reconcile_worker',
            'history_reconcile_evidence.provider_visible_history',
            'DELETE'
        )
        OR has_table_privilege(
            'history_reconcile_worker',
            'history_reconcile_evidence.provider_visible_history',
            'TRUNCATE'
        )
      INTO v_direct_mutation;

    SELECT pg_has_role(
        'history_reconcile_worker',
        'history_reconcile_owner',
        'MEMBER'
    ) INTO v_owner_membership;

    IF v_direct_mutation THEN
        RAISE EXCEPTION 'history reconciliation worker unexpectedly has direct provider mutation privilege';
    END IF;
    IF v_owner_membership THEN
        RAISE EXCEPTION 'history reconciliation worker unexpectedly inherits provider dataset owner authority';
    END IF;
END;
$$;

SELECT 'history_worker_no_direct_provider_mutation=PASS' AS result;
SELECT 'history_worker_cannot_administer_provider_triggers=PASS' AS result;

-- Even the privileged evidence owner cannot accidentally translate TRUNCATE
-- into a new invisible provider snapshot: the statement is rejected before any
-- rows disappear. Production owner/superuser governance remains a deployment
-- trust boundary; this vector proves the evidence model itself fails closed.
SET ROLE history_reconcile_owner;
DO $$
DECLARE
    v_before bigint;
    v_after bigint;
BEGIN
    SELECT count(*) INTO v_before
      FROM history_reconcile_evidence.provider_visible_history;

    BEGIN
        TRUNCATE history_reconcile_evidence.provider_visible_history;
        RAISE EXCEPTION 'provider history truncate unexpectedly allowed';
    EXCEPTION WHEN OTHERS THEN
        IF SQLERRM NOT LIKE '%provider history truncate requires explicit gap authority%' THEN
            RAISE;
        END IF;
    END;

    SELECT count(*) INTO v_after
      FROM history_reconcile_evidence.provider_visible_history;
    IF v_after <> v_before THEN
        RAISE EXCEPTION 'failed provider truncate changed visible-history cardinality';
    END IF;
END;
$$;
RESET ROLE;

SELECT 'history_provider_truncate_fails_closed=PASS' AS result;
