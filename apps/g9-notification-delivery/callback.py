from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime,timezone
from hashlib import sha256
import hmac
import json
from typing import Protocol


class CallbackPort(Protocol):
    def record_provider_callback(self,**kwargs)->dict: ...


@dataclass(frozen=True)
class Route:
    provider_account_ref:str
    tenant_id:str
    secret:bytes


@dataclass
class WhatsAppCallbackBoundary:
    port:CallbackPort
    routes:dict[str,Route]
    replay_window_seconds:int=300
    max_body_bytes:int=16384

    def admit(
        self,*,provider_account_ref:str,callback_ref:str,provider_message_ref:str,
        evidence_kind:str,body:bytes,timestamp_epoch:int,signature_hex:str,
        provider_observed_at:datetime|None=None
    )->dict:
        route=self.routes.get(provider_account_ref)
        if route is None:
            raise PermissionError("trusted route missing")
        if len(body)>self.max_body_bytes:
            raise ValueError("callback body too large")

        now=int(datetime.now(timezone.utc).timestamp())
        if abs(now-int(timestamp_epoch))>self.replay_window_seconds:
            raise PermissionError("callback replay window exceeded")

        signed=str(timestamp_epoch).encode()+b"." + body
        expected=hmac.new(route.secret,signed,sha256).hexdigest()
        if not hmac.compare_digest(expected,signature_hex):
            raise PermissionError("callback signature invalid")

        payload=json.loads(body)
        if not isinstance(payload,dict):
            raise ValueError("callback payload must be object")
        if evidence_kind not in {
            "provider_accepted","delivered","external_read_observed","failed","unknown"
        }:
            raise ValueError("callback evidence kind invalid")

        payload_hash=sha256(body).hexdigest()
        return self.port.record_provider_callback(
            tenant_id=route.tenant_id,
            callback_ref=callback_ref,
            provider_message_ref=provider_message_ref,
            payload_hash=payload_hash,
            evidence_kind=evidence_kind,
            authentication_evidence={
                "verified":True,
                "trusted_route_ref":provider_account_ref,
                "timestamp_epoch":timestamp_epoch,
                "signature_profile":"hmac-sha256@1",
            },
            bounded_payload=payload,
            provider_observed_at=provider_observed_at,
        )
