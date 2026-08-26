-- Wave 2 durable correctness records.
-- Authority base: main@ff932cec10e3b7dcc13b050bb09d4a7efd634598
--
-- This migration deliberately selects no broker, cache, KMS, schema registry,
-- pooler/HA topology or Product behavior. It materializes PostgreSQL records for
-- the accepted transactional business/authority substrate. Owning use cases are
-- responsible for committing domain mutation + required audit intent + outbox
-- insert in ONE transaction. A dispatcher is never domain-fact authority.
--
-- Critical Wave 2 objects are intentionally CREATE-without-IF-NOT-EXISTS. A
-- pre-existing same-name table/function/trigger is not evidence that its shape,
-- constraints, ownership or transition semantics conform; reuse therefore fails
-- closed and must be handled by a separately reviewed migration/revalidation.

BEGIN;

CREATE SCHEMA IF NOT EXISTS system;

CREATE TABLE system.async_outbox_message (
    outbox_record_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    producer_message_scope TEXT NOT NULL,
    message_id TEXT NOT NULL,
    message_class TEXT NOT NULL CHECK (message_class IN (
        'domain_event', 'integration_event', 'job_command', 'process_signal',
        'realtime_projection', 'outbound_webhook_delivery'
    )),
    contract_name TEXT NOT NULL,
    contract_version TEXT NOT NULL,
    producer TEXT NOT NULL,
    producer_generation TEXT NULL,
    scope_class TEXT NOT NULL CHECK (scope_class IN ('tenant', 'global')),
    tenant_id TEXT NULL,
    subject_type TEXT NULL,
    subject_id TEXT NULL,
    occurred_at TIMESTAMPTZ NULL,
    created_at TIMESTAMPTZ NULL,
    operation_id TEXT NULL,
    not_before TIMESTAMPTZ NULL,
    deadline TIMESTAMPTZ NULL,
    correlation_id TEXT NOT NULL,
    causation_id TEXT NULL,
    data_classification TEXT NOT NULL,
    serialization_profile_id TEXT NOT NULL,
    encoded_payload BYTEA NOT NULL,
    comparison_profile_id TEXT NOT NULL,
    comparison_profile_version TEXT NOT NULL,
    comparison_evidence_form TEXT NOT NULL,
    comparison_verifier_generation TEXT NULL,
    comparison_evidence BYTEA NOT NULL CHECK (octet_length(comparison_evidence) > 0),
    committed_at TIMESTAMPTZ NOT NULL DEFAULT transaction_timestamp(),
    UNIQUE (producer_message_scope, message_id),
    CHECK (
        (scope_class = 'tenant' AND tenant_id IS NOT NULL)
        OR (scope_class = 'global' AND tenant_id IS NULL)
    ),
    CHECK ((subject_type IS NULL) = (subject_id IS NULL)),
    CHECK (
        (message_class IN ('domain_event', 'integration_event', 'realtime_projection')
            AND occurred_at IS NOT NULL AND created_at IS NULL)
        OR (message_class IN ('job_command', 'process_signal', 'outbound_webhook_delivery')
            AND created_at IS NOT NULL AND occurred_at IS NULL)
    ),
    CHECK (message_class <> 'job_command' OR operation_id IS NOT NULL),
    CHECK (message_class = 'job_command' OR (not_before IS NULL AND deadline IS NULL)),
    CHECK (not_before IS NULL OR not_before >= created_at),
    CHECK (deadline IS NULL OR deadline >= created_at),
    CHECK (deadline IS NULL OR not_before IS NULL OR deadline >= not_before)
);

COMMENT ON TABLE system.async_outbox_message IS
'Immutable logical publication evidence. Normal runtime dispatch bookkeeping belongs in async_outbox_dispatch, not this table.';

CREATE FUNCTION system.wave2_reject_outbox_immutable_update()
RETURNS trigger
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = pg_catalog, system
AS $$
BEGIN
    RAISE EXCEPTION 'immutable Wave 2 outbox message cannot be updated';
END;
$$;

CREATE TRIGGER wave2_outbox_immutable_update_guard
BEFORE UPDATE ON system.async_outbox_message
FOR EACH ROW EXECUTE FUNCTION system.wave2_reject_outbox_immutable_update();

