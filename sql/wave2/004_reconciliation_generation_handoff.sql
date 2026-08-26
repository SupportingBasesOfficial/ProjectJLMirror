-- Wave 2 reconciliation generation handoff hardening.
-- Applies after migrations 001..003.
--
-- Append-only reconciliation rows are durable history. The mutable reconciliation
-- pointer on an operation/receipt describes the transition that made the current
-- state eligible; it must not leak into the next effect attempt. A successor
-- attempt consumes/clears the prior effect_proven_absent pointer while the
-- append-only evidence row remains immutable and addressable.

BEGIN;

CREATE OR REPLACE FUNCTION system.wave2_guard_cross_authority_operation_update()
RETURNS trigger
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = pg_catalog, system
AS $$
DECLARE
    evidence_resolution TEXT;
    evidence_result_id TEXT;
    evidence_result_kind TEXT;
BEGIN
    IF ROW(NEW.operation_id, NEW.tenant_id, NEW.owner_contract, NEW.created_at)
       IS DISTINCT FROM ROW(OLD.operation_id, OLD.tenant_id, OLD.owner_contract, OLD.created_at) THEN
        RAISE EXCEPTION 'Wave 2 cross-authority operation identity/scope is immutable';
    END IF;

    IF OLD.state = 'prepared' AND NEW.state = 'attempting' THEN
        IF NEW.attempt_generation <> OLD.attempt_generation + 1 THEN
            RAISE EXCEPTION 'Wave 2 new attempt must advance exactly one attempt generation';
        END IF;
        IF OLD.reconciliation_resolution IS NOT NULL
           AND OLD.reconciliation_resolution <> 'effect_proven_absent' THEN
            RAISE EXCEPTION 'prepared Wave 2 operation carries non-retry reconciliation state';
        END IF;
        IF NEW.reconciliation_revision IS NOT NULL OR NEW.reconciliation_resolution IS NOT NULL THEN
            RAISE EXCEPTION 'successor Wave 2 attempt must consume prior reconciliation pointer';
        END IF;
    ELSIF OLD.state = 'attempting' AND NEW.state = 'completed' THEN
        IF NEW.reconciliation_revision IS DISTINCT FROM OLD.reconciliation_revision
           OR NEW.reconciliation_resolution IS DISTINCT FROM OLD.reconciliation_resolution THEN
            RAISE EXCEPTION 'direct attempt completion cannot manufacture reconciliation evidence';
        END IF;
    ELSIF OLD.state = 'attempting' AND NEW.state IN ('reconciliation_required', 'failed_terminal') THEN
        IF NEW.reconciliation_revision IS NOT NULL OR NEW.reconciliation_resolution IS NOT NULL THEN
            RAISE EXCEPTION 'attempt failure/ambiguity cannot pre-authorize a reconciliation result';
        END IF;
    ELSIF OLD.state = 'reconciliation_required' AND NEW.state IN ('reconciliation_required', 'prepared', 'completed') THEN
        IF NEW.reconciliation_revision IS NULL THEN
            RAISE EXCEPTION 'Wave 2 reconciliation transition requires append-only evidence revision';
        END IF;
        SELECT resolution, confirmed_result_id, confirmed_result_kind
          INTO evidence_resolution, evidence_result_id, evidence_result_kind
          FROM system.async_cross_authority_reconciliation
         WHERE operation_id = NEW.operation_id
           AND reconciliation_revision = NEW.reconciliation_revision
         FOR SHARE;
        IF NOT FOUND OR NEW.reconciliation_resolution IS DISTINCT FROM evidence_resolution THEN
            RAISE EXCEPTION 'Wave 2 operation reconciliation does not match append-only evidence';
        END IF;
        IF NEW.state = 'reconciliation_required' AND evidence_resolution <> 'still_unknown' THEN
            RAISE EXCEPTION 'still-blocked operation requires still_unknown reconciliation evidence';
        END IF;
        IF NEW.state = 'prepared' AND evidence_resolution <> 'effect_proven_absent' THEN
            RAISE EXCEPTION 'retry eligibility requires effect_proven_absent reconciliation evidence';
        END IF;
        IF NEW.state = 'completed' AND NOT (
            evidence_resolution = 'effect_confirmed'
            AND NEW.outcome_result_id IS NOT DISTINCT FROM evidence_result_id
            AND NEW.outcome_result_kind IS NOT DISTINCT FROM evidence_result_kind
        ) THEN
            RAISE EXCEPTION 'reconciled completion must match confirmed append-only outcome evidence';
        END IF;
    ELSIF NEW.state = OLD.state THEN
        IF OLD.state = 'reconciliation_required' THEN
            RAISE EXCEPTION 'reconciliation_required same-state update must consume a new evidence revision through guarded reconciliation branch';
        END IF;
        IF ROW(NEW.attempt_generation, NEW.executor_id, NEW.attempt_expires_at,
               NEW.execution_admission_revision, NEW.execution_authorization_revision,
               NEW.execution_principal_id, NEW.execution_principal_credential_generation,
               NEW.execution_runtime_profile_id, NEW.execution_runtime_generation,
               NEW.execution_environment_class, NEW.execution_placement_version,
               NEW.execution_fence_scope_id, NEW.execution_fence_epoch,
               NEW.outcome_result_id, NEW.outcome_result_kind, NEW.ambiguity_reason,
               NEW.reconciliation_revision, NEW.reconciliation_resolution)
           IS DISTINCT FROM
           ROW(OLD.attempt_generation, OLD.executor_id, OLD.attempt_expires_at,
               OLD.execution_admission_revision, OLD.execution_authorization_revision,
               OLD.execution_principal_id, OLD.execution_principal_credential_generation,
               OLD.execution_runtime_profile_id, OLD.execution_runtime_generation,
               OLD.execution_environment_class, OLD.execution_placement_version,
               OLD.execution_fence_scope_id, OLD.execution_fence_epoch,
               OLD.outcome_result_id, OLD.outcome_result_kind, OLD.ambiguity_reason,
               OLD.reconciliation_revision, OLD.reconciliation_resolution) THEN
            RAISE EXCEPTION 'same-state Wave 2 operation cannot rewrite claim/outcome/reconciliation evidence';
        END IF;
    ELSE
        RAISE EXCEPTION 'invalid Wave 2 cross-authority operation transition % -> %', OLD.state, NEW.state;
    END IF;
    RETURN NEW;
END;
$$;

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
        IF NEW.execution_generation <> OLD.execution_generation + 1 THEN
            RAISE EXCEPTION 'Wave 2 inbox execution generation must advance exactly once';
        END IF;
        IF NEW.reconciliation_revision IS NOT NULL THEN
            RAISE EXCEPTION 'successor Wave 2 inbox claim must consume prior reconciliation pointer';
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

-- No GRANT statements are intentionally present. Reconciliation history remains
-- append-only while current-attempt pointers are consumed only by guarded state
-- transitions.

COMMIT;
