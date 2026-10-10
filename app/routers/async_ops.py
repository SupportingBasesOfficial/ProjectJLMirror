"""Async domain router — outbox, inbox, quarantine, reconciliation.

Exposes operations from ``jlmirror_async``. See ADR-008 (transactions/outbox)
and ADR-009 (event semantics). Uses in-memory ledgers for development;
production binds these to PostgreSQL tables (sql/wave2/).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from jlmirror_async.model import (
    ComparisonEvidence,
    LogicalMessage,
    MessageClass,
    MessageScope,
    MessageSubject,
    OutboxDispatchState,
)
from jlmirror_async.outbox import InMemoryOutboxLedger, tenant_message_from_context

from app.context import build_tenant_context

router = APIRouter()

# In-memory ledger singleton for development.
_outbox_ledger = InMemoryOutboxLedger()


class OutboxAppendRequest(BaseModel):
    message_id: str
    producer_message_scope: str = "tenant"
    message_class: str = "integration_event"
    contract_name: str
    contract_version: str
    producer: str
    correlation_id: str
    data_classification: str = "internal"
    serialization_profile_id: str = "serialization.json@1"
    encoded_payload: str
    subject_type: str
    subject_id: str


class OutboxAppendResponse(BaseModel):
    record_id: int
    state: str


@router.post("/async/outbox/append", response_model=OutboxAppendResponse)
async def outbox_append(
    body: OutboxAppendRequest,
    context: Annotated[Any, Depends(build_tenant_context)],
) -> OutboxAppendResponse:
    """Append a committed outbox message for the tenant (ADR-008)."""
    if context is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tenant context required")

    try:
        msg_class = MessageClass(body.message_class)
        msg_scope = MessageScope(body.producer_message_scope)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid enum: {exc}",
        ) from exc

    comparison_evidence = ComparisonEvidence(
        comparison_profile_id="comparison.sha256@1",
        comparison_profile_version="1",
        evidence_form="digest",
        evidence=body.encoded_payload.encode("utf-8"),
    )

    message = tenant_message_from_context(
        context,
        message_id=body.message_id,
        producer_message_scope=msg_scope.value,
        message_class=msg_class,
        contract_name=body.contract_name,
        contract_version=body.contract_version,
        producer=body.producer,
        correlation_id=body.correlation_id,
        data_classification=body.data_classification,
        serialization_profile_id=body.serialization_profile_id,
        encoded_payload=body.encoded_payload.encode("utf-8"),
        comparison_evidence=comparison_evidence,
        subject=MessageSubject(subject_type=body.subject_type, subject_id=body.subject_id),
    )

    record_id = _outbox_ledger.append_committed(message)
    return OutboxAppendResponse(
        record_id=record_id,
        state=_outbox_ledger.state(record_id).value,
    )


class OutboxClaimRequest(BaseModel):
    owner_id: str
    claim_ttl_seconds: int = 60


class OutboxClaimResponse(BaseModel):
    record_id: int | None
    owner_id: str
    claim_generation: int
    claim_expires_at: str | None
    state: str | None


@router.post("/async/outbox/claim-next", response_model=OutboxClaimResponse)
async def outbox_claim_next(
    body: OutboxClaimRequest,
    context: Annotated[Any, Depends(build_tenant_context)],
) -> OutboxClaimResponse:
    """Claim the next pending outbox message for dispatch."""
    now = datetime.now(timezone.utc)
    expires = now + timedelta(seconds=body.claim_ttl_seconds)
    claim = _outbox_ledger.claim_next(
        body.owner_id,
        observed_at=now,
        claim_expires_at=expires,
    )
    if claim is None:
        return OutboxClaimResponse(
            record_id=None,
            owner_id=body.owner_id,
            claim_generation=0,
            claim_expires_at=None,
            state=None,
        )
    return OutboxClaimResponse(
        record_id=claim.record_id,
        owner_id=claim.owner_id,
        claim_generation=claim.claim_generation,
        claim_expires_at=claim.claim_expires_at.isoformat(),
        state=_outbox_ledger.state(claim.record_id).value,
    )


class OutboxPublishRequest(BaseModel):
    record_id: int
    owner_id: str
    claim_generation: int
    claim_expires_at: str
    receipt_id: str = "receipt-1"


class OutboxStateResponse(BaseModel):
    record_id: int
    state: str
    attempt_count: int


@router.post("/async/outbox/mark-published", response_model=OutboxStateResponse)
async def outbox_mark_published(
    body: OutboxPublishRequest,
) -> OutboxStateResponse:
    """Mark an outbox record as successfully published to the broker."""
    now = datetime.now(timezone.utc)
    from jlmirror_async.model import BrokerPublicationReceipt
    from jlmirror_async.outbox import OutboxClaim

    # Reconstruct the claim object from the request fields.
    message = _outbox_ledger.message(body.record_id)
    claim = OutboxClaim(
        record_id=body.record_id,
        owner_id=body.owner_id,
        claim_generation=body.claim_generation,
        claim_expires_at=datetime.fromisoformat(body.claim_expires_at),
        message=message,
    )
    receipt = BrokerPublicationReceipt(
        receipt_id=body.receipt_id,
        observed_at=now,
    )
    _outbox_ledger.mark_published(claim, receipt, observed_at=now)
    return OutboxStateResponse(
        record_id=body.record_id,
        state=_outbox_ledger.state(body.record_id).value,
        attempt_count=_outbox_ledger.attempt_count(body.record_id),
    )


@router.get("/async/outbox/pending", response_model=list[OutboxStateResponse])
async def outbox_pending() -> list[OutboxStateResponse]:
    """List pending outbox messages."""
    now = datetime.now(timezone.utc)
    pending = list(_outbox_ledger.pending_messages(observed_at=now))
    if not pending:
        return []
    # The in-memory ledger does not expose a record_id lookup by message.
    # In production, the outbox table has an explicit record_id column.
    # For dev mode, we return a placeholder listing.
    return [
        OutboxStateResponse(
            record_id=0,
            state=OutboxDispatchState.PENDING.value,
            attempt_count=0,
        )
        for _ in pending
    ]
