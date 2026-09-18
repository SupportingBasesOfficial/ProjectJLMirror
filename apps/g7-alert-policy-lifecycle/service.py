from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from domain import ActiveAlert, Decision, PolicyVersion, SourceState, evaluate


class EffectPort(Protocol):
    def current_policy(self, tenant_id: str, policy_id: str, policy_version: int) -> tuple[PolicyVersion, bool]: ...
    def current_source(self, policy: PolicyVersion, subject_id: str) -> SourceState: ...
    def active_alert(self, policy: PolicyVersion, subject_id: str) -> ActiveAlert | None: ...
    def apply_decision(self, decision: Decision) -> dict: ...


@dataclass
class AlertPolicyLifecycleService:
    effects: EffectPort

    def evaluate_subject(
        self,
        *,
        tenant_id: str,
        policy_id: str,
        policy_version: int,
        subject_id: str,
    ) -> dict:
        policy, effective = self.effects.current_policy(tenant_id, policy_id, policy_version)
        state = self.effects.current_source(policy, subject_id)
        active = self.effects.active_alert(policy, subject_id)
        decision = evaluate(policy, state, active, policy_is_effective=effective)
        if decision.action == "none":
            return {
                "decision_id": decision.decision_id,
                "action": "none",
                "alert_id": decision.alert_id,
                "source_revision": decision.source_revision,
            }
        return self.effects.apply_decision(decision)
