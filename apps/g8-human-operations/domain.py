from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from typing import Literal

ResponsibilityRole=Literal[
    "technical_responsible","service_owner","operator","customer_responsible"
]
AssignmentSource=Literal["manual","configured"]
ActionKind=Literal[
    "investigate_alert","acknowledge_alert","review_alert","customer_review_required"
]
ViewerSide=Literal["internal","customer"]

RESPONSIBILITY_ROLES={
    "technical_responsible","service_owner","operator","customer_responsible"
}
ASSIGNMENT_SOURCES={"manual","configured"}
ACTION_KINDS={
    "investigate_alert","acknowledge_alert","review_alert","customer_review_required"
}
VIEWER_SIDES={"internal","customer"}
VISIBILITY_CAPABILITY="platform_native_authenticated_view@1"


@dataclass(frozen=True)
class AuthoritySnapshot:
    tenant_id:str
    principal_id:str
    current:bool
    action:str
    policy_revision:str

    def validate(self, *, tenant_id:str, actor_principal_id:str) -> None:
        if not self.current:
            raise PermissionError("current authority required")
        if self.tenant_id!=tenant_id or self.principal_id!=actor_principal_id:
            raise PermissionError("authority identity mismatch")
        if not self.action or not self.policy_revision:
            raise PermissionError("bounded authority evidence required")


def deterministic_id(prefix:str,*parts:str)->str:
    material="\x1f".join(parts)
    return prefix+sha256(material.encode()).hexdigest()


def require_responsibility(role:str,source:str)->None:
    if role not in RESPONSIBILITY_ROLES:
        raise ValueError("unsupported responsibility role")
    if source not in ASSIGNMENT_SOURCES:
        raise ValueError("unsupported assignment source")


def require_action(kind:str)->None:
    if kind not in ACTION_KINDS:
        raise ValueError("unsupported action kind")


def require_visibility(side:str,capability:str)->None:
    if side not in VIEWER_SIDES:
        raise ValueError("unsupported viewer side")
    if capability!=VISIBILITY_CAPABILITY:
        raise ValueError("unsupported visibility capability")
