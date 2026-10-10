from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from domain import (
    ApplicationErrorEvent,IncidentResponsePolicy,
    validate_event,evaluate_policy,minute_bucket,
    SEVERITIES,
)


class IncidentResponsePort(Protocol):
    def get_policy(self,tenant_id:str)->dict|None: ...
    def upsert_policy(self,tenant_id:str,policy:dict,actor_principal_id:str)->dict: ...
    def claim_dedupe(self,tenant_id:str,application_id:str,error_code:str,bucket_ts:str)->bool: ...
    def store_event(self,event:ApplicationErrorEvent)->dict: ...
    def enqueue_action(self,tenant_id:str,event_id:str,action_kind:str)->dict: ...
    def record_action_attempt(self,tenant_id:str,request_id:str,result_state:str,
                              provider_ref:str|None,failure_reason:str|None)->None: ...
    def list_events(self,tenant_id:str)->list[dict]: ...
    def get_event(self,tenant_id:str,event_id:str)->dict|None: ...
    def next_pending_action(self,tenant_id:str)->dict|None: ...
    def claim_action(self,tenant_id:str,request_id:str,executor_id:str,claim_seconds:int)->dict: ...
    def complete_action(self,tenant_id:str,request_id:str,executor_id:str,
                        result_state:str,provider_ref:str|None,failure_class:str|None)->dict: ...


def _policy_from_dict(tenant_id:str,raw:dict)->IncidentResponsePolicy:
    threshold=raw.get("severity_threshold","HIGH")
    if threshold not in SEVERITIES: raise ValueError("severity_threshold invalid")
    return IncidentResponsePolicy(
        tenant_id=tenant_id,
        severity_threshold=threshold,
        auto_open_ticket=bool(raw.get("auto_open_ticket",False)),
        manual_override_only=bool(raw.get("manual_override_only",False)),
        notify_channels=tuple(raw.get("notify_channels",[])),
        automation_triggers=tuple(raw.get("automation_triggers",[])),
    )


def _policy_to_dict(p:IncidentResponsePolicy)->dict:
    return {
        "tenant_id":p.tenant_id,
        "severity_threshold":p.severity_threshold,
        "auto_open_ticket":p.auto_open_ticket,
        "manual_override_only":p.manual_override_only,
        "notify_channels":list(p.notify_channels),
        "automation_triggers":list(p.automation_triggers),
    }


@dataclass
class IncidentResponseService:
    port:IncidentResponsePort

    def get_policy(self,tenant_id:str)->dict:
        raw=self.port.get_policy(tenant_id)
        if raw is None:
            return _policy_to_dict(IncidentResponsePolicy(tenant_id=tenant_id))
        return raw

    def upsert_policy(self,tenant_id:str,raw:dict,actor_principal_id:str)->dict:
        if not actor_principal_id: raise ValueError("actor_principal_id required")
        policy=_policy_from_dict(tenant_id,raw)
        return self.port.upsert_policy(tenant_id,_policy_to_dict(policy),actor_principal_id)

    def ingest_event(self,event:ApplicationErrorEvent)->dict:
        validate_event(event)
        bucket=minute_bucket(event.occurred_at)
        is_first=self.port.claim_dedupe(event.tenant_id,event.application_id,event.error_code,bucket)
        if not is_first:
            return {"status":"deduplicated"}
        stored=self.port.store_event(event)
        event_id=stored["event_id"]
        raw_policy=self.port.get_policy(event.tenant_id)
        policy=(
            _policy_from_dict(event.tenant_id,raw_policy)
            if raw_policy
            else IncidentResponsePolicy(tenant_id=event.tenant_id)
        )
        actions=evaluate_policy(event,policy)
        for action in actions:
            self.port.enqueue_action(event.tenant_id,event_id,action)
        return {"status":"accepted","event_id":event_id,"actions_enqueued":actions}

    def list_events(self,tenant_id:str)->list[dict]:
        return self.port.list_events(tenant_id)

    def get_event(self,tenant_id:str,event_id:str)->dict:
        result=self.port.get_event(tenant_id,event_id)
        if result is None: raise KeyError(event_id)
        return result
