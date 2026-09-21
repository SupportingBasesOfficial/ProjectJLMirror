from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256

STATES={"open","in_progress","resolved","closed"}
TRANSITIONS={
    ("open","in_progress"),
    ("open","resolved"),
    ("in_progress","resolved"),
    ("resolved","closed"),
}
SYNC_STATES={"pending","dispatching","linked","failed","unknown","reconciliation_required"}


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


def require_transition(current:str,target:str)->None:
    if (current,target) not in TRANSITIONS:
        raise ValueError("unsupported incident transition")


def require_comment(body:str)->None:
    if not body or len(body)>4000:
        raise ValueError("comment body invalid")
