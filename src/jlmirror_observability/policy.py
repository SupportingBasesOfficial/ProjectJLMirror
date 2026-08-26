from __future__ import annotations

from dataclasses import dataclass
import re

from .catalog import ReliabilityObservabilityJoin, join_for
from .model import CORE_ALERT_PROFILES, CORE_HEALTH_PROFILES, CORE_SLI_PROFILES, ObservationError


_EVIDENCE_REFERENCE_RE = re.compile(r"^evidence:[A-Za-z0-9][A-Za-z0-9_.:@/-]{0,190}$")


def _require_evidence_reference(name: str, value: str) -> None:
    if not isinstance(value, str) or not _EVIDENCE_REFERENCE_RE.fullmatch(value):
        raise ObservationError(f"{name} must be an immutable durable evidence record identity")


@dataclass(frozen=True)
class NoApplicableCaseEvidence:
    reason: str
    authority_profile: str
    evidence_reference: str
    scope_binding: str
    current: bool

    def validate_for(self, expected_scope: str) -> None:
        if not all((self.reason, self.authority_profile, self.scope_binding, expected_scope)):
            raise ObservationError("NO_APPLICABLE_CASE requires reason, authority, evidence and exact scope")
        _require_evidence_reference("no_applicable_case.evidence_reference", self.evidence_reference)
        if not self.current:
            raise ObservationError("NO_APPLICABLE_CASE evidence is not current")
        if self.scope_binding != expected_scope:
            raise ObservationError("NO_APPLICABLE_CASE evidence is bound to a different observability scope")


@dataclass(frozen=True)
class ProductApplicabilityEvidence:
    authority_profile: str
    evidence_reference: str
    scope_binding: str
    current: bool
    enabled: bool

    def validate_for(self, expected_scope: str) -> None:
        if not all((self.authority_profile, self.scope_binding, expected_scope)):
            raise ObservationError("Product applicability requires authority, evidence and exact scope")
        _require_evidence_reference("product_applicability.evidence_reference", self.evidence_reference)
        if not self.current:
            raise ObservationError("Product applicability evidence is not current")
        if self.scope_binding != expected_scope:
            raise ObservationError("Product applicability evidence is bound to a different scope")


@dataclass(frozen=True)
class ObservabilityBinding:
    health_profile_id: str
    sli_profile_ids: tuple[str, ...]
    alert_profile_ids: tuple[str, ...]
    direct_sli_applicable: bool
    binding_scope: str
    no_applicable_case: NoApplicableCaseEvidence | None = None

    def __post_init__(self) -> None:
        if self.health_profile_id not in CORE_HEALTH_PROFILES:
            raise ObservationError("unknown health profile binding")
        unknown_sli = set(self.sli_profile_ids) - CORE_SLI_PROFILES
        if unknown_sli:
            raise ObservationError(f"unknown SLI binding(s): {sorted(unknown_sli)}")
        unknown_alert = set(self.alert_profile_ids) - CORE_ALERT_PROFILES
        if unknown_alert:
            raise ObservationError(f"unknown alert binding(s): {sorted(unknown_alert)}")
        if not self.binding_scope:
            raise ObservationError("observability binding requires an exact scope")
        if not self.direct_sli_applicable:
            if self.no_applicable_case is None:
                raise ObservationError("direct SLI NO_APPLICABLE_CASE requires evidence-backed disposition")
            self.no_applicable_case.validate_for(self.binding_scope)
        elif self.no_applicable_case is not None:
            raise ObservationError("applicable direct SLI cannot also claim NO_APPLICABLE_CASE")


def binding_for_reliability_profile(reliability_profile_id: str) -> ReliabilityObservabilityJoin:
    return join_for(reliability_profile_id)


def require_product_applicability(evidence: ProductApplicabilityEvidence, *, expected_scope: str) -> bool:
    """Fail closed: Product applicability requires current authority/evidence bound to exact scope."""
    evidence.validate_for(expected_scope)
    return evidence.enabled
