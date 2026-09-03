from __future__ import annotations

from policy_boundary import (
    DataClassification,
    ErasureGovernanceApproval,
    ErasureGovernanceAuthority,
    GovernedOpaqueStore,
    LogicalDelivery,
    LogicalProjectionConsumer,
    OpaqueReference,
    PerTenantRawAssignment,
    PhysicalRoute,
    PolicyViolation,
    PublicationPolicy,
    PublicationProjection,
    RawRegulatedException,
    RouteCoupledProbeConsumer,
    TenantAuthorization,
    TenantRawAssignmentAuthority,
    TopologyAdapter,
    assert_replacement_mapping_semantics,
)


def must_reject(name: str, fn) -> None:
    try:
        fn()
    except PolicyViolation:
        return
    raise AssertionError(f"negative control unexpectedly passed: {name}")


def must_assert_fail(name: str, fn) -> None:
    try:
        fn()
    except AssertionError:
        return
    raise AssertionError(f"semantic negative control unexpectedly passed: {name}")


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
        "string classification bypass",
        lambda: PublicationPolicy.validate(
            PublicationProjection(
                classification="sensitive_or_regulated",  # type: ignore[arg-type]
                raw_value=b"regulated-raw-value",
            ),
            trusted_tenant_id=tenant,
        ),
    )
    must_reject(
        "non-bytes raw value",
        lambda: PublicationPolicy.validate(
            PublicationProjection(
                classification=DataClassification.SENSITIVE_OR_REGULATED,
                raw_value="regulated-raw-value",  # type: ignore[arg-type]
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

    assignment_authority = TenantRawAssignmentAuthority()
    governance_authority = ErasureGovernanceAuthority()
    assignment = assignment_authority.issue(
        tenant_id=tenant,
        assignment_kind="partition",
        assignment_id="tenant-a-partition-7",
    )
    approval = governance_authority.approve(tenant_id=tenant, approval_id="approval-17")
    good_exception = RawRegulatedException(
        per_tenant_assignment=assignment,
        segment_retention_ceiling_seconds=600,
        governed_erasure_sla_seconds=900,
        erasure_governance_approval=approval,
    )

    def validate_raw(exception: RawRegulatedException, **authority_overrides) -> None:
        PublicationPolicy.validate(
            PublicationProjection(
                classification=DataClassification.SENSITIVE_OR_REGULATED,
                raw_value=b"bounded-exception-value",
                raw_regulated_exception=exception,
            ),
            trusted_tenant_id=tenant,
            assignment_authority=authority_overrides.get("assignment_authority", assignment_authority),
            erasure_governance_authority=authority_overrides.get(
                "erasure_governance_authority", governance_authority
            ),
        )

    validate_raw(good_exception)
    must_reject(
        "exception without supplied authorities",
        lambda: PublicationPolicy.validate(
            PublicationProjection(
                classification=DataClassification.SENSITIVE_OR_REGULATED,
                raw_value=b"bounded-exception-value",
                raw_regulated_exception=good_exception,
            ),
            trusted_tenant_id=tenant,
        ),
    )
    must_reject(
        "mixed raw and opaque regulated representation",
        lambda: PublicationPolicy.validate(
            PublicationProjection(
                classification=DataClassification.SENSITIVE_OR_REGULATED,
                raw_value=b"bounded-exception-value",
                opaque_reference=ref,
                raw_regulated_exception=good_exception,
            ),
            trusted_tenant_id=tenant,
            assignment_authority=assignment_authority,
            erasure_governance_authority=governance_authority,
        ),
    )
    must_reject(
        "dangling regulated exception metadata",
        lambda: PublicationPolicy.validate(
            PublicationProjection(
                classification=DataClassification.SENSITIVE_OR_REGULATED,
                opaque_reference=ref,
                raw_regulated_exception=good_exception,
            ),
            trusted_tenant_id=tenant,
            assignment_authority=assignment_authority,
            erasure_governance_authority=governance_authority,
        ),
    )

    foreign_assignment_authority = TenantRawAssignmentAuthority()
    foreign_governance_authority = ErasureGovernanceAuthority()
    forged_assignment = PerTenantRawAssignment(tenant, "partition", "tenant-a-partition-7", object())
    forged_approval = ErasureGovernanceApproval(tenant, "approval-17", object())
    foreign_assignment = foreign_assignment_authority.issue(
        tenant_id=tenant, assignment_kind="partition", assignment_id="tenant-a-partition-7"
    )
    foreign_approval = foreign_governance_authority.approve(tenant_id=tenant, approval_id="approval-17")
    cross_tenant_assignment = assignment_authority.issue(
        tenant_id="tenant-b", assignment_kind="partition", assignment_id="tenant-b-partition-3"
    )
    cross_tenant_approval = governance_authority.approve(tenant_id="tenant-b", approval_id="approval-17")

    bad_exceptions = (
        ("missing per-tenant assignment", RawRegulatedException(None, 600, 900, approval)),
        ("forged assignment", RawRegulatedException(forged_assignment, 600, 900, approval)),
        ("foreign-authority assignment", RawRegulatedException(foreign_assignment, 600, 900, approval)),
        ("cross-tenant assignment", RawRegulatedException(cross_tenant_assignment, 600, 900, approval)),
        ("missing retention ceiling", RawRegulatedException(assignment, None, 900, approval)),
        ("boolean retention ceiling", RawRegulatedException(assignment, True, 900, approval)),
        ("boolean erasure sla", RawRegulatedException(assignment, 600, True, approval)),
        ("retention exceeds erasure sla", RawRegulatedException(assignment, 901, 900, approval)),
        ("missing erasure governance approval", RawRegulatedException(assignment, 600, 900, None)),
        ("forged governance approval", RawRegulatedException(assignment, 600, 900, forged_approval)),
        ("foreign-authority approval", RawRegulatedException(assignment, 600, 900, foreign_approval)),
        ("cross-tenant governance approval", RawRegulatedException(assignment, 600, 900, cross_tenant_approval)),
    )
    for name, exception in bad_exceptions:
        must_reject(name, lambda exception=exception: validate_raw(exception))

    must_reject(
        "wrong assignment authority supplied",
        lambda: validate_raw(good_exception, assignment_authority=foreign_assignment_authority),
    )
    must_reject(
        "wrong governance authority supplied",
        lambda: validate_raw(good_exception, erasure_governance_authority=foreign_governance_authority),
    )
    must_reject(
        "invalid assignment kind issuance",
        lambda: assignment_authority.issue(
            tenant_id=tenant, assignment_kind="shared-cluster", assignment_id="shared-1"
        ),
    )

    delivery = LogicalDelivery(
        tenant_id=tenant,
        contract_name="monitoring.observation.recorded",
        contract_version=1,
        message_identity_scope="monitoring-observation",
        message_id="msg-0007",
    )
    auth = TenantAuthorization(tenant_id=tenant, allowed_contracts=frozenset({delivery.contract_name}))
    route_v1 = PhysicalRoute(
        topic="cell-a.monitoring.observation.v1",
        consumer_group="cell-a.monitoring-projection",
        cell="cell-a",
    )
    route_v2 = PhysicalRoute(topic="cohort-17.events", consumer_group="projection-v2", cell="cell-c")
    first = TopologyAdapter({(tenant, delivery.contract_name): route_v1})
    replacement = TopologyAdapter({(tenant, delivery.contract_name): route_v2})

    consumer = LogicalProjectionConsumer()
    before_route, after_route, before_result, after_result = assert_replacement_mapping_semantics(
        delivery, auth, first, replacement, consumer
    )
    assert before_route.topic != after_route.topic
    assert before_route.consumer_group != after_route.consumer_group
    assert before_route.cell != after_route.cell
    assert before_result == after_result
    assert before_result.effect_key == (
        "tenant-a|monitoring.observation.recorded|monitoring-observation|msg-0007"
    )
    assert delivery.semantic_identity() == (
        tenant,
        "monitoring.observation.recorded",
        1,
        "monitoring-observation",
        "msg-0007",
    )
    assert all(
        physical not in repr(before_result)
        for physical in (
            before_route.topic,
            before_route.consumer_group,
            before_route.cell,
            after_route.topic,
            after_route.consumer_group,
            after_route.cell,
        )
    )
    must_assert_fail(
        "route-coupled consumer semantics",
        lambda: assert_replacement_mapping_semantics(
            delivery,
            auth,
            first,
            replacement,
            RouteCoupledProbeConsumer(),
        ),
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
    must_reject(
        "boolean logical contract version",
        lambda: LogicalDelivery(
            tenant_id=tenant,
            contract_name=delivery.contract_name,
            contract_version=True,  # type: ignore[arg-type]
            message_identity_scope=delivery.message_identity_scope,
            message_id="msg-bad",
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
        "runtime_type_confusion=blocked regulated_representation=unambiguous "
        "exception_assignment=authority_issued_tenant_bound exception_governance=authority_issued_tenant_bound "
        "forged_exception_authority=blocked retention_ceiling=bounded tenant_auth=before_mapping "
        "consumer_operation=executed_both_mappings route_coupled_consumer=detected "
        "physical_identity=nonsemantic replacement_mapping=semantic_stable"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
