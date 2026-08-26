-- Wave 2 cross-authority inbox completion hardening.
-- Applies after 001_async_correctness.sql and 002_reconciliation_evidence_and_transition_hardening.sql.
--
-- Once an inbox receipt is bound to a stable cross-authority operation, ordinary
-- processing completion cannot substitute a caller/local result for the durable
-- operation outcome. Direct success must match a completed, non-reconciled
-- operation. Reconciled success exits only through append-only effect_confirmed
-- evidence from the reconciliation_required branch.

BEGIN;

CREATE OR REPLACE FUNCTION system.wave2_guard_consumer_inbox_update()
RETURNS trigger
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = pg_catalog, system
AS $$
DECLARE
    op_state TEXT;
    op_reconciliation_revision TEXT;
    op_reconciliation_resolution TEXT;
    op_result_id TEXT;
    op_result_kind TEXT;
    evidence_resolution TEXT;
    evidence_result_id TEXT;
    evidence_result_kind TEXT;
BEGIN
    IF ROW(NEW.consumer_contract, NEW.message_identity_scope, NEW.message_id, NEW.tenant_id,
           NEW.comparison_profile_id, NEW.comparison_profile_version, NEW.comparison_evidence_form,
           NEW.comparison_verifier_generation, NEW.comparison_evidence, NEW.admitted_at)
       IS DISTINCT FROM
       ROW(OLD.consumer_contract, OLD.message_identity_scope, OLD.message_id, OLD.tenant_id,
           OLD.comparison_profile_id, OLD.comparison_profile_version, OLD.comparison_evidence_form,
           OLD.comparison_verifier_generation, OLD.comparison_evidence, OLD.admitted_at) THEN
        RAISE EXCEPTION 'Wave 2 inbox identity/trusted binding/comparison evidence is immutable';
    END IF;
    IF OLD.operation_id IS NOT NULL AND NEW.operation_id IS DISTINCT FROM OLD.operation_id THEN
        RAISE EXCEPTION 'Wave 2 inbox cannot be rebound to another cross-authority operation';
    END IF;
    IF OLD.operation_id IS NULL AND NEW.operation_id IS NOT NULL
       AND NOT (OLD.state = 'processing' AND NEW.state = 'processing') THEN
        RAISE EXCEPTION 'Wave 2 operation binding is allowed only by the current processing executor';
    END IF;

    IF OLD.state = 'admitted' AND NEW.state = 'processing' THEN
        IF NEW.execution_generation <> OLD.execution_generation + 1
           OR NEW.reconciliation_revision IS DISTINCT FROM OLD.reconciliation_revision THEN
            RAISE EXCEPTION 'Wave 2 inbox claim must advance once without rewriting reconciliation evidence';
        END IF;
    ELSIF OLD.state = 'admitted' AND NEW.state IN ('reconciliation_required', 'quarantined', 'failed_terminal') THEN
        IF NEW.reconciliation_revision IS NOT NULL THEN
            RAISE EXCEPTION 'initial denial/ambiguity cannot manufacture reconciliation evidence';
        END IF;
    ELSIF OLD.state = 'processing' AND NEW.state = 'completed' THEN
        IF NEW.reconciliation_revision IS NOT NULL THEN
            RAISE EXCEPTION 'direct executor completion cannot manufacture reconciliation evidence';
        END IF;
        IF NEW.operation_id IS NOT NULL THEN
            SELECT state, reconciliation_revision, reconciliation_resolution,
                   outcome_result_id, outcome_result_kind
              INTO op_state, op_reconciliation_revision, op_reconciliation_resolution,
                   op_result_id, op_result_kind
              FROM system.async_cross_authority_operation
             WHERE operation_id = NEW.operation_id
             FOR SHARE;
            IF NOT FOUND OR NOT (
                op_state = 'completed'
                AND op_reconciliation_revision IS NULL
                AND op_reconciliation_resolution IS NULL
                AND op_result_id IS NOT DISTINCT FROM NEW.effect_result_id
                AND op_result_kind IS NOT DISTINCT FROM NEW.effect_result_kind
            ) THEN
                RAISE EXCEPTION 'operation-bound Wave 2 inbox completion requires exact direct durable operation outcome';
            END IF;
        END IF;
    ELSIF OLD.state = 'processing' AND NEW.state IN ('reconciliation_required', 'quarantined', 'failed_terminal') THEN
        IF NEW.reconciliation_revision IS NOT NULL THEN
            RAISE EXCEPTION 'executor failure/ambiguity cannot manufacture reconciliation evidence';
        END IF;
    ELSIF OLD.state = 'processing' AND NEW.state = 'processing' THEN
        IF ROW(NEW.executor_id, NEW.execution_generation, NEW.claim_expires_at,
               NEW.execution_admission_revision, NEW.execution_authorization_revision,
               NEW.execution_principal_id, NEW.execution_principal_credential_generation,
               NEW.execution_runtime_profile_id, NEW.execution_runtime_generation,
               NEW.execution_environment_class, NEW.execution_placement_version,
               NEW.execution_fence_scope_id, NEW.execution_fence_epoch,
               NEW.effect_result_id, NEW.effect_result_kind, NEW.terminal_reason,
               NEW.reconciliation_revision)
           IS DISTINCT FROM
           ROW(OLD.executor_id, OLD.execution_generation, OLD.claim_expires_at,
               OLD.execution_admission_revision, OLD.execution_authorization_revision,
               OLD.execution_principal_id, OLD.execution_principal_credential_generation,
               OLD.execution_runtime_profile_id, OLD.execution_runtime_generation,
               OLD.execution_environment_class, OLD.execution_placement_version,
               OLD.execution_fence_scope_id, OLD.execution_fence_epoch,
               OLD.effect_result_id, OLD.effect_result_kind, OLD.terminal_reason,
               OLD.reconciliation_revision) THEN
            RAISE EXCEPTION 'current Wave 2 inbox claim/admission evidence is immutable';
        END IF;
    ELSIF OLD.state = 'reconciliation_required' AND NEW.state IN ('admitted', 'completed') THEN
        IF NEW.operation_id IS NULL OR NEW.reconciliation_revision IS NULL THEN
            RAISE EXCEPTION 'Wave 2 reconciliation exit requires bound operation + evidence revision';
        END IF;
        SELECT o.state, r.resolution, r.confirmed_result_id, r.confirmed_result_kind
          INTO op_state, evidence_resolution, evidence_result_id, evidence_result_kind
          FROM system.async_cross_authority_operation AS o
          JOIN system.async_cross_authority_reconciliation AS r
            ON r.operation_id = o.operation_id
           AND r.reconciliation_revision = NEW.reconciliation_revision
         WHERE o.operation_id = NEW.operation_id
         FOR SHARE OF o, r;
        IF NOT FOUND THEN
            RAISE EXCEPTION 'Wave 2 inbox reconciliation lacks append-only operation evidence';
        END IF;
        IF NEW.state = 'admitted' AND NOT (
            op_state = 'prepared' AND evidence_resolution = 'effect_proven_absent'
        ) THEN
            RAISE EXCEPTION 'Wave 2 retry admission requires reconciled effect absence';
        END IF;
        IF NEW.state = 'completed' AND NOT (
            op_state = 'completed' AND evidence_resolution = 'effect_confirmed'
            AND evidence_result_id IS NOT DISTINCT FROM NEW.effect_result_id
            AND evidence_result_kind IS NOT DISTINCT FROM NEW.effect_result_kind
        ) THEN
            RAISE EXCEPTION 'Wave 2 reconciled completion must match confirmed operation outcome';
        END IF;
    ELSIF NEW.state = OLD.state THEN
        IF ROW(NEW.executor_id, NEW.execution_generation, NEW.claim_expires_at,
               NEW.execution_admission_revision, NEW.execution_authorization_revision,
               NEW.execution_principal_id, NEW.execution_principal_credential_generation,
               NEW.execution_runtime_profile_id, NEW.execution_runtime_generation,
               NEW.execution_environment_class, NEW.execution_placement_version,
               NEW.execution_fence_scope_id, NEW.execution_fence_epoch,
               NEW.effect_result_id, NEW.effect_result_kind, NEW.operation_id,
               NEW.terminal_reason, NEW.reconciliation_revision)
           IS DISTINCT FROM
           ROW(OLD.executor_id, OLD.execution_generation, OLD.claim_expires_at,
               OLD.execution_admission_revision, OLD.execution_authorization_revision,
               OLD.execution_principal_id, OLD.execution_principal_credential_generation,
               OLD.execution_runtime_profile_id, OLD.execution_runtime_generation,
               OLD.execution_environment_class, OLD.execution_placement_version,
               OLD.execution_fence_scope_id, OLD.execution_fence_epoch,
               OLD.effect_result_id, OLD.effect_result_kind, OLD.operation_id,
               OLD.terminal_reason, OLD.reconciliation_revision) THEN
            RAISE EXCEPTION 'same-state Wave 2 inbox cannot rewrite claim/result/reconciliation evidence';
        END IF;
    ELSE
        RAISE EXCEPTION 'invalid Wave 2 inbox transition % -> %', OLD.state, NEW.state;
    END IF;
    RETURN NEW;
END;
$$;

-- No GRANT statements are intentionally present. Runtime mutation capabilities
-- remain a separately reviewed C2 mapping and cannot bypass this trigger contract.

COMMIT;
