from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

from .model import (
    CORE_ALERT_PROFILES,
    CORE_HEALTH_PROFILES,
    CORE_SIGNAL_PROFILES,
    CORE_SLI_PROFILES,
    ObservationError,
)


@dataclass(frozen=True)
class ApplicabilityResolution:
    state: str
    sli_profile_ids: tuple[str, ...] = ()
    alert_profile_ids: tuple[str, ...] = ()
    open_decision_id: str | None = None
    no_applicable_case_reason: str | None = None


@dataclass(frozen=True)
class ReliabilityObservabilityJoin:
    reliability_profile_id: str
    profile_version: int
    diagnostic_signal_ids: tuple[str, ...]
    health_profile_ids: tuple[str, ...]
    sli_profile_ids: tuple[str, ...]
    impact_sli_profile_ids: tuple[str, ...]
    alert_profile_ids: tuple[str, ...]
    required_fault_vectors: tuple[str, ...]
    direct_sli_no_applicable_case_reason: str | None = None
    product_selector: str | None = None

    def __post_init__(self) -> None:
        if not self.reliability_profile_id.startswith("rel.") or self.profile_version != 1:
            raise ObservationError("invalid reliability observability join key")
        unknown_signal = set(self.diagnostic_signal_ids) - CORE_SIGNAL_PROFILES
        unknown_health = set(self.health_profile_ids) - CORE_HEALTH_PROFILES
        unknown_sli = set(self.sli_profile_ids + self.impact_sli_profile_ids) - CORE_SLI_PROFILES
        unknown_alert = set(self.alert_profile_ids) - CORE_ALERT_PROFILES
        if unknown_signal or unknown_health or unknown_sli or unknown_alert:
            raise ObservationError("join references an unknown observability profile")
        if not self.diagnostic_signal_ids or not self.health_profile_ids:
            raise ObservationError("same-key join requires signal and health bindings")
        if not self.required_fault_vectors:
            raise ObservationError("same-key join requires fault-vector evidence")
        if self.product_selector is None:
            if not self.sli_profile_ids and not self.direct_sli_no_applicable_case_reason:
                raise ObservationError("direct SLI omission requires explicit NO_APPLICABLE_CASE reason")
            if self.sli_profile_ids and self.direct_sli_no_applicable_case_reason:
                raise ObservationError("direct SLI cannot be both applicable and NO_APPLICABLE_CASE")

    def resolve_product_applicability(self, selector_value: str) -> ApplicabilityResolution:
        if self.product_selector == "webhook_product_state":
            if selector_value == "product_enabled":
                return ApplicabilityResolution(state="open", open_decision_id="OPEN-OBS-035")
            if selector_value == "product_not_enabled":
                return ApplicabilityResolution(
                    state="no_applicable_case",
                    no_applicable_case_reason="outbound webhook Product capability is not enabled",
                )
            if selector_value == "product_state_unproven":
                return ApplicabilityResolution(state="open", open_decision_id="OPEN-OBS-037")
        elif self.product_selector == "artifact_delivery_product_state":
            if selector_value == "product_exposed_delivery":
                return ApplicabilityResolution(
                    state="applicable",
                    sli_profile_ids=("sli.artifact.delivery@1",),
                    alert_profile_ids=self.alert_profile_ids,
                )
            if selector_value == "product_not_exposed_delivery":
                return ApplicabilityResolution(
                    state="no_applicable_case",
                    alert_profile_ids=self.alert_profile_ids,
                    no_applicable_case_reason="Product-facing artifact delivery is not exposed",
                )
            if selector_value == "product_state_unproven":
                return ApplicabilityResolution(
                    state="open",
                    alert_profile_ids=self.alert_profile_ids,
                    open_decision_id="OPEN-OBS-037",
                )
        raise ObservationError(
            f"invalid or unproven Product applicability selector for {self.reliability_profile_id}"
        )


def _join(rid, signals, health, slis, alerts, vectors, *, impact=(), na=None, selector=None):
    return ReliabilityObservabilityJoin(rid, 1, signals, health, slis, impact, alerts, vectors, na, selector)


