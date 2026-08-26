"""Portable Wave 2 transactional/async correctness primitives.

The package is subordinate to accepted Data, Phase 10/11 and Wave 1 authority
contracts. It selects no broker, schema registry, KMS, cache or Product behavior.
"""

from .execution import (
    AsyncExecutionAdmission,
    AsyncExecutionRequest,
    CurrentAsyncExecutionAuthorityPort,
    require_current_execution,
)
from .inbox import (
    CrossAuthorityReconciliationPort,
    InboxAdmission,
    InboxExecutorClaim,
    InMemoryInboxLedger,
)
from .model import (
    AsyncCorrectnessError,
    BrokerPublicationReceipt,
    ComparisonEvidence,
    EffectResultLink,
    EquivalenceRelation,
    InboxState,
    IntegrityConflict,
    InvalidTransition,
    LogicalMessage,
    MessageClass,
    MessageScope,
    MessageSubject,
    OperationState,
    OutboxDispatchState,
    ReconciliationBlocked,
    ReconciliationResolution,
    ScopedMessageIdentity,
)
from .outbox import InMemoryOutboxLedger, OutboxClaim, tenant_message_from_context
from .reconciliation import InMemoryCrossAuthorityOperationLedger, OperationAttempt

__all__ = [
    "AsyncCorrectnessError",
    "AsyncExecutionAdmission",
    "AsyncExecutionRequest",
    "BrokerPublicationReceipt",
    "ComparisonEvidence",
    "CrossAuthorityReconciliationPort",
    "CurrentAsyncExecutionAuthorityPort",
    "EffectResultLink",
    "EquivalenceRelation",
    "InboxAdmission",
    "InboxExecutorClaim",
    "InboxState",
    "InMemoryCrossAuthorityOperationLedger",
    "InMemoryInboxLedger",
    "InMemoryOutboxLedger",
    "IntegrityConflict",
    "InvalidTransition",
    "LogicalMessage",
    "MessageClass",
    "MessageScope",
    "MessageSubject",
    "OperationAttempt",
    "OperationState",
    "OutboxClaim",
    "OutboxDispatchState",
    "ReconciliationBlocked",
    "ReconciliationResolution",
    "ScopedMessageIdentity",
    "require_current_execution",
    "tenant_message_from_context",
]
