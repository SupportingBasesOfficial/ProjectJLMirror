from __future__ import annotations

from dataclasses import dataclass

from .catalog import ReliabilityObservabilityJoin, join_for
from .model import CORE_ALERT_PROFILES, CORE_HEALTH_PROFILES, CORE_SLI_PROFILES, ObservationError


@dataclass(frozen=True)
class ObservabilityBinding:
    health_profile_id: str
    sli_profile_ids: tuple[str, ...]
    alert_profile_ids: tuple[str, ...]
    direct_sli_applicable: bool
    no_applicable_case_reason: str | None = None

    def __post_init__(self) -> None:
        if self.health_profile_id not in CORE_HEALTH_PROFILES:
            raise ObservationError("unknown health profile binding")
        unknown_sli = set(self.sli_profile_ids) - CORE_SLI_PROFILES
        if unknown_sli:
            raise ObservationError(f"unknown SLI binding(s): {sorted(unknown_sli)}")
        unknown_alert = set(self.alert_profile_ids) - CORE_ALERT_PROFILES
        if unknown_alert:
            raise ObservationError(f"unknown alert binding(s): {sorted(unknown_alert)}")
        if not self.direct_sli_applicable and not self.no_applicable_case_reason:
            raise ObservationError("direct SLI NO_APPLICABLE_CASE requires an explicit semantic reason")
        if self.direct_sli_applicable and self.no_applicable_case_reason is not None:
            raise ObservationError("applicable direct SLI cannot also claim NO_APPLICABLE_CASE")


def binding_for_reliability_profile(reliability_profile_id: str) -> ReliabilityObservabilityJoin:
    return join_for(reliability_profile_id)


def require_product_applicability(*, product_state_proven: bool, enabled: bool) -> bool:
    """Fail closed: unknown Product applicability is not absence or enablement."""
    if not product_state_proven:
        raise ObservationError("Product applicability is unproven")
    return enabled
