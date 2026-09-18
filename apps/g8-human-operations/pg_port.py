from __future__ import annotations

import json
from typing import Any

from domain import AuthoritySnapshot


def _decode(value: Any) -> Any:
    if isinstance(value,str):
        return json.loads(value)
    return value


class PgHumanOperationsGateway:
    def __init__(self,connection:Any):
        self.connection=connection

    def _scalar(self,statement:str,params:tuple[Any,...])->Any:
        with self.connection.cursor() as cursor:
            cursor.execute(statement,params)
            row=cursor.fetchone()
        return None if row is None else _decode(row[0])

    @staticmethod
    def _authority(a:AuthoritySnapshot)->dict:
        return {
            "tenant_id":a.tenant_id,
            "principal_id":a.principal_id,
            "current":a.current,
            "action":a.action,
            "policy_revision":a.policy_revision,
        }

    def assign_resource_responsibility(self,**kwargs)->dict:
        a=kwargs["authority"]
        return self._scalar(
            "SELECT human_operations.g8_assign_resource_responsibility(%s,%s,%s,%s,%s,%s,%s,%s::jsonb)",
            (
                kwargs["tenant_id"],kwargs["resource_id"],kwargs["responsible_principal_id"],
                kwargs["responsibility_role"],kwargs["assignment_source"],
                kwargs["actor_principal_id"],kwargs["logical_action_id"],
                json.dumps(self._authority(a),separators=(",",":")),
            ),
        )

    def end_resource_responsibility(
        self,*,authority:AuthoritySnapshot,tenant_id:str,assignment_id:str,
        actor_principal_id:str,end_reason:str
    )->dict:
        return self._scalar(
            "SELECT human_operations.g8_end_resource_responsibility(%s,%s,%s,%s,%s::jsonb)",
            (
                tenant_id,assignment_id,actor_principal_id,end_reason,
                json.dumps(self._authority(authority),separators=(",",":")),
            ),
        )

    def assign_alert_action(self,**kwargs)->dict:
        a=kwargs["authority"]
        return self._scalar(
            "SELECT human_operations.g8_assign_alert_action(%s,%s,%s,%s,%s,%s,%s::jsonb)",
            (
                kwargs["tenant_id"],kwargs["alert_id"],kwargs["owner_principal_id"],
                kwargs["action_kind"],kwargs["actor_principal_id"],kwargs["logical_action_id"],
                json.dumps(self._authority(a),separators=(",",":")),
            ),
        )

    def acknowledge_alert(self,**kwargs)->dict:
        a=kwargs["authority"]
        return self._scalar(
            "SELECT human_operations.g8_acknowledge_alert(%s,%s,%s,%s,%s,%s::jsonb)",
            (
                kwargs["tenant_id"],kwargs["alert_id"],kwargs["actor_principal_id"],
                kwargs["logical_action_id"],kwargs.get("note"),
                json.dumps(self._authority(a),separators=(",",":")),
            ),
        )

    def create_visibility_requirement(self,**kwargs)->dict:
        a=kwargs["authority"]
        return self._scalar(
            "SELECT human_operations.g8_create_visibility_requirement(%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb)",
            (
                kwargs["tenant_id"],kwargs["alert_id"],kwargs["viewer_principal_id"],
                kwargs["viewer_side"],kwargs["capability_class"],kwargs["presentation_ref"],
                kwargs["actor_principal_id"],kwargs["logical_action_id"],
                json.dumps(self._authority(a),separators=(",",":")),
            ),
        )

    def record_visibility_receipt(
        self,*,authority:AuthoritySnapshot,tenant_id:str,requirement_id:str,
        viewer_principal_id:str,logical_action_id:str,session_evidence:dict
    )->dict:
        return self._scalar(
            "SELECT human_operations.g8_record_visibility_receipt(%s,%s,%s,%s,%s::jsonb,%s::jsonb)",
            (
                tenant_id,requirement_id,viewer_principal_id,logical_action_id,
                json.dumps(self._authority(authority),separators=(",",":")),
                json.dumps(session_evidence,separators=(",",":")),
            ),
        )

    def alert_human_operations(self,tenant_id:str,alert_id:str)->dict:
        return self._scalar(
            "SELECT human_operations.g8_alert_human_operations(%s,%s)",
            (tenant_id,alert_id),
        )

    def resource_responsibilities(self,tenant_id:str,resource_id:str)->list[dict]:
        return list(self._scalar(
            "SELECT human_operations.g8_resource_responsibilities(%s,%s)",
            (tenant_id,resource_id),
        ) or [])
