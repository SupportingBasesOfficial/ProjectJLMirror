from __future__ import annotations

import json
from typing import Any

from domain import ApplicationErrorEvent


def _decode(value:Any)->Any:
    if isinstance(value,str): return json.loads(value)
    return value


class PgIncidentResponseGateway:
    def __init__(self,connection:Any):
        self.connection=connection

    def _scalar(self,statement:str,params:tuple[Any,...])->Any:
        with self.connection.cursor() as cursor:
            cursor.execute(statement,params)
            row=cursor.fetchone()
        return None if row is None else _decode(row[0])

    def get_policy(self,tenant_id:str)->dict|None:
        return self._scalar("SELECT incident_response.g11_get_policy(%s)",(tenant_id,))

    def upsert_policy(self,tenant_id:str,policy:dict,actor_principal_id:str)->dict:
        return self._scalar(
            "SELECT incident_response.g11_upsert_policy(%s,%s::jsonb,%s)",
            (tenant_id,json.dumps(policy,separators=(",",":")),actor_principal_id),
        )

    def claim_dedupe(self,tenant_id:str,application_id:str,error_code:str,bucket_ts:str)->bool:
        result=self._scalar(
            "SELECT incident_response.g11_claim_dedupe(%s,%s,%s,%s)",
            (tenant_id,application_id,error_code,bucket_ts),
        )
        return bool(result)

    def store_event(self,event:ApplicationErrorEvent)->dict:
        raw=None if event.raw_payload is None else json.dumps(event.raw_payload,separators=(",",":"))
        return self._scalar(
            "SELECT incident_response.g11_store_event(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb)",
            (
                event.tenant_id,event.application_id,event.error_code,event.error_message,
                event.occurred_at,event.source_principal_id,event.principal_id,
                event.operation,event.session_context,event.severity_hint,raw,
            ),
        )

    def enqueue_action(self,tenant_id:str,event_id:str,action_kind:str)->dict:
        return self._scalar(
            "SELECT incident_response.g11_enqueue_action(%s,%s,%s)",
            (tenant_id,event_id,action_kind),
        )

    def record_action_attempt(self,tenant_id:str,request_id:str,result_state:str,
                              provider_ref:str|None,failure_reason:str|None)->None:
        self._scalar(
            "SELECT incident_response.g11_record_action_attempt(%s,%s,%s,%s,%s)",
            (tenant_id,request_id,result_state,provider_ref,failure_reason),
        )

    def list_events(self,tenant_id:str)->list[dict]:
        return list(self._scalar("SELECT incident_response.g11_list_events(%s)",(tenant_id,)) or [])

    def get_event(self,tenant_id:str,event_id:str)->dict|None:
        return self._scalar("SELECT incident_response.g11_get_event(%s,%s)",(tenant_id,event_id))

    def next_pending_action(self,tenant_id:str)->dict|None:
        return self._scalar("SELECT incident_response.g11_next_pending_action(%s)",(tenant_id,))

    def claim_action(self,tenant_id:str,request_id:str,executor_id:str,claim_seconds:int)->dict:
        return self._scalar(
            "SELECT incident_response.g11_claim_action(%s,%s,%s,%s)",
            (tenant_id,request_id,executor_id,claim_seconds),
        )

    def complete_action(self,tenant_id:str,request_id:str,executor_id:str,
                        result_state:str,provider_ref:str|None,failure_class:str|None)->dict:
        return self._scalar(
            "SELECT incident_response.g11_complete_action(%s,%s,%s,%s,%s,%s)",
            (tenant_id,request_id,executor_id,result_state,provider_ref,failure_class),
        )
