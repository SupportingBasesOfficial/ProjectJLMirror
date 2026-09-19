from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


class SyncPort(Protocol):
    def next_sync_candidate(self,tenant_id:str)->dict|None: ...
    def claim_sync(self,tenant_id:str,outbox_id:str,executor_id:str,claim_seconds:int)->dict: ...
    def complete_sync(self,tenant_id:str,outbox_id:str,executor_id:str,result_state:str,
                      provider_ticket_ref:str|None,provider_evidence:dict,failure_class:str|None)->dict: ...
    def reconcile_sync(self,tenant_id:str,outbox_id:str)->dict: ...


class ITSMAdapter(Protocol):
    version:str
    def create_or_link(self,*,incident:dict,sync_identity:str)->dict: ...


@dataclass
class ITSMSyncWorker:
    port:SyncPort
    adapter:ITSMAdapter
    executor_id:str
    claim_seconds:int=60

    def sync_next(self,tenant_id:str)->dict:
        candidate=self.port.next_sync_candidate(tenant_id)
        if candidate is None:
            return {"state":"idle"}
        outbox_id=candidate["sync_outbox_id"]
        claim=self.port.claim_sync(tenant_id,outbox_id,self.executor_id,self.claim_seconds)
        if claim.get("state")!="dispatching":
            return claim
        try:
            result=self.adapter.create_or_link(
                incident=candidate,
                sync_identity=candidate["sync_identity"],
            )
        except Exception:
            return self.port.complete_sync(
                tenant_id,outbox_id,self.executor_id,"unknown",None,
                {"adapter_version":self.adapter.version},"adapter_execution_unknown"
            )
        state=str(result.get("state","unknown"))
        if state not in {"linked","failed","unknown"}:
            state="unknown"
        return self.port.complete_sync(
            tenant_id,outbox_id,self.executor_id,state,
            result.get("provider_ticket_ref"),
            {"adapter_version":self.adapter.version,"provider_status":result.get("provider_status")},
            result.get("failure_class"),
        )


class FixtureNeutralAdapter:
    version="fixture-neutral@1"
    def __init__(self,state:str="linked")->None:
        self.state=state
        self.calls=[]
    def create_or_link(self,*,incident:dict,sync_identity:str)->dict:
        self.calls.append((dict(incident),sync_identity))
        return {
            "state":self.state,
            "provider_ticket_ref":"external-ticket-1" if self.state=="linked" else None,
            "provider_status":"created" if self.state=="linked" else "unknown",
            "failure_class":None if self.state=="linked" else "fixture_failure",
        }
