from __future__ import annotations

from policy_boundary import (
    DataClassification,
    GovernedOpaqueStore,
    LogicalDelivery,
    OpaqueReference,
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

    # Default regulated profile is reference-only and supports record-level erasure by reference.
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

    # Raw-regulated exception is conjunctive: every binding control is required.
    good_exception = RawRegulatedException(
        per_tenant_assignment=True,
        segment_retention_ceiling_seconds=600,
        governed_erasure_sla_seconds=900,
        erasure_governance_signoff=True,
    )
    PublicationPolicy.validate(
        PublicationProjection(
            classification=DataClassification.SENSITIVE_OR_REGULATED,
            raw_value=b"bounded-exception-value",
            raw_regulated_exception=good_exception,
        ),
        trusted_tenant_id=tenant,
    )
    for name, exception in (
        ("missing per-tenant assignment", RawRegulatedException(False, 600, 900, True)),
        ("missing retention ceiling", RawRegulatedException(True, None, 900, True)),
        ("retention exceeds erasure sla", RawRegulatedException(True, 901, 900, True)),
        ("missing erasure governance signoff", RawRegulatedException(True, 600, 900, False)),
    ):
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

    # Physical values in an unrelated payload dictionary cannot override trusted mapping.
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
        "exception_controls=conjunctive tenant_auth=before_mapping physical_identity=nonsemantic "
        "replacement_mapping=semantic_stable"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
