from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Mapping


class PolicyViolation(ValueError):
    pass


def _valid_token(value: object) -> bool:
    return isinstance(value, str) and bool(value) and value.strip() == value


def _positive_plain_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


class DataClassification(str, Enum):
    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL_TENANT = "confidential_tenant"
    SENSITIVE_OR_REGULATED = "sensitive_or_regulated"
    SECRET_OR_CREDENTIAL = "secret_or_credential"


@dataclass(frozen=True)
class OpaqueReference:
    tenant_id: str
    record_id: str
    reference_id: str

    def __post_init__(self) -> None:
        for name, value in (
            ("tenant_id", self.tenant_id),
            ("record_id", self.record_id),
            ("reference_id", self.reference_id),
        ):
            if not _valid_token(value):
                raise PolicyViolation(f"invalid opaque reference {name}")


class GovernedOpaqueStore:
    """Minimal evidence store proving erasure can target one governed record."""

    def __init__(self) -> None:
        self._records: dict[tuple[str, str, str], bytes] = {}

    @staticmethod
    def _key(reference: OpaqueReference) -> tuple[str, str, str]:
        return (reference.tenant_id, reference.record_id, reference.reference_id)

    @staticmethod
    def _authorize_reference(reference: object, trusted_tenant_id: object) -> OpaqueReference:
        if not isinstance(reference, OpaqueReference):
            raise PolicyViolation("opaque store requires governed opaque reference")
        if not _valid_token(trusted_tenant_id) or reference.tenant_id != trusted_tenant_id:
            raise PolicyViolation("opaque store tenant mismatch")
        return reference

    def put(self, reference: OpaqueReference, value: bytes, *, trusted_tenant_id: str) -> None:
        reference = self._authorize_reference(reference, trusted_tenant_id)
        if not isinstance(value, bytes) or not value:
            raise PolicyViolation("opaque store requires non-empty bytes")
        self._records[self._key(reference)] = value

    def exists(self, reference: OpaqueReference, *, trusted_tenant_id: str) -> bool:
        reference = self._authorize_reference(reference, trusted_tenant_id)
        return self._key(reference) in self._records

    def erase_record(self, reference: OpaqueReference, *, trusted_tenant_id: str) -> None:
        reference = self._authorize_reference(reference, trusted_tenant_id)
        self._records.pop(self._key(reference), None)


@dataclass(frozen=True)
class PerTenantRawAssignment:
    tenant_id: str
    assignment_kind: str
    assignment_id: str
    _authority_seal: object


class TenantRawAssignmentAuthority:
    """Evidence authority that exclusively issues tenant-bound raw placement permits."""

    def __init__(self) -> None:
        self._seal = object()

    def issue(self, *, tenant_id: str, assignment_kind: str, assignment_id: str) -> PerTenantRawAssignment:
        if not _valid_token(tenant_id):
            raise PolicyViolation("assignment tenant invalid")
        if assignment_kind not in {"topic", "partition"}:
            raise PolicyViolation("assignment kind must be topic or partition")
        if not _valid_token(assignment_id):
            raise PolicyViolation("assignment id invalid")
        return PerTenantRawAssignment(tenant_id, assignment_kind, assignment_id, self._seal)

    def verifies(self, assignment: object, *, trusted_tenant_id: str) -> bool:
        return (
            isinstance(assignment, PerTenantRawAssignment)
            and assignment._authority_seal is self._seal
            and _valid_token(trusted_tenant_id)
            and assignment.tenant_id == trusted_tenant_id
            and assignment.assignment_kind in {"topic", "partition"}
            and _valid_token(assignment.assignment_id)
        )


@dataclass(frozen=True)
class ErasureGovernanceApproval:
    tenant_id: str
    approval_id: str
    _authority_seal: object


class ErasureGovernanceAuthority:
    """Evidence authority that exclusively issues erasure-governance approvals."""

    authority_id = "erasure-governance-authority"

    def __init__(self) -> None:
        self._seal = object()

    def approve(self, *, tenant_id: str, approval_id: str) -> ErasureGovernanceApproval:
        if not _valid_token(tenant_id):
            raise PolicyViolation("approval tenant invalid")
        if not _valid_token(approval_id):
            raise PolicyViolation("approval id invalid")
        return ErasureGovernanceApproval(tenant_id, approval_id, self._seal)

    def verifies(self, approval: object, *, trusted_tenant_id: str) -> bool:
        return (
            isinstance(approval, ErasureGovernanceApproval)
            and approval._authority_seal is self._seal
            and _valid_token(trusted_tenant_id)
            and approval.tenant_id == trusted_tenant_id
            and _valid_token(approval.approval_id)
        )


