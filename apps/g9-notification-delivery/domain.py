from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256

CHANNEL="whatsapp_business@1"
INTENT_REASONS={
    "alert_requires_attention",
    "alert_action_requested",
    "customer_awareness_required",
}
ATTEMPT_STATES={
    "dispatching","sent","provider_accepted","delivered","failed","unknown"
}
EVIDENCE_KINDS={
    "provider_accepted","delivered","external_read_observed","failed","unknown"
}
MAX_ATTEMPTS=3


@dataclass(frozen=True)
class AuthoritySnapshot:
    tenant_id:str
    principal_id:str
    current:bool
    action:str
    policy_revision:str

    def validate(self,*,tenant_id:str,actor_principal_id:str)->None:
        if not self.current:
            raise PermissionError("current authority required")
        if self.tenant_id!=tenant_id or self.principal_id!=actor_principal_id:
            raise PermissionError("authority identity mismatch")
        if not self.action or not self.policy_revision:
            raise PermissionError("bounded authority evidence required")


def deterministic_id(prefix:str,*parts:str)->str:
    return prefix+sha256("\x1f".join(parts).encode()).hexdigest()


def require_intent(reason:str,channel:str)->None:
    if reason not in INTENT_REASONS:
        raise ValueError("unsupported notification reason")
    if channel!=CHANNEL:
        raise ValueError("unsupported notification channel")


def require_attempt_state(state:str)->None:
    if state not in ATTEMPT_STATES:
        raise ValueError("unsupported attempt state")


def require_evidence(kind:str)->None:
    if kind not in EVIDENCE_KINDS:
        raise ValueError("unsupported provider evidence kind")