CREATE TABLE system.async_outbox_dispatch (
    outbox_record_id BIGINT PRIMARY KEY
        REFERENCES system.async_outbox_message(outbox_record_id) ON DELETE RESTRICT,
    state TEXT NOT NULL DEFAULT 'pending' CHECK (state IN ('pending', 'claimed', 'published', 'quarantined')),
    claim_owner TEXT NULL,
    claim_generation BIGINT NOT NULL DEFAULT 0 CHECK (claim_generation >= 0),
    claim_expires_at TIMESTAMPTZ NULL,
    attempt_count BIGINT NOT NULL DEFAULT 0 CHECK (attempt_count >= 0),
    next_attempt_at TIMESTAMPTZ NULL,
    last_error_class TEXT NULL,
    published_at TIMESTAMPTZ NULL,
    broker_receipt_ref TEXT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT transaction_timestamp(),
    CHECK (
        (state = 'claimed' AND claim_owner IS NOT NULL AND claim_expires_at IS NOT NULL)
        OR (state <> 'claimed' AND claim_owner IS NULL AND claim_expires_at IS NULL)
    ),
    CHECK (state <> 'published' OR (published_at IS NOT NULL AND broker_receipt_ref IS NOT NULL))
);

COMMENT ON TABLE system.async_outbox_dispatch IS
'Mutable publication-attempt state. Claim exclusivity does not imply exactly-once delivery. Claim expiry permits same-message redispatch only; it never proves broker-effect absence.';

CREATE FUNCTION system.wave2_guard_outbox_dispatch_update()
RETURNS trigger
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = pg_catalog, system
AS $$
BEGIN
    IF NEW.outbox_record_id IS DISTINCT FROM OLD.outbox_record_id THEN
        RAISE EXCEPTION 'Wave 2 dispatch record cannot be rebound to another outbox message';
    END IF;
    IF OLD.state = 'published' AND NEW.state <> 'published' THEN
        RAISE EXCEPTION 'published Wave 2 dispatch state cannot be reset by ordinary update';
    END IF;
    IF OLD.state = 'quarantined' AND NEW.state <> 'quarantined' THEN
        RAISE EXCEPTION 'quarantined Wave 2 dispatch requires separately governed redrive';
    END IF;
    IF OLD.state = 'pending' AND NEW.state NOT IN ('pending', 'claimed', 'quarantined') THEN
        RAISE EXCEPTION 'invalid Wave 2 pending dispatch transition';
    END IF;
    IF OLD.state = 'claimed' AND NEW.state NOT IN ('claimed', 'pending', 'published', 'quarantined') THEN
        RAISE EXCEPTION 'invalid Wave 2 claimed dispatch transition';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER wave2_outbox_dispatch_update_guard
BEFORE UPDATE ON system.async_outbox_dispatch
FOR EACH ROW EXECUTE FUNCTION system.wave2_guard_outbox_dispatch_update();

CREATE FUNCTION system.wave2_initialize_outbox_dispatch()
RETURNS trigger
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = pg_catalog, system
AS $$
BEGIN
    INSERT INTO system.async_outbox_dispatch(outbox_record_id) VALUES (NEW.outbox_record_id);
    RETURN NEW;
END;
$$;

CREATE TRIGGER wave2_outbox_dispatch_initialize
AFTER INSERT ON system.async_outbox_message
FOR EACH ROW EXECUTE FUNCTION system.wave2_initialize_outbox_dispatch();