RELIABILITY_OBSERVABILITY_JOINS: Mapping[str, ReliabilityObservabilityJoin] = MappingProxyType({
    j.reliability_profile_id: j for j in (
        _join("rel.control-plane-placement@1", ("obs.operation.state@1","obs.security.authority-freshness@1","obs.recovery.reconciliation@1"), ("health.control-plane@1",), ("sli.control-plane.admission@1",), ("alert.customer-impact@1","alert.recovery-continuity@1","alert.security-trust@1"), ("OBSV-013","OBSV-014","OBSV-015","OBSV-021")),
        _join("rel.cell-transactional-store@1", ("obs.request.outcome@1","obs.operation.state@1","obs.recovery.reconciliation@1"), ("health.cell@1",), ("sli.cell.admission@1","sli.api.outcome@1"), ("alert.customer-impact@1","alert.recovery-continuity@1","alert.capacity-saturation@1"), ("OBSV-013","OBSV-014","OBSV-016","OBSV-025")),
        _join("rel.security-session-authority@1", ("obs.security.authority-freshness@1","obs.request.outcome@1"), ("health.security-authority@1",), (), ("alert.security-trust@1","alert.customer-impact@1"), ("OBSV-003","OBSV-013","OBSV-015","OBSV-027"), impact=("sli.api.outcome@1",), na="authorization correctness is a hard gate, not an error-budget allowance"),
        _join("rel.placement-reference-cache@1", ("obs.security.authority-freshness@1","obs.operation.state@1"), ("health.control-plane@1",), (), ("alert.recovery-continuity@1","alert.customer-impact@1"), ("OBSV-013","OBSV-014","OBSV-021"), impact=("sli.control-plane.admission@1","sli.cell.admission@1"), na="placement cache correctness is observed through consuming admission outcomes"),
        _join("rel.performance-cache@1", ("obs.request.outcome@1",), ("health.api-bff@1",), ("sli.api.outcome@1","sli.api.latency@1"), ("alert.customer-impact@1","alert.capacity-saturation@1"), ("OBSV-011","OBSV-025")),
        _join("rel.replay-consume-state@1", ("obs.message-equivalence.admission@1","obs.message-equivalence.verifier@1","obs.recovery.reconciliation@1"), ("health.message-equivalence@1","health.recovery@1"), (), ("alert.recovery-continuity@1","alert.security-trust@1"), ("OBSV-023","OBSV-032","OBSV-033","OBSV-034","OBSV-035","OBSV-036"), impact=("sli.recovery.convergence@1",), na="duplicate/replay correctness is a hard gate; recovery convergence carries impact"),
        _join("rel.secret-key-authority@1", ("obs.security.authority-freshness@1",), ("health.security-authority@1",), (), ("alert.security-trust@1","alert.durable-progress@1"), ("OBSV-015","OBSV-027"), impact=("sli.api.outcome@1","sli.async.progress@1","sli.recovery.convergence@1"), na="cryptographic authority correctness is a hard gate"),
        _join("rel.configuration-authority@1", ("obs.configuration.generation@1","obs.security.authority-freshness@1"), ("health.control-plane@1","health.cell@1"), (), ("alert.customer-impact@1","alert.security-trust@1"), ("OBSV-013","OBSV-021"), impact=("sli.control-plane.admission@1","sli.cell.admission@1"), na="configuration authority correctness is measured through consuming admission"),
        _join("rel.outbox-publication@1", ("obs.async.progress@1","obs.operation.state@1"), ("health.async-worker@1",), ("sli.async.progress@1",), ("alert.durable-progress@1","alert.capacity-saturation@1"), ("OBSV-001","OBSV-016","OBSV-025")),
        _join("rel.broker-job-transport@1", ("obs.async.transport@1","obs.async.progress@1"), ("health.async-worker@1",), ("sli.async.progress@1",), ("alert.durable-progress@1","alert.capacity-saturation@1"), ("OBSV-008","OBSV-016","OBSV-025")),
        _join("rel.consumer-inbox-effect@1", ("obs.async.progress@1","obs.message-equivalence.admission@1","obs.message-equivalence.verifier@1"), ("health.async-worker@1","health.message-equivalence@1"), ("sli.async.progress@1",), ("alert.durable-progress@1","alert.recovery-continuity@1","alert.security-trust@1"), ("OBSV-016","OBSV-031","OBSV-033","OBSV-034","OBSV-035","OBSV-036")),
        _join("rel.external-provider@1", ("obs.provider.operation@1","obs.operation.state@1","obs.recovery.reconciliation@1"), ("health.provider-adapter@1",), ("sli.provider.outcome@1",), ("alert.customer-impact@1","alert.durable-progress@1","alert.capacity-saturation@1","alert.security-trust@1"), ("OBSV-001","OBSV-015","OBSV-017","OBSV-025")),
        _join("rel.realtime-fanout@1", ("obs.realtime.lifecycle@1",), ("health.realtime@1",), ("sli.realtime.delivery@1",), ("alert.customer-impact@1","alert.capacity-saturation@1"), ("OBSV-001","OBSV-013","OBSV-025")),
        _join("rel.webhook-delivery@1", ("obs.webhook.delivery@1","obs.recovery.reconciliation@1"), ("health.webhook-delivery@1",), (), (), ("OBSV-017","OBSV-019","OBSV-025","OBSV-037"), selector="webhook_product_state"),
        _join("rel.telemetry-plane@1", ("obs.observability.pipeline@1",), ("health.observability-pipeline@1",), ("sli.observability.integrity@1",), ("alert.telemetry-integrity@1","alert.capacity-saturation@1"), ("OBSV-008","OBSV-010","OBSV-011","OBSV-026")),
        _join("rel.customer-telemetry-acceptance@1", ("obs.telemetry.acceptance@1","obs.async.progress@1","obs.recovery.reconciliation@1"), ("health.customer-telemetry@1",), ("sli.customer-telemetry.acceptance@1",), ("alert.customer-impact@1","alert.durable-progress@1","alert.capacity-saturation@1","alert.recovery-continuity@1"), ("OBSV-010","OBSV-012","OBSV-016","OBSV-025")),
        _join("rel.mandatory-audit-plane@1", ("obs.audit.responsibility-health@1",), ("health.audit-plane@1",), (), ("alert.customer-impact@1","alert.security-trust@1"), ("OBSV-009","OBSV-011","OBSV-015"), impact=("sli.api.outcome@1","sli.async.progress@1"), na="mandatory audit durability is a hard responsibility gate"),
        _join("rel.artifact-storage@1", ("obs.artifact.lifecycle@1","obs.recovery.reconciliation@1"), ("health.artifact@1",), (), ("alert.customer-impact@1","alert.recovery-continuity@1","alert.capacity-saturation@1","alert.security-trust@1"), ("OBSV-014","OBSV-024","OBSV-025","OBSV-028","OBSV-037"), selector="artifact_delivery_product_state"),
        _join("rel.reporting-derived@1", ("obs.request.outcome@1","obs.operation.state@1","obs.async.progress@1"), ("health.api-bff@1","health.async-worker@1"), ("sli.api.outcome@1","sli.async.progress@1"), ("alert.customer-impact@1","alert.durable-progress@1","alert.capacity-saturation@1"), ("OBSV-016","OBSV-025","OBSV-029")),
        _join("rel.privileged-operations@1", ("obs.operation.state@1","obs.security.authority-freshness@1","obs.recovery.reconciliation@1"), ("health.security-authority@1","health.recovery@1","health.async-worker@1"), (), ("alert.security-trust@1","alert.recovery-continuity@1","alert.durable-progress@1"), ("OBSV-003","OBSV-014","OBSV-015","OBSV-028"), impact=("sli.async.progress@1","sli.recovery.convergence@1"), na="privileged authorization correctness is a hard gate"),
    )
})

EXPECTED_RELIABILITY_PROFILE_IDS = frozenset(RELIABILITY_OBSERVABILITY_JOINS)


def join_for(reliability_profile_id: str) -> ReliabilityObservabilityJoin:
    try:
        return RELIABILITY_OBSERVABILITY_JOINS[reliability_profile_id]
    except KeyError as exc:
        raise ObservationError(f"no exact Phase 11 -> Phase 12 observability join for {reliability_profile_id}") from exc
