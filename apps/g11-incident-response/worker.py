from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


class ActionPort(Protocol):
    def next_pending_action(self,tenant_id:str)->dict|None: ...
    def claim_action(self,tenant_id:str,request_id:str,executor_id:str,claim_seconds:int)->dict: ...
    def complete_action(self,tenant_id:str,request_id:str,executor_id:str,
                        result_state:str,provider_ref:str|None,failure_class:str|None)->dict: ...


class TicketBridgeAdapter(Protocol):
    version:str
    def create_ticket(self,*,event:dict,request:dict)->dict: ...


class NotifyBridgeAdapter(Protocol):
    version:str
    def send_notification(self,*,event:dict,request:dict)->dict: ...


@dataclass
class IncidentResponseWorker:
    port:ActionPort
    ticket_adapter:TicketBridgeAdapter
    notify_adapter:NotifyBridgeAdapter|None
    executor_id:str
    claim_seconds:int=60

    def process_next(self,tenant_id:str)->dict:
        candidate=self.port.next_pending_action(tenant_id)
        if candidate is None: return {"state":"idle"}
        request_id=candidate["request_id"]
        action_kind=candidate.get("action_kind","open_ticket")
        claim=self.port.claim_action(tenant_id,request_id,self.executor_id,self.claim_seconds)
        if claim.get("state")!="dispatching": return claim
        try:
            if action_kind=="open_ticket":
                result=self.ticket_adapter.create_ticket(
                    event=candidate.get("event",{}),request=candidate,
                )
            elif action_kind=="notify" and self.notify_adapter:
                result=self.notify_adapter.send_notification(
                    event=candidate.get("event",{}),request=candidate,
                )
            else:
                result={"state":"skipped","failure_class":"no_adapter"}
        except Exception:
            return self.port.complete_action(
                tenant_id,request_id,self.executor_id,"unknown",None,"adapter_execution_unknown",
            )
        state=str(result.get("state","unknown"))
        if state not in {"linked","failed","skipped","unknown"}: state="unknown"
        return self.port.complete_action(
            tenant_id,request_id,self.executor_id,state,
            result.get("provider_ref"),result.get("failure_class"),
        )


class FixtureNeutralTicketAdapter:
    version="fixture-neutral-ticket@1"
    def __init__(self,state:str="linked")->None:
        self.state=state
        self.calls:list=[]
    def create_ticket(self,*,event:dict,request:dict)->dict:
        self.calls.append((dict(event),dict(request)))
        return {
            "state":self.state,
            "provider_ref":"fixture-ticket-1" if self.state=="linked" else None,
            "failure_class":None if self.state=="linked" else "fixture_failure",
        }