CREATE TABLE system.async_cross_authority_operation (
    operation_id TEXT PRIMARY KEY,
    tenant_id TEXT NULL,
    owner_contract TEXT NOT NULL,
    state TEXT NOT NULL DEFAULT 'prepared' CHECK (state IN (
        'prepared', 'attempting', 'completed', 'reconciliation_required', 'failed_terminal'
    )),
    attempt_generation BIGINT NOT NULL DEFAULT 0 CHECK (attempt_generation >= 0),
    executor_id TEXT NULL,
    attempt_expires_at TIMESTAMPTZ NULL,
    execution_admission_revision TEXT NULL,
    execution_authorization_revision TEXT NULL,
    execution_principal_id TEXT NULL,
    execution_principal_credential_generation TEXT NULL,
    execution_runtime_profile_id TEXT NULL,
    execution_runtime_generation TEXT NULL,
    execution_environment_class TEXT NULL,
    execution_placement_version TEXT NULL,
    execution_fence_scope_id TEXT NULL,
    execution_fence_epoch BIGINT NULL CHECK (execution_fence_epoch IS NULL OR execution_fence_epoch > 0),
    outcome_result_id TEXT NULL,
    outcome_result_kind TEXT NULL,
    ambiguity_reason TEXT NULL,
    reconciliation_revision TEXT NULL,
    reconciliation_resolution TEXT NULL CHECK (
        reconciliation_resolution IS NULL OR reconciliation_resolution IN (
            'effect_confirmed', 'effect_proven_absent', 'still_unknown'
        )
    ),
    created_at TIMESTAMPTZ NOT NULL DEFAULT transaction_timestamp(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT transaction_timestamp(),
    CHECK ((outcome_result_id IS NULL) = (outcome_result_kind IS NULL)),
    CHECK ((reconciliation_revision IS NULL) = (reconciliation_resolution IS NULL)),
    CHECK (
        (state = 'attempting'
            AND executor_id IS NOT NULL AND attempt_expires_at IS NOT NULL
            AND execution_admission_revision IS NOT NULL
            AND execution_authorization_revision IS NOT NULL
            AND execution_principal_id IS NOT NULL
            AND execution_principal_credential_generation IS NOT NULL
            AND execution_runtime_profile_id IN ('runtime.api@1', 'runtime.worker@1')
            AND execution_runtime_generation IS NOT NULL
            AND execution_environment_class IS NOT NULL)
        OR (state <> 'attempting' AND executor_id IS NULL AND attempt_expires_at IS NULL)
    ),
    CHECK (
        tenant_id IS NULL OR state <> 'attempting' OR (
            execution_placement_version IS NOT NULL
            AND execution_fence_scope_id IS NOT NULL
            AND execution_fence_epoch IS NOT NULL
        )
    ),
    CHECK (tenant_id IS NOT NULL OR execution_placement_version IS NULL),
    CHECK (state <> 'completed' OR outcome_result_id IS NOT NULL),
    CHECK (state <> 'reconciliation_required' OR ambiguity_reason IS NOT NULL),
    CHECK (
        state <> 'prepared'
        OR reconciliation_resolution IS NULL
        OR reconciliation_resolution = 'effect_proven_absent'
    )
);

COMMENT ON TABLE system.async_cross_authority_operation IS
'Stable operation identity for effects that cannot commit atomically with inbox state. Ambiguous outcome or attempt-lease loss blocks blind retry. Reconciliation transitions retain a stable evidence revision.';

CREATE FUNCTION system.wave2_guard_cross_authority_operation_update()
RETURNS trigger
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = pg_catalog, system
AS $$
BEGIN
    IF ROW(NEW.operation_id, NEW.tenant_id, NEW.owner_contract, NEW.created_at)
       IS DISTINCT FROM ROW(OLD.operation_id, OLD.tenant_id, OLD.owner_contract, OLD.created_at) THEN
        RAISE EXCEPTION 'Wave 2 cross-authority operation identity/scope is immutable';
    END IF;

    IF OLD.state = 'prepared' AND NEW.state = 'attempting' THEN
        IF NEW.attempt_generation <> OLD.attempt_generation + 1 THEN
            RAISE EXCEPTION 'Wave 2 attempt generation must advance exactly once';
        END IF;
    ELSIF OLD.state = 'attempting' AND NEW.state IN ('completed', 'reconciliation_required', 'failed_terminal') THEN
        NULL;
    ELSIF OLD.state = 'reconciliation_required' AND NEW.state = 'reconciliation_required' THEN
        IF NEW.reconciliation_resolution IS DISTINCT FROM 'still_unknown'
           OR NEW.reconciliation_revision IS NULL THEN
            RAISE EXCEPTION 'still-blocked reconciliation requires durable still_unknown evidence';
        END IF;
    ELSIF OLD.state = 'reconciliation_required' AND NEW.state = 'prepared' THEN
        IF NEW.reconciliation_resolution IS DISTINCT FROM 'effect_proven_absent'
           OR NEW.reconciliation_revision IS NULL THEN
            RAISE EXCEPTION 'retry eligibility requires durable effect-proven-absent reconciliation';
        END IF;
    ELSIF OLD.state = 'reconciliation_required' AND NEW.state = 'completed' THEN
        IF NEW.reconciliation_resolution IS DISTINCT FROM 'effect_confirmed'
           OR NEW.reconciliation_revision IS NULL OR NEW.outcome_result_id IS NULL THEN
            RAISE EXCEPTION 'reconciled completion requires durable confirmed-effect evidence';
        END IF;
    ELSIF NEW.state = OLD.state THEN
        IF OLD.state IN ('completed', 'failed_terminal') THEN
            IF ROW(NEW.outcome_result_id, NEW.outcome_result_kind, NEW.ambiguity_reason,
                   NEW.reconciliation_revision, NEW.reconciliation_resolution)
               IS DISTINCT FROM ROW(OLD.outcome_result_id, OLD.outcome_result_kind, OLD.ambiguity_reason,
                   OLD.reconciliation_revision, OLD.reconciliation_resolution) THEN
                RAISE EXCEPTION 'terminal Wave 2 operation outcome/evidence is immutable';
            END IF;
        END IF;
    ELSE
        RAISE EXCEPTION 'invalid Wave 2 cross-authority operation transition % -> %', OLD.state, NEW.state;
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER wave2_cross_authority_operation_update_guard
BEFORE UPDATE ON system.async_cross_authority_operation
FOR EACH ROW EXECUTE FUNCTION system.wave2_guard_cross_authority_operation_update();

CREATE TABLE system.async_consumer_inbox (
    consumer_contract TEXT NOT NULL,
    message_identity_scope TEXT NOT NULL,
    message_id TEXT NOT NULL,
    tenant_id TEXT NULL,
    comparison_profile_id TEXT NOT NULL,
    comparison_profile_version TEXT NOT NULL,
    comparison_evidence_form TEXT NOT NULL,
    comparison_verifier_generation TEXT NULL,
    comparison_evidence BYTEA NOT NULL CHECK (octet_length(comparison_evidence) > 0),
    state TEXT NOT NULL DEFAULT 'admitted' CHECK (state IN (
        'admitted', 'processing', 'completed', 'failed_terminal', 'reconciliation_required', 'quarantined'
    )),
    executor_id TEXT NULL,
    execution_generation BIGINT NOT NULL DEFAULT 0 CHECK (execution_generation >= 0),
    claim_expires_at TIMESTAMPTZ NULL,
    execution_admission_revision TEXT NULL,
    execution_authorization_revision TEXT NULL,
    execution_principal_id TEXT NULL,
    execution_principal_credential_generation TEXT NULL,
    execution_runtime_profile_id TEXT NULL,
    execution_runtime_generation TEXT NULL,
    execution_environment_class TEXT NULL,
    execution_placement_version TEXT NULL,
    execution_fence_scope_id TEXT NULL,
    execution_fence_epoch BIGINT NULL CHECK (execution_fence_epoch IS NULL OR execution_fence_epoch > 0),
    effect_result_id TEXT NULL,
    effect_result_kind TEXT NULL,
    operation_id TEXT NULL REFERENCES system.async_cross_authority_operation(operation_id) ON DELETE RESTRICT,
    terminal_reason TEXT NULL,
    reconciliation_revision TEXT NULL,
    admitted_at TIMESTAMPTZ NOT NULL DEFAULT transaction_timestamp(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT transaction_timestamp(),
    PRIMARY KEY (consumer_contract, message_identity_scope, message_id),
    CHECK ((effect_result_id IS NULL) = (effect_result_kind IS NULL)),
    CHECK (
        (state = 'processing'
            AND executor_id IS NOT NULL AND claim_expires_at IS NOT NULL
            AND execution_admission_revision IS NOT NULL
            AND execution_authorization_revision IS NOT NULL
            AND execution_principal_id IS NOT NULL
            AND execution_principal_credential_generation IS NOT NULL
            AND execution_runtime_profile_id IN ('runtime.api@1', 'runtime.worker@1')
            AND execution_runtime_generation IS NOT NULL
            AND execution_environment_class IS NOT NULL)
        OR (state <> 'processing' AND executor_id IS NULL AND claim_expires_at IS NULL)
    ),
    CHECK (
        tenant_id IS NULL OR state <> 'processing' OR (
            execution_placement_version IS NOT NULL
            AND execution_fence_scope_id IS NOT NULL
            AND execution_fence_epoch IS NOT NULL
        )
    ),
    CHECK (tenant_id IS NOT NULL OR execution_placement_version IS NULL),
    CHECK (state <> 'completed' OR effect_result_id IS NOT NULL),
    CHECK (state NOT IN ('reconciliation_required', 'quarantined', 'failed_terminal') OR terminal_reason IS NOT NULL)
);

COMMENT ON TABLE system.async_consumer_inbox IS
'Durable create-or-observe receipt keyed by (consumer_contract, message_identity_scope, message_id). Identity/comparison evidence/trusted tenant binding are immutable. Processing requires current execution evidence; lease loss becomes reconciliation.';

CREATE FUNCTION system.wave2_guard_consumer_inbox_update()
RETURNS trigger
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = pg_catalog, system
AS $$
DECLARE
    op_state TEXT;
    op_resolution TEXT;
    op_revision TEXT;
    op_result_id TEXT;
    op_result_kind TEXT;
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
    ELSIF OLD.state = 'admitted' AND NEW.state IN ('reconciliation_required', 'quarantined', 'failed_terminal') THEN
        NULL;
    ELSIF OLD.state = 'processing' AND NEW.state IN ('completed', 'reconciliation_required', 'quarantined', 'failed_terminal') THEN
        NULL;
    ELSIF OLD.state = 'processing' AND NEW.state = 'processing' THEN
        IF ROW(NEW.executor_id, NEW.execution_generation, NEW.claim_expires_at,
               NEW.execution_admission_revision, NEW.execution_authorization_revision,
               NEW.execution_principal_id, NEW.execution_principal_credential_generation,
               NEW.execution_runtime_profile_id, NEW.execution_runtime_generation,
               NEW.execution_environment_class, NEW.execution_placement_version,
               NEW.execution_fence_scope_id, NEW.execution_fence_epoch)
           IS DISTINCT FROM
           ROW(OLD.executor_id, OLD.execution_generation, OLD.claim_expires_at,
               OLD.execution_admission_revision, OLD.execution_authorization_revision,
               OLD.execution_principal_id, OLD.execution_principal_credential_generation,
               OLD.execution_runtime_profile_id, OLD.execution_runtime_generation,
               OLD.execution_environment_class, OLD.execution_placement_version,
               OLD.execution_fence_scope_id, OLD.execution_fence_epoch) THEN
            RAISE EXCEPTION 'current Wave 2 inbox claim/admission evidence is immutable';
        END IF;
    ELSIF OLD.state = 'reconciliation_required' AND NEW.state IN ('admitted', 'completed') THEN
        IF NEW.reconciliation_revision IS NULL THEN
            RAISE EXCEPTION 'Wave 2 reconciliation transition requires stable evidence revision';
        END IF;
        IF NEW.operation_id IS NOT NULL THEN
            SELECT state, reconciliation_resolution, reconciliation_revision,
                   outcome_result_id, outcome_result_kind
              INTO op_state, op_resolution, op_revision, op_result_id, op_result_kind
              FROM system.async_cross_authority_operation
             WHERE operation_id = NEW.operation_id;
            IF NOT FOUND OR op_revision IS DISTINCT FROM NEW.reconciliation_revision THEN
                RAISE EXCEPTION 'Wave 2 inbox reconciliation is not bound to operation evidence';
            END IF;
            IF NEW.state = 'admitted' AND NOT (
                op_state = 'prepared' AND op_resolution = 'effect_proven_absent'
            ) THEN
                RAISE EXCEPTION 'Wave 2 retry admission requires reconciled effect absence';
            END IF;
            IF NEW.state = 'completed' AND NOT (
                op_state = 'completed' AND op_resolution = 'effect_confirmed'
                AND op_result_id IS NOT DISTINCT FROM NEW.effect_result_id
                AND op_result_kind IS NOT DISTINCT FROM NEW.effect_result_kind
            ) THEN
                RAISE EXCEPTION 'Wave 2 reconciled completion must match confirmed operation outcome';
            END IF;
        END IF;
    ELSIF NEW.state = OLD.state THEN
        IF OLD.state IN ('completed', 'failed_terminal', 'quarantined') THEN
            IF ROW(NEW.effect_result_id, NEW.effect_result_kind, NEW.operation_id,
                   NEW.terminal_reason, NEW.reconciliation_revision)
               IS DISTINCT FROM
               ROW(OLD.effect_result_id, OLD.effect_result_kind, OLD.operation_id,
                   OLD.terminal_reason, OLD.reconciliation_revision) THEN
                RAISE EXCEPTION 'terminal/quarantined Wave 2 inbox evidence is immutable';
            END IF;
        END IF;
    ELSE
        RAISE EXCEPTION 'invalid Wave 2 inbox transition % -> %', OLD.state, NEW.state;
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER wave2_consumer_inbox_update_guard
BEFORE UPDATE ON system.async_consumer_inbox
FOR EACH ROW EXECUTE FUNCTION system.wave2_guard_consumer_inbox_update();

-- No GRANT statements are intentionally present. Concrete serving/worker/admin
-- privileges remain a separately reviewed runtime/operational mapping and SHALL
-- preserve logical ownership and least privilege. Runtime roles should receive
-- only reviewed transition/function capabilities, not blanket table-owner power.

COMMIT;
