-- Wave 2 durable correctness records.
-- Authority base: main@ff932cec10e3b7dcc13b050bb09d4a7efd634598
--
-- This migration deliberately selects no broker, cache, KMS, schema registry,
-- pooler/HA topology or Product behavior. It materializes PostgreSQL records for
-- the accepted transactional business/authority substrate. Owning use cases are
-- responsible for committing domain mutation + required audit intent + outbox
-- insert in ONE transaction. A dispatcher is never domain-fact authority.

BEGIN;

CREATE SCHEMA IF NOT EXISTS system;

CREATE TABLE IF NOT EXISTS system.async_outbox_message (
    outbox_record_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    producer_message_scope TEXT NOT NULL,
    message_id TEXT NOT NULL,
    message_class TEXT NOT NULL CHECK (message_class IN (
        'domain_event',
        'integration_event',
        'job_command',
        'process_signal',
        'realtime_projection',
        'outbound_webhook_delivery'
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
        (
            message_class IN ('domain_event', 'integration_event', 'realtime_projection')
            AND occurred_at IS NOT NULL
            AND created_at IS NULL
        )
        OR (
            message_class IN ('job_command', 'process_signal', 'outbound_webhook_delivery')
            AND created_at IS NOT NULL
            AND occurred_at IS NULL
        )
    ),
    CHECK (message_class <> 'job_command' OR operation_id IS NOT NULL),
    CHECK (
        message_class = 'job_command'
        OR (not_before IS NULL AND deadline IS NULL)
    ),
    CHECK (not_before IS NULL OR not_before >= created_at),
    CHECK (deadline IS NULL OR deadline >= created_at),
    CHECK (deadline IS NULL OR not_before IS NULL OR deadline >= not_before)
);

COMMENT ON TABLE system.async_outbox_message IS
'Immutable logical publication evidence. Normal runtime dispatch bookkeeping belongs in async_outbox_dispatch, not this table. Event/fact classes retain occurred_at; work/process classes retain created_at. A job command carries stable operation_id.';

CREATE OR REPLACE FUNCTION system.wave2_reject_outbox_immutable_update()
RETURNS trigger
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = pg_catalog, system
AS $$
BEGIN
    RAISE EXCEPTION 'immutable Wave 2 outbox message cannot be updated';
END;
$$;

DROP TRIGGER IF EXISTS wave2_outbox_immutable_update_guard ON system.async_outbox_message;
CREATE TRIGGER wave2_outbox_immutable_update_guard
BEFORE UPDATE ON system.async_outbox_message
FOR EACH ROW
EXECUTE FUNCTION system.wave2_reject_outbox_immutable_update();

CREATE TABLE IF NOT EXISTS system.async_outbox_dispatch (
    outbox_record_id BIGINT PRIMARY KEY
        REFERENCES system.async_outbox_message(outbox_record_id) ON DELETE RESTRICT,
    state TEXT NOT NULL DEFAULT 'pending' CHECK (state IN (
        'pending', 'claimed', 'published', 'quarantined'
    )),
    claim_owner TEXT NULL,
    claim_generation BIGINT NOT NULL DEFAULT 0 CHECK (claim_generation >= 0),
    attempt_count BIGINT NOT NULL DEFAULT 0 CHECK (attempt_count >= 0),
    next_attempt_at TIMESTAMPTZ NULL,
    last_error_class TEXT NULL,
    published_at TIMESTAMPTZ NULL,
    broker_receipt_ref TEXT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT transaction_timestamp(),
    CHECK (
        (state = 'claimed' AND claim_owner IS NOT NULL)
        OR (state <> 'claimed' AND claim_owner IS NULL)
    ),
    CHECK (
        state <> 'published'
        OR (published_at IS NOT NULL AND broker_receipt_ref IS NOT NULL)
    )
);

COMMENT ON TABLE system.async_outbox_dispatch IS
'Mutable publication-attempt state. Claim exclusivity does not imply exactly-once delivery.';

CREATE TABLE IF NOT EXISTS system.async_cross_authority_operation (
    operation_id TEXT PRIMARY KEY,
    tenant_id TEXT NULL,
    owner_contract TEXT NOT NULL,
    state TEXT NOT NULL DEFAULT 'prepared' CHECK (state IN (
        'prepared',
        'attempting',
        'completed',
        'reconciliation_required',
        'failed_terminal'
    )),
    attempt_generation BIGINT NOT NULL DEFAULT 0 CHECK (attempt_generation >= 0),
    executor_id TEXT NULL,
    outcome_result_id TEXT NULL,
    outcome_result_kind TEXT NULL,
    ambiguity_reason TEXT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT transaction_timestamp(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT transaction_timestamp(),
    CHECK ((outcome_result_id IS NULL) = (outcome_result_kind IS NULL)),
    CHECK (
        (state = 'attempting' AND executor_id IS NOT NULL)
        OR (state <> 'attempting' AND executor_id IS NULL)
    ),
    CHECK (
        state <> 'completed'
        OR outcome_result_id IS NOT NULL
    ),
    CHECK (
        state <> 'reconciliation_required'
        OR ambiguity_reason IS NOT NULL
    )
);

COMMENT ON TABLE system.async_cross_authority_operation IS
'Stable operation identity for effects that cannot commit atomically with inbox state. Ambiguous outcome blocks blind retry.';

CREATE TABLE IF NOT EXISTS system.async_consumer_inbox (
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
        'admitted',
        'processing',
        'completed',
        'failed_terminal',
        'reconciliation_required',
        'quarantined'
    )),
    executor_id TEXT NULL,
    execution_generation BIGINT NOT NULL DEFAULT 0 CHECK (execution_generation >= 0),
    effect_result_id TEXT NULL,
    effect_result_kind TEXT NULL,
    operation_id TEXT NULL
        REFERENCES system.async_cross_authority_operation(operation_id) ON DELETE RESTRICT,
    terminal_reason TEXT NULL,
    admitted_at TIMESTAMPTZ NOT NULL DEFAULT transaction_timestamp(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT transaction_timestamp(),
    PRIMARY KEY (consumer_contract, message_identity_scope, message_id),
    CHECK ((effect_result_id IS NULL) = (effect_result_kind IS NULL)),
    CHECK (
        (state = 'processing' AND executor_id IS NOT NULL)
        OR (state <> 'processing' AND executor_id IS NULL)
    ),
    CHECK (
        state <> 'completed'
        OR effect_result_id IS NOT NULL
    ),
    CHECK (
        state NOT IN ('reconciliation_required', 'quarantined', 'failed_terminal')
        OR terminal_reason IS NOT NULL
    )
);

COMMENT ON TABLE system.async_consumer_inbox IS
'Durable create-or-observe receipt keyed by (consumer_contract, message_identity_scope, message_id). Identity alone is insufficient for benign duplicate classification; retained comparison evidence is mandatory.';

-- No GRANT statements are intentionally present. Concrete serving/worker/admin
-- privileges remain a separately reviewed runtime/operational mapping and SHALL
-- preserve logical ownership and least privilege.

COMMIT;
