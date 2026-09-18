from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from domain import AuthoritySnapshot, require_action, require_responsibility, require_visibility


class HumanOperationsPort(Protocol):
    def assign_resource_responsibility(self, **kwargs) -> dict: ...
    def end_resource_responsibility(self, **kwargs) -> dict: ...
    def assign_alert_action(self, **kwargs) -> dict: ...
    def acknowledge_alert(self, **kwargs) -> dict: ...
    def create_visibility_requirement(self, **kwargs) -> dict: ...
    def record_visibility_receipt(self, **kwargs) -> dict: ...
    def alert_human_operations(self, tenant_id:str, alert_id:str) -> dict: ...
    def resource_responsibilities(self, tenant_id:str, resource_id:str) -> list[dict]: ...


@dataclass
class HumanOperationsService:
    port:HumanOperationsPort

    def assign_resource(
        self, *,
        authority:AuthoritySnapshot,
        tenant_id:str,
        resource_id:str,
        responsible_principal_id:str,
        responsibility_role:str,
        assignment_source:str,
        actor_principal_id:str,
        logical_action_id:str,
    )->dict:
        authority.validate(tenant_id=tenant_id,actor_principal_id=actor_principal_id)
        require_responsibility(responsibility_role,assignment_source)
        return self.port.assign_resource_responsibility(
            authority=authority,tenant_id=tenant_id,resource_id=resource_id,
            responsible_principal_id=responsible_principal_id,
            responsibility_role=responsibility_role,assignment_source=assignment_source,
            actor_principal_id=actor_principal_id,logical_action_id=logical_action_id,
        )

    def assign_action(
        self, *,
        authority:AuthoritySnapshot,
        tenant_id:str,
        alert_id:str,
        owner_principal_id:str,
        action_kind:str,
        actor_principal_id:str,
        logical_action_id:str,
    )->dict:
        authority.validate(tenant_id=tenant_id,actor_principal_id=actor_principal_id)
        require_action(action_kind)
        return self.port.assign_alert_action(
            authority=authority,tenant_id=tenant_id,alert_id=alert_id,
            owner_principal_id=owner_principal_id,action_kind=action_kind,
            actor_principal_id=actor_principal_id,logical_action_id=logical_action_id,
        )

    def ack(
        self, *,
        authority:AuthoritySnapshot,
        tenant_id:str,
        alert_id:str,
        actor_principal_id:str,
        logical_action_id:str,
        note:str|None=None,
    )->dict:
        authority.validate(tenant_id=tenant_id,actor_principal_id=actor_principal_id)
        return self.port.acknowledge_alert(
            authority=authority,tenant_id=tenant_id,alert_id=alert_id,
            actor_principal_id=actor_principal_id,logical_action_id=logical_action_id,
            note=note,
        )

    def require_visibility(
        self, *,
        authority:AuthoritySnapshot,
        tenant_id:str,
        alert_id:str,
        viewer_principal_id:str,
        viewer_side:str,
        capability_class:str,
        presentation_ref:str,
        actor_principal_id:str,
        logical_action_id:str,
    )->dict:
        authority.validate(tenant_id=tenant_id,actor_principal_id=actor_principal_id)
        require_visibility(viewer_side,capability_class)
        return self.port.create_visibility_requirement(
            authority=authority,tenant_id=tenant_id,alert_id=alert_id,
            viewer_principal_id=viewer_principal_id,viewer_side=viewer_side,
            capability_class=capability_class,presentation_ref=presentation_ref,
            actor_principal_id=actor_principal_id,logical_action_id=logical_action_id,
        )