@dataclass(frozen=True)
class RawRegulatedException:
    per_tenant_assignment: PerTenantRawAssignment | None
    segment_retention_ceiling_seconds: int | None
    governed_erasure_sla_seconds: int | None
    erasure_governance_approval: ErasureGovernanceApproval | None

    def is_fully_authorized(
        self,
        *,
        trusted_tenant_id: str,
        assignment_authority: TenantRawAssignmentAuthority | None,
        erasure_governance_authority: ErasureGovernanceAuthority | None,
    ) -> bool:
        if not isinstance(assignment_authority, TenantRawAssignmentAuthority):
            return False
        if not assignment_authority.verifies(self.per_tenant_assignment, trusted_tenant_id=trusted_tenant_id):
            return False
        if not isinstance(erasure_governance_authority, ErasureGovernanceAuthority):
            return False
        if not erasure_governance_authority.verifies(
            self.erasure_governance_approval, trusted_tenant_id=trusted_tenant_id
        ):
            return False
        if not _positive_plain_int(self.segment_retention_ceiling_seconds):
            return False
        if not _positive_plain_int(self.governed_erasure_sla_seconds):
            return False
        return self.segment_retention_ceiling_seconds <= self.governed_erasure_sla_seconds


@dataclass(frozen=True)
class PublicationProjection:
    classification: DataClassification
    raw_value: bytes | None = None
    opaque_reference: OpaqueReference | None = None
    raw_regulated_exception: RawRegulatedException | None = None


class PublicationPolicy:
    """Evidence boundary for ordinary async record-value eligibility."""

    @staticmethod
    def validate(
        projection: PublicationProjection,
        *,
        trusted_tenant_id: str,
        assignment_authority: TenantRawAssignmentAuthority | None = None,
        erasure_governance_authority: ErasureGovernanceAuthority | None = None,
    ) -> None:
        if not isinstance(projection, PublicationProjection):
            raise PolicyViolation("publication projection type required")
        if not _valid_token(trusted_tenant_id):
            raise PolicyViolation("trusted tenant id required")
        if not isinstance(projection.classification, DataClassification):
            raise PolicyViolation("data classification must be canonical enum value")
        if projection.raw_value is not None and not isinstance(projection.raw_value, bytes):
            raise PolicyViolation("raw async value must be bytes")
        if projection.opaque_reference is not None and not isinstance(projection.opaque_reference, OpaqueReference):
            raise PolicyViolation("opaque reference type required")
        if projection.raw_regulated_exception is not None and not isinstance(
            projection.raw_regulated_exception, RawRegulatedException
        ):
            raise PolicyViolation("raw regulated exception type required")

        if projection.classification is DataClassification.SECRET_OR_CREDENTIAL:
            raise PolicyViolation("secret_or_credential is prohibited in ordinary async payloads")

        ref = projection.opaque_reference
        if ref is not None and ref.tenant_id != trusted_tenant_id:
            raise PolicyViolation("opaque reference tenant must match trusted tenant context")

        if projection.classification is DataClassification.SENSITIVE_OR_REGULATED:
            if projection.raw_value is not None:
                if ref is not None:
                    raise PolicyViolation("regulated projection cannot mix raw value and opaque reference")
                exception = projection.raw_regulated_exception
                if exception is None or not exception.is_fully_authorized(
                    trusted_tenant_id=trusted_tenant_id,
                    assignment_authority=assignment_authority,
                    erasure_governance_authority=erasure_governance_authority,
                ):
                    raise PolicyViolation("raw sensitive_or_regulated value rejected by default")
            else:
                if projection.raw_regulated_exception is not None:
                    raise PolicyViolation("regulated exception metadata requires raw regulated value")
                if ref is None:
                    raise PolicyViolation("sensitive_or_regulated projection requires governed opaque reference")
            return

        if projection.raw_regulated_exception is not None:
            raise PolicyViolation("regulated exception metadata is invalid for non-regulated classification")


@dataclass(frozen=True)
class LogicalDelivery:
    tenant_id: str
    contract_name: str
    contract_version: int
    message_identity_scope: str
    message_id: str

    def __post_init__(self) -> None:
        for name, value in (
            ("tenant_id", self.tenant_id),
            ("contract_name", self.contract_name),
            ("message_identity_scope", self.message_identity_scope),
            ("message_id", self.message_id),
        ):
            if not _valid_token(value):
                raise PolicyViolation(f"invalid logical delivery {name}")
        if not _positive_plain_int(self.contract_version):
            raise PolicyViolation("contract_version must be positive integer")

    def semantic_identity(self) -> tuple[str, str, int, str, str]:
        return (
            self.tenant_id,
            self.contract_name,
            self.contract_version,
            self.message_identity_scope,
            self.message_id,
        )


