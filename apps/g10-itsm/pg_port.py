from __future__ import annotations

import json
from typing import Any
from domain import AuthoritySnapshot


def _decode(value:Any)->Any:
    if isinstance(value,str):
        return json.loads(value)
    return value


class PgIncidentGateway:
    def __init__(self,connection:Any):
        self.connection=connection

    def _scalar(self,statement:str,params:tuple[Any,...])->Any:
        with self.connection.cursor() as cursor:
            cursor.execute(statement,params)
            row=cursor.fetchone()
        return None if row is None else _decode(row[0])

    @staticmethod
    def _authority(a:AuthoritySnapshot)->str:
        return json.dumps({
            "tenant_id":a.tenant_id,"principal_id":a.principal_id,
            "current":a.current,"action":a.action,"policy_revision":a.policy_revision,
        },separators=(",",":"))

    def create_incident(self,**k)->dict:
        return self._scalar(
            "SELECT itsm.g10_create_incident(%s,%s,%s,%s,%s,%s,%s::jsonb)",
            (k["tenant_id"],k["alert_id"],k["title"],k["description"],
             k["actor_principal_id"],k["logical_action_id"],self._authority(k["authority"]))
        )

    def transition_incident(self,**k)->dict:
        return self._scalar(
            "SELECT itsm.g10_transition_incident(%s,%s,%s,%s,%s,%s::jsonb)",
            (k["tenant_id"],k["incident_id"],k["target_state"],k["actor_principal_id"],
             k["logical_action_id"],self._authority(k["authority"]))
        )

    def assign_incident(self,**k)->dict:
        return self._scalar(
            "SELECT itsm.g10_assign_incident(%s,%s,%s,%s,%s,%s::jsonb)",
            (k["tenant_id"],k["incident_id"],k["assignee_principal_id"],k["actor_principal_id"],
             k["logical_action_id"],self._authority(k["authority"]))
        )

    def add_comment(self,**k)->dict:
        return self._scalar(
            "SELECT itsm.g10_add_comment(%s,%s,%s,%s,%s,%s::jsonb)",
            (k["tenant_id"],k["incident_id"],k["body"],k["actor_principal_id"],
             k["logical_action_id"],self._authority(k["authority"]))
        )

    def get_incident(self,tenant_id:str,incident_id:str)->dict:
        return self._scalar("SELECT itsm.g10_get_incident(%s,%s)",(tenant_id,incident_id))

    def list_alert_incidents(self,tenant_id:str,alert_id:str)->list[dict]:
        return list(self._scalar("SELECT itsm.g10_list_alert_incidents(%s,%s)",(tenant_id,alert_id)) or [])

    def next_sync_candidate(self,tenant_id:str)->dict|None:
        return self._scalar("SELECT itsm.g10_next_sync_candidate(%s)",(tenant_id,))

    def claim_sync(self,tenant_id:str,outbox_id:str,executor_id:str,claim_seconds:int)->dict:
        return self._scalar("SELECT itsm.g10_claim_sync(%s,%s,%s,%s)",
                            (tenant_id,outbox_id,executor_id,claim_seconds))

    def complete_sync(self,tenant_id:str,outbox_id:str,executor_id:str,result_state:str,
                      provider_ticket_ref:str|None,provider_evidence:dict,failure_class:str|None)->dict:
        return self._scalar(
            "SELECT itsm.g10_complete_sync(%s,%s,%s,%s,%s,%s::jsonb,%s)",
            (tenant_id,outbox_id,executor_id,result_state,provider_ticket_ref,
             json.dumps(provider_evidence,separators=(",",":")),failure_class)
        )

    def schedule_sync_retry(self,tenant_id:str,incident_id:str)->dict:
        return self._scalar(
            "SELECT itsm.g10_schedule_sync_retry(%s,%s)",
            (tenant_id,incident_id),
        )

    def reconcile_sync(self,tenant_id:str,outbox_id:str)->dict:
        return self._scalar("SELECT itsm.g10_reconcile_sync(%s,%s)",(tenant_id,outbox_id))
