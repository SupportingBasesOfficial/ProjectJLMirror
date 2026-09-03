from __future__ import annotations

from policy_boundary import (
    DataClassification,
    ErasureGovernanceApproval,
    GovernedOpaqueStore,
    LogicalDelivery,
    OpaqueReference,
    PerTenantRawAssignment,
    PhysicalRoute,
    PolicyViolation,
    PublicationPolicy,
    PublicationProjection,
    RawRegulatedException,
    TenantAuthorization,
    TopologyAdapter,
    assert_replacement_mapping_semantics,
)


def must_reject(name: str, fn) -> None:
    try:
        fn()
    except PolicyViolation:
        return
    raise AssertionError(f"negative control unexpectedly passed: {name}")


def main() -> int:
    tenant = "tenant-a"
    ref = OpaqueReference(tenant_id=tenant, record_id="record-7", reference_id="opaque-ref-7")

    PublicationPolicy.validate(
        PublicationProjection(
            classification=DataClassification.SENSITIVE_OR_REGULATED,
            opaque_reference=ref,
        ),
        trusted_tenant_id=tenant,
    )
    neighbor = OpaqueReference(tenant_id=tenant, record_id="record-8", reference_id="opaque-ref-8")
    store = GovernedOpaqueStore()
    store.put(ref, b"regulated-record-7", trusted_tenant_id=tenant)
    store.put(neighbor, b"regulated-record-8", trusted_tenant_id=tenant)
    assert store.exists(ref, trusted_tenant_id=tenant)
    assert store.exists(neighbor, trusted_tenant_id=tenant)
    store.erase_record(ref, trusted_tenant_id=tenant)
    assert not store.exists(ref, trusted_tenant_id=tenant)
    assert store.exists(neighbor, trusted_tenant_id=tenant)
    must_reject(
        "cross-tenant opaque erasure",
        lambda: store.erase_record(neighbor, trusted_tenant_id="tenant-b"),
    )

    must_reject(
        "raw regulated leak by default",
        lambda: PublicationPolicy.validate(
            PublicationProjection(
                classification=DataClassification.SENSITIVE_OR_REGULATED,
                raw_value=b"regulated-raw-value",
            ),
            trusted_tenant_id=tenant,
        ),
    )
    must_reject(
        "regulated projection without opaque reference",
        lambda: PublicationPolicy.validate(
            PublicationProjection(classification=DataClassification.SENSITIVE_OR_REGULATED),
            trusted_tenant_id=tenant,
        ),
    )
    must_reject(
        "cross-tenant opaque reference",
        lambda: PublicationPolicy.validate(
            PublicationProjection(
                classification=DataClassification.SENSITIVE_OR_REGULATED,
                opaque_reference=OpaqueReference(
                    tenant_id="tenant-b", record_id="record-7", reference_id="opaque-ref-7"
                ),
            ),
            trusted_tenant_id=tenant,
        ),
    )
    must_reject(
        "secret payload",
        lambda: PublicationPolicy.validate(
            PublicationProjection(
                classification=DataClassification.SECRET_OR_CREDENTIAL,
                raw_value=b"token",
            ),
            trusted_tenant_id=tenant,
        ),
    )

    assignment = PerTenantRawAssignment(
        tenant_id=tenant,
        assignment_kind="partition",
        assignment_id="tenant-a-partition-7",
    )
    approval = ErasureGovernanceApproval(
        tenant_id=tenant,
        authority_id="erasure-governance-authority",
        approval_id="approval-17",
    )
    good_exception = RawRegulatedException(
        per_tenant_assignment=assignment,
        segment_retention_ceiling_seconds=600,
        governed_erasure_sla_seconds=900,
        erasure_governance_approval=approval,
    )
    PublicationPolicy.validate(
        PublicationProjection(
            classification=DataClassification.SENSITIVE_OR_REGULATED,
            raw_value=b"bounded-exception-value",
            raw_regulated_exception=good_exception,
        ),
        trusted_tenant_id=tenant,
    )

    bad_exceptions = (
        (
            "missing per-tenant assignment",
            RawRegulatedException(None, 600, 900, approval),
        ),
        (
            "cross-tenant assignment",
            RawRegulatedException(
                PerTenantRawAssignment("tenant-b", "partition", "tenant-b-partition-3"),
                600,
                900,
                approval,
            ),
        ),
        (
            "invalid assignment kind",
            RawRegulatedException(
                PerTenantRawAssignment(tenant, "shared-cluster", "shared-1"),
                600,
                900,
                approval,
            ),
        ),
        (
            "missing retention ceiling",
            RawRegulatedException(assignment, None, 900, approval),
        ),
        (
            "retention exceeds erasure sla",
            RawRegulatedException(assignment, 901, 900, approval),
        ),
        (
            "missing erasure governance approval",
            RawRegulatedException(assignment, 600, 900, None),
        ),
        (
            "wrong governance authority",
            RawRegulatedException(
                assignment,
                600,
                900,
                ErasureGovernanceApproval(tenant, "ordinary-service", "approval-17"),
            ),
        ),
        (
            "cross-tenant governance approval",
            RawRegulatedException(
                assignment,
                600,
                900,
                ErasureGovernanceApproval("tenant-b", "erasure-governance-authority", "approval-17"),
            ),
        ),
    )
    for name, exception in bad_exceptions:
        must_reject(
            name,
            lambda exception=exception: PublicationPolicy.validate(
                PublicationProjection(
                    classification=DataClassification.SENSITIVE_OR_REGULATED,
                    raw_value=b"regulated-raw-value",
                    raw_regulated_exception=exception,
                ),
                trusted_tenant_id=tenant,
            ),
        )

    delivery = LogicalDelivery(
        tenant_id=tenant,
        contract_name="monitoring.observation.recorded",
        contract_version=1,
        message_identity_scope="monitoring-observation",
        message_id="msg-0007",
    )
    auth = TenantAuthorization(
        tenant_id=tenant,
        allowed_contracts=frozenset({delivery.contract_name}),
    )
    route_v1 = PhysicalRoute(
        topic="cell-a.monitoring.observation.v1",
        consumer_group="cell-a.monitoring-projection",
        cell="cell-a",
    )
    route_v2 = PhysicalRoute(
        topic="cohort-17.events",
        consumer_group="projection-v2",
        cell="cell-c",
    )
    first = TopologyAdapter({(tenant, delivery.contract_name): route_v1})
    replacement = TopologyAdapter({(tenant, delivery.contract_name): route_v2})

    before, after = assert_replacement_mapping_semantics(delivery, auth, first, replacement)
    assert before.topic != after.topic
    assert before.consumer_group != after.consumer_group
    assert before.cell != after.cell
    assert delivery.semantic_identity() == (
        tenant,
        "monitoring.observation.recorded",
        1,
        "monitoring-observation",
        "msg-0007",
    )
    assert all(
        physical not in repr(delivery.semantic_identity())
        for physical in (before.topic, before.consumer_group, before.cell, after.topic, after.consumer_group, after.cell)
    )

    must_reject(
        "cross-tenant authorization before mapping",
        lambda: first.map_authorized(
            delivery,
            TenantAuthorization(
                tenant_id="tenant-b",
                allowed_contracts=frozenset({delivery.contract_name}),
            ),
        ),
    )
    must_reject(
        "contract authorization before mapping",
        lambda: first.map_authorized(
            delivery,
            TenantAuthorization(tenant_id=tenant, allowed_contracts=frozenset()),
        ),
    )

    hostile_payload = {
        "topic": "attacker.topic",
        "consumer_group": "attacker.group",
        "cell": "attacker-cell",
        "tenant_id": "tenant-b",
    }
    resolved = first.map_authorized(delivery, auth)
    assert resolved == route_v1
    assert all(
        hostile_payload[key] != getattr(resolved, attr)
        for key, attr in (("topic", "topic"), ("consumer_group", "consumer_group"), ("cell", "cell"))
    )

    print(
        "d4a_data_topology=PASS "
        "regulated_default=opaque_reference per_record_erasure=isolated raw_leak=blocked "
        "exception_assignment=tenant_bound exception_governance=authority_bound retention_ceiling=bounded "
        "tenant_auth=before_mapping physical_identity=nonsemantic replacement_mapping=semantic_stable"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