@dataclass(frozen=True)
class PhysicalRoute:
    topic: str
    consumer_group: str
    cell: str

    def __post_init__(self) -> None:
        for name, value in (("topic", self.topic), ("consumer_group", self.consumer_group), ("cell", self.cell)):
            if not _valid_token(value):
                raise PolicyViolation(f"invalid physical route {name}")


@dataclass(frozen=True)
class TenantAuthorization:
    tenant_id: str
    allowed_contracts: frozenset[str]

    def __post_init__(self) -> None:
        if not _valid_token(self.tenant_id):
            raise PolicyViolation("authorization tenant invalid")
        if not isinstance(self.allowed_contracts, frozenset) or any(
            not _valid_token(contract) for contract in self.allowed_contracts
        ):
            raise PolicyViolation("authorization contracts invalid")

    def authorizes(self, delivery: LogicalDelivery) -> bool:
        return self.tenant_id == delivery.tenant_id and delivery.contract_name in self.allowed_contracts


class TopologyAdapter:
    """Maps trusted logical delivery identity into replaceable physical placement."""

    def __init__(self, routes: Mapping[tuple[str, str], PhysicalRoute]) -> None:
        if not isinstance(routes, Mapping):
            raise PolicyViolation("topology routes mapping required")
        normalized: dict[tuple[str, str], PhysicalRoute] = {}
        for key, route in routes.items():
            if (
                not isinstance(key, tuple)
                or len(key) != 2
                or not _valid_token(key[0])
                or not _valid_token(key[1])
                or not isinstance(route, PhysicalRoute)
            ):
                raise PolicyViolation("invalid topology route entry")
            normalized[(key[0], key[1])] = route
        self._routes = normalized

    def map_authorized(self, delivery: LogicalDelivery, authorization: TenantAuthorization) -> PhysicalRoute:
        if not isinstance(delivery, LogicalDelivery) or not isinstance(authorization, TenantAuthorization):
            raise PolicyViolation("typed logical delivery and authorization required")
        if not authorization.authorizes(delivery):
            raise PolicyViolation("tenant/contract authorization denied before transport mapping")
        key = (delivery.tenant_id, delivery.contract_name)
        try:
            return self._routes[key]
        except KeyError as exc:
            raise PolicyViolation("no physical mapping for authorized logical delivery") from exc


@dataclass(frozen=True)
class ConsumerLogicalResult:
    tenant_id: str
    contract_name: str
    contract_version: int
    message_identity_scope: str
    message_id: str
    effect_key: str


class LogicalProjectionConsumer:
    """Reference consumer whose business result is intentionally route-neutral."""

    def execute(
        self,
        delivery: LogicalDelivery,
        authorization: TenantAuthorization,
        topology: TopologyAdapter,
    ) -> ConsumerLogicalResult:
        topology.map_authorized(delivery, authorization)
        return ConsumerLogicalResult(
            tenant_id=delivery.tenant_id,
            contract_name=delivery.contract_name,
            contract_version=delivery.contract_version,
            message_identity_scope=delivery.message_identity_scope,
            message_id=delivery.message_id,
            effect_key=f"{delivery.tenant_id}|{delivery.contract_name}|{delivery.message_identity_scope}|{delivery.message_id}",
        )


class RouteCoupledProbeConsumer(LogicalProjectionConsumer):
    """Negative control: deliberately leaks physical topic into consumer semantics."""

    def execute(self, delivery, authorization, topology):
        route = topology.map_authorized(delivery, authorization)
        logical = super().execute(delivery, authorization, topology)
        return (logical, route.topic)


def assert_replacement_mapping_semantics(
    delivery: LogicalDelivery,
    authorization: TenantAuthorization,
    first: TopologyAdapter,
    replacement: TopologyAdapter,
    consumer: LogicalProjectionConsumer,
) -> tuple[PhysicalRoute, PhysicalRoute, ConsumerLogicalResult, ConsumerLogicalResult]:
    if not isinstance(consumer, LogicalProjectionConsumer):
        raise PolicyViolation("consumer-facing operation required")
    first_route = first.map_authorized(delivery, authorization)
    replacement_route = replacement.map_authorized(delivery, authorization)
    if first_route == replacement_route:
        raise AssertionError("replacement mapping evidence requires physically distinct routes")
    before = consumer.execute(delivery, authorization, first)
    after = consumer.execute(delivery, authorization, replacement)
    if before != after:
        raise AssertionError("consumer semantics changed across physical mapping replacement")
    if not isinstance(before, ConsumerLogicalResult) or not isinstance(after, ConsumerLogicalResult):
        raise AssertionError("consumer-facing operation must return route-neutral logical result")
    return first_route, replacement_route, before, after
