from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


class DispatchPort(Protocol):
    def next_dispatch_candidate(self,tenant_id:str)->dict|None: ...
    def claim_dispatch(self,**kwargs)->dict: ...
    def complete_dispatch(self,**kwargs)->dict: ...
    def schedule_retry(self,tenant_id:str,intent_id:str)->dict: ...


class WhatsAppAdapter(Protocol):
    version:str
    def send(self,*,intent:dict)->dict: ...


@dataclass
class NotificationDispatcher:
    port:DispatchPort
    adapter:WhatsAppAdapter
    executor_id:str
    claim_seconds:int=60

    def dispatch_next(self,*,tenant_id:str)->dict:
        candidate=self.port.next_dispatch_candidate(tenant_id)
        if candidate is None:
            return {"state":"idle"}
        return self.dispatch(
            tenant_id=tenant_id,
            outbox_id=candidate["dispatch_outbox_id"],
            intent=candidate,
        )

    def reconcile_retry(self,*,tenant_id:str,intent_id:str)->dict:
        return self.port.schedule_retry(tenant_id,intent_id)

    def dispatch(self,*,tenant_id:str,outbox_id:str,intent:dict)->dict:
        claimed=self.port.claim_dispatch(
            tenant_id=tenant_id,outbox_id=outbox_id,executor_id=self.executor_id,
            claim_seconds=self.claim_seconds,adapter_version=self.adapter.version,
            request_evidence={
                "channel":"whatsapp_business@1",
                "notification_intent_id":intent["notification_intent_id"],
                "payload_hash":intent["payload_hash"],
            },
        )
        if claimed.get("state")!="processing":
            return claimed

        try:
            result=self.adapter.send(intent=intent)
        except Exception as exc:
            return self.port.complete_dispatch(
                tenant_id=tenant_id,outbox_id=outbox_id,executor_id=self.executor_id,
                attempt_state="unknown",provider_message_ref=None,
                failure_class="adapter_execution_unknown",
            )

        state=str(result.get("state","unknown"))
        if state not in {"sent","provider_accepted","delivered","failed","unknown"}:
            state="unknown"
        provider_ref=result.get("provider_message_ref")
        failure=result.get("failure_class")
        return self.port.complete_dispatch(
            tenant_id=tenant_id,outbox_id=outbox_id,executor_id=self.executor_id,
            attempt_state=state,provider_message_ref=provider_ref,failure_class=failure,
        )


class FixtureWhatsAppAdapter:
    version="fixture-whatsapp@1"

    def __init__(self,state:str="sent")->None:
        self.state=state
        self.calls:list[dict]=[]

    def send(self,*,intent:dict)->dict:
        self.calls.append(dict(intent))
        return {
            "state":self.state,
            "provider_message_ref":"wa-provider-message-1",
            "failure_class":None if self.state not in {"failed","unknown"} else "fixture_failure",
        }
