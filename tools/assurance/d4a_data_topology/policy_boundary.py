from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Mapping


class PolicyViolation(ValueError):
    pass


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
            if not value or value.strip() != value:
                raise PolicyViolation(f"invalid opaque reference {name}")


@dataclass(frozen=True)
class RawRegulatedException:
    per_tenant_assignment: bool
    segment_retention_ceiling_seconds: int | None
    governed_erasure_sla_seconds: int | None
    erasure_governance_signoff: bool

    def is_fully_authorized(self) -> bool:
        if not self.per_tenant_assignment or not self.erasure_governance_signoff:
            return False
        if self.segment_retention_ceiling_seconds is None or self.governed_erasure_sla_seconds is None:
            return False
        if self.segment_retention_ceiling_seconds <= 0 or self.governed_erasure_sla_seconds <= 0:
            return False
        return self.segment_retention_ceiling_seconds <= self.governed_erasure_sla_seconds


@dataclass(frozen=True)
class PublicationProjection:
    classification: DataClassification
    raw_value: bytes | None = None
    opaque_reference: OpaqueReference | None = None
    raw_regulated_exception: RawRegulatedException | None = None


class PublicationPolicy:
    """Evidence boundary for ordinary async record-value eligibility.

    This is a source-evidence reference boundary, not production transport authority.
    """

    @staticmethod
    def validate(projection: PublicationProjection, *, trusted_tenant_id: str) -> None:
        if not trusted_tenant_id or trusted_tenant_id.strip() != trusted_tenant_id:
            raise PolicyViolation("trusted tenant id required")

        if projection.classification is DataClassification.SECRET_OR_CREDENTIAL:
            raise PolicyViolation("secret_or_credential is prohibited in ordinary async payloads")

        ref = projection.opaque_reference
        if ref is not None and ref.tenant_id != trusted_tenant_id:
            raise PolicyViolation("opaque reference tenant must match trusted tenant context")

        if projection.classification is DataClassification.SENSITIVE_OR_REGULATED:
            if projection.raw_value is not None:
                exception = projection.raw_regulated_exception
                if exception is None or not exception.is_fully_authorized():
                    raise PolicyViolation("raw sensitive_or_regulated value rejected by default")
            else:
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


@dataclass(frozen=True)
class TenantAuthorization:
    tenant_id: str
    allowed_contracts: frozenset[str]

    def authorizes(self, delivery: LogicalDelivery) -> bool:
        return self.tenant_id == delivery.tenant_id and delivery.contract_name in self.allowed_contracts


class TopologyAdapter:
    """Maps trusted logical delivery identity into replaceable physical placement."""

    def __init__(self, routes: Mapping[tuple[str, str], PhysicalRoute]) -> None:
        self._routes = dict(routes)

    def map_authorized(self, delivery: LogicalDelivery, authorization: TenantAuthorization) -> PhysicalRoute:
        # Authorization intentionally occurs before any physical route lookup.
        if not authorization.authorizes(delivery):
            raise PolicyViolation("tenant/contract authorization denied before transport mapping")
        key = (delivery.tenant_id, delivery.contract_name)
        try:
            return self._routes[key]
        except KeyError as exc:
            raise PolicyViolation("no physical mapping for authorized logical delivery") from exc


def assert_replacement_mapping_semantics(
    delivery: LogicalDelivery,
    authorization: TenantAuthorization,
    first: TopologyAdapter,
    replacement: TopologyAdapter,
) -> tuple[PhysicalRoute, PhysicalRoute]:
    before = delivery.semantic_identity()
    first_route = first.map_authorized(delivery, authorization)
    replacement_route = replacement.map_authorized(delivery, authorization)
    after = delivery.semantic_identity()
    if before != after:
        raise AssertionError("physical mapping changed logical delivery identity")
    if first_route == replacement_route:
        raise AssertionError("replacement mapping evidence requires physically distinct routes")
    return first_route, replacement_route
