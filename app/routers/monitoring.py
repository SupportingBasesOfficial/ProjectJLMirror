"""Monitoring domain router — sources, health projection, metrics, problem state.

Exposes operations from ``jlmirror_monitoring``. See ADR for monitoring domain
and the SQL in ``sql/wave4/``.
"""

from __future__ import annotations

import json
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from psycopg.types.json import Jsonb
from pydantic import BaseModel

from jlmirror_monitoring.health_projection import (
    EvidenceState,
    HealthClass,
    HealthInput,
    SeverityClass,
    derive_health,
    semantic_health_change,
)
from jlmirror_monitoring.source import (
    ConfiguredProviderScope,
    CreateMonitoringSourceCommand,
    ZabbixProviderConfiguration,
    plan_source_creation,
)

from app.context import build_tenant_context, resolve_dev_principal
from app.db import get_pool, set_tenant_context

router = APIRouter()


class ProviderScopeModel(BaseModel):
    host_group_refs: list[str]


class CreateSourceRequest(BaseModel):
    display_name: str
    provider_instance_ref: str
    base_url: str
    credential_binding_ref: str
    configured_provider_scope: ProviderScopeModel


class CreateSourceResponse(BaseModel):
    monitoring_source_id: str
    generation_id: str
    sync_operation_id: str
    audit_evidence_id: str
    canonical_request_fingerprint: str


@router.post("/monitoring/sources", response_model=CreateSourceResponse)
def create_monitoring_source(
    body: CreateSourceRequest,
    context: Annotated[Any, Depends(build_tenant_context)],
    principal: Annotated[Any, Depends(resolve_dev_principal)],
) -> CreateSourceResponse:
    """Create a monitoring source (Zabbix provider) for the tenant."""
    if context is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tenant context required")

    command = CreateMonitoringSourceCommand(
        tenant_id=context.tenant_id,
        display_name=body.display_name,
        provider_instance_ref=body.provider_instance_ref,
        provider_configuration=ZabbixProviderConfiguration(base_url=body.base_url),
        credential_binding_ref=body.credential_binding_ref,
        configured_provider_scope=ConfiguredProviderScope(
            host_group_refs=tuple(body.configured_provider_scope.host_group_refs)
        ),
    )
    plan = plan_source_creation(command)

    pool = get_pool()
    with pool.connection() as conn:
        set_tenant_context(conn, context.tenant_id)
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT monitoring_source_id, monitoring_sync_operation_id, idempotency_state, replayed
                FROM monitoring.create_zabbix_source(
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
                """,
                (
                    context.tenant_id,
                    plan.canonical_request_fingerprint,
                    plan.canonical_request_fingerprint,
                    plan.source.monitoring_source_id,
                    plan.generation.source_instance_generation,
                    plan.source.provider_scope_tenant_binding_id,
                    plan.sync_operation.monitoring_sync_operation_id,
                    plan.audit_evidence_id,
                    principal.principal_id,
                    principal.kind.value,
                    principal.credential_generation,
                    "dev-authz-r1",
                    "dev-correlation",
                    plan.source.display_name,
                    plan.generation.provider_instance_ref,
                    plan.generation.provider_configuration.base_url,
                    plan.source.credential_binding_ref,
                    Jsonb({"host_group_refs": list(plan.source.configured_provider_scope.host_group_refs)}),
                ),
            )
            row = cur.fetchone()
        conn.commit()

    db_source_id = row["monitoring_source_id"] if row else plan.source.monitoring_source_id
    db_operation_id = row["monitoring_sync_operation_id"] if row else plan.sync_operation.monitoring_sync_operation_id

    return CreateSourceResponse(
        monitoring_source_id=db_source_id,
        generation_id=plan.generation.source_instance_generation,
        sync_operation_id=db_operation_id,
        audit_evidence_id=plan.audit_evidence_id,
        canonical_request_fingerprint=plan.canonical_request_fingerprint,
    )


class HealthInputModel(BaseModel):
    monitoring_source_id: str
    monitoring_resource_id: str
    source_is_current: bool
    resource_present: bool
    scope_is_current_and_in_scope: bool
    problem_completeness_is_current: bool
    evidence_state: str = "current"
    active_problem_severities: list[str] = []
    reason_refs: list[str] = []


class HealthResponse(BaseModel):
    health_class: str
    evidence_state: str
    reason_refs: list[str]


@router.post("/monitoring/health/derive", response_model=HealthResponse)
async def derive_health_endpoint(
    body: HealthInputModel,
    context: Annotated[Any, Depends(build_tenant_context)],
) -> HealthResponse:
    """Derive a health decision from monitoring evidence inputs."""
    if context is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tenant context required")

    try:
        evidence_state = EvidenceState(body.evidence_state)
        severities = [SeverityClass(s) for s in body.active_problem_severities]
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid enum value: {exc}",
        ) from exc

    health_input = HealthInput(
        tenant_id=context.tenant_id,
        monitoring_source_id=body.monitoring_source_id,
        source_instance_generation="gen-current",
        monitoring_resource_id=body.monitoring_resource_id,
        source_is_current=body.source_is_current,
        resource_present=body.resource_present,
        scope_is_current_and_in_scope=body.scope_is_current_and_in_scope,
        problem_completeness_is_current=body.problem_completeness_is_current,
        evidence_state=evidence_state,
        active_problem_severities=severities,
        reason_refs=tuple(body.reason_refs),
    )

    decision = derive_health(health_input)
    return HealthResponse(
        health_class=decision.health_class.value,
        evidence_state=decision.evidence_state.value,
        reason_refs=list(decision.reason_refs),
    )


class SemanticChangeRequest(BaseModel):
    previous_health_class: str | None = None
    previous_evidence_state: str | None = None
    current_health_class: str
    current_evidence_state: str


class SemanticChangeResponse(BaseModel):
    changed: bool


@router.post("/monitoring/health/semantic-change", response_model=SemanticChangeResponse)
async def check_semantic_change(
    body: SemanticChangeRequest,
) -> SemanticChangeResponse:
    """Check whether a health transition is semantically meaningful."""
    from jlmirror_monitoring.health_projection import HealthDecision

    previous = None
    if body.previous_health_class is not None and body.previous_evidence_state is not None:
        previous = HealthDecision(
            HealthClass(body.previous_health_class),
            EvidenceState(body.previous_evidence_state),
            (),
        )
    current = HealthDecision(
        HealthClass(body.current_health_class),
        EvidenceState(body.current_evidence_state),
        (),
    )
    return SemanticChangeResponse(changed=semantic_health_change(previous, current))
