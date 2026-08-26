from __future__ import annotations

from dataclasses import dataclass

from .model import HealthAssessment, HealthState


@dataclass(frozen=True)
class ObservabilityPipelineEvidence:
    ingest_current: bool | None
    export_current: bool | None
    query_current: bool | None
    self_observation_confidence_current: bool | None
    drop_state_known: bool

    def assess(self) -> HealthAssessment:
        values = (
            self.ingest_current,
            self.export_current,
            self.query_current,
            self.self_observation_confidence_current,
        )
        if any(value is None for value in values) or not self.drop_state_known:
            return HealthAssessment(
                "health.observability-pipeline@1",
                HealthState.UNKNOWN,
                "pipeline_evidence_incomplete",
                False,
            )
        if self.self_observation_confidence_current is False:
            return HealthAssessment(
                "health.observability-pipeline@1",
                HealthState.UNKNOWN,
                "self_observation_confidence_not_current",
                False,
            )
        if not all((self.ingest_current, self.export_current, self.query_current)):
            return HealthAssessment(
                "health.observability-pipeline@1",
                HealthState.DEGRADED,
                "pipeline_degradation_proven",
                True,
            )
        return HealthAssessment(
            "health.observability-pipeline@1",
            HealthState.HEALTHY,
            "pipeline_evidence_complete",
            True,
        )
