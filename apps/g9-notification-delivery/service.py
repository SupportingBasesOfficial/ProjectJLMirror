from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from domain import AuthoritySnapshot,CHANNEL,require_intent


class NotificationPort(Protocol):
    def create_intent(self,**kwargs)->dict: ...
    def get_intent(self,tenant_id:str,intent_id:str)->dict: ...
    def list_alert_intents(self,tenant_id:str,alert_id:str)->list[dict]: ...


@dataclass
class NotificationService:
    port:NotificationPort

    def create(
        self,*,authority:AuthoritySnapshot,tenant_id:str,alert_id:str,
        recipient_principal_id:str|None,destination_ref:str,reason:str,
        payload_ref:str,payload_hash:str,visibility_requirement_id:str|None,
        actor_principal_id:str,logical_action_id:str
    )->dict:
        authority.validate(tenant_id=tenant_id,actor_principal_id=actor_principal_id)
        require_intent(reason,CHANNEL)
        if not destination_ref or len(destination_ref)>512:
            raise ValueError("destination reference invalid")
        if not payload_ref or len(payload_ref)>512 or not payload_hash or len(payload_hash)>128:
            raise ValueError("payload reference invalid")
        return self.port.create_intent(
            authority=authority,tenant_id=tenant_id,alert_id=alert_id,
            recipient_principal_id=recipient_principal_id,destination_ref=destination_ref,
            channel_class=CHANNEL,reason=reason,payload_ref=payload_ref,payload_hash=payload_hash,
            visibility_requirement_id=visibility_requirement_id,
            actor_principal_id=actor_principal_id,logical_action_id=logical_action_id,
        )
