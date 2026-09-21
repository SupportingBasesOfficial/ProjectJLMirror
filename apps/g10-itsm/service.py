from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from domain import AuthoritySnapshot,require_comment


class IncidentPort(Protocol):
    def create_incident(self,**kwargs)->dict: ...
    def transition_incident(self,**kwargs)->dict: ...
    def assign_incident(self,**kwargs)->dict: ...
    def add_comment(self,**kwargs)->dict: ...
    def get_incident(self,tenant_id:str,incident_id:str)->dict: ...
    def list_alert_incidents(self,tenant_id:str,alert_id:str)->list[dict]: ...


@dataclass
class IncidentService:
    port:IncidentPort

    def create(self,*,authority:AuthoritySnapshot,tenant_id:str,alert_id:str,title:str,
               description:str|None,actor_principal_id:str,logical_action_id:str)->dict:
        authority.validate(tenant_id=tenant_id,actor_principal_id=actor_principal_id)
        if not title or len(title)>240:
            raise ValueError("title invalid")
        if description is not None and len(description)>8000:
            raise ValueError("description invalid")
        return self.port.create_incident(
            authority=authority,tenant_id=tenant_id,alert_id=alert_id,title=title,
            description=description,actor_principal_id=actor_principal_id,
            logical_action_id=logical_action_id,
        )

    def transition(self,*,authority:AuthoritySnapshot,tenant_id:str,incident_id:str,
                   target_state:str,actor_principal_id:str,logical_action_id:str)->dict:
        authority.validate(tenant_id=tenant_id,actor_principal_id=actor_principal_id)
        return self.port.transition_incident(
            authority=authority,tenant_id=tenant_id,incident_id=incident_id,
            target_state=target_state,actor_principal_id=actor_principal_id,
            logical_action_id=logical_action_id,
        )

    def assign(self,*,authority:AuthoritySnapshot,tenant_id:str,incident_id:str,
               assignee_principal_id:str,actor_principal_id:str,logical_action_id:str)->dict:
        authority.validate(tenant_id=tenant_id,actor_principal_id=actor_principal_id)
        if not assignee_principal_id:
            raise ValueError("assignee required")
        return self.port.assign_incident(
            authority=authority,tenant_id=tenant_id,incident_id=incident_id,
            assignee_principal_id=assignee_principal_id,
            actor_principal_id=actor_principal_id,logical_action_id=logical_action_id,
        )

    def comment(self,*,authority:AuthoritySnapshot,tenant_id:str,incident_id:str,
                body:str,actor_principal_id:str,logical_action_id:str)->dict:
        authority.validate(tenant_id=tenant_id,actor_principal_id=actor_principal_id)
        require_comment(body)
        return self.port.add_comment(
            authority=authority,tenant_id=tenant_id,incident_id=incident_id,body=body,
            actor_principal_id=actor_principal_id,logical_action_id=logical_action_id,
        )
