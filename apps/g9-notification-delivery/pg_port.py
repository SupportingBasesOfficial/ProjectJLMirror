from __future__ import annotations

import json
from typing import Any

from domain import AuthoritySnapshot


def _decode(value:Any)->Any:
    if isinstance(value,str):
        return json.loads(value)
    return value


class PgNotificationGateway:
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
            "tenant_id":a.tenant_id,
            "principal_id":a.principal_id,
            "current":a.current,
            "action":a.action,
            "policy_revision":a.policy_revision,
        },separators=(",",":"))

    def create_intent(self,**kwargs)->dict:
        a=kwargs["authority"]
        return self._scalar(
            "SELECT notification.g9_create_intent(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb)",
            (
                kwargs["tenant_id"],kwargs["alert_id"],kwargs["recipient_principal_id"],
                kwargs["destination_ref"],kwargs["channel_class"],kwargs["reason"],
                kwargs["payload_ref"],kwargs["payload_hash"],kwargs["visibility_requirement_id"],
                kwargs["actor_principal_id"],kwargs["logical_action_id"],self._authority(a),
            ),
        )

    def get_intent(self,tenant_id:str,intent_id:str)->dict:
        return self._scalar(
            "SELECT notification.g9_get_intent(%s,%s)",
            (tenant_id,intent_id),
        )

    def list_alert_intents(self,tenant_id:str,alert_id:str)->list[dict]:
        return list(self._scalar(
            "SELECT notification.g9_list_alert_intents(%s,%s)",
            (tenant_id,alert_id),
        ) or [])

    def claim_dispatch(
        self,*,tenant_id:str,outbox_id:str,executor_id:str,claim_seconds:int,
        adapter_version:str,request_evidence:dict
    )->dict:
        return self._scalar(
            "SELECT notification.g9_claim_dispatch(%s,%s,%s,%s,%s,%s::jsonb)",
            (
                tenant_id,outbox_id,executor_id,claim_seconds,adapter_version,
                json.dumps(request_evidence,separators=(",",":")),
            ),
        )

    def complete_dispatch(
        self,*,tenant_id:str,outbox_id:str,executor_id:str,attempt_state:str,
        provider_message_ref:str|None,failure_class:str|None
    )->dict:
        return self._scalar(
            "SELECT notification.g9_complete_dispatch(%s,%s,%s,%s,%s,%s)",
            (tenant_id,outbox_id,executor_id,attempt_state,provider_message_ref,failure_class),
        )

    def record_provider_callback(
        self,*,tenant_id:str,callback_ref:str,provider_message_ref:str,payload_hash:str,
        evidence_kind:str,authentication_evidence:dict,bounded_payload:dict,
        provider_observed_at:Any
    )->dict:
        return self._scalar(
            "SELECT notification.g9_record_provider_callback(%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s)",
            (
                tenant_id,callback_ref,provider_message_ref,payload_hash,evidence_kind,
                json.dumps(authentication_evidence,separators=(",",":")),
                json.dumps(bounded_payload,separators=(",",":")),
                provider_observed_at,
            ),
        )
