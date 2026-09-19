from __future__ import annotations
from dataclasses import dataclass
from html import escape
from typing import Protocol


@dataclass(frozen=True)
class AuthContext:
    tenant_id:str
    principal_id:str
    scopes:frozenset[str]


class ReadPort(Protocol):
    def get_intent(self,tenant_id:str,intent_id:str)->dict: ...
    def list_alert_intents(self,tenant_id:str,alert_id:str)->list[dict]: ...


def _require(auth:AuthContext,scope:str)->None:
    if not auth.tenant_id or not auth.principal_id or scope not in auth.scopes:
        raise PermissionError(scope)


def intent_api(port:ReadPort,auth:AuthContext,intent_id:str)->dict:
    _require(auth,"notification:read")
    return port.get_intent(auth.tenant_id,intent_id)


def alert_intents_api(port:ReadPort,auth:AuthContext,alert_id:str)->dict:
    _require(auth,"notification:read")
    return {"items":port.list_alert_intents(auth.tenant_id,alert_id)}


def render_intent(port:ReadPort,auth:AuthContext,intent_id:str)->str:
    item=intent_api(port,auth,intent_id)
    projection=item.get("projection") or {}
    rows="".join(
        f"<li>{escape(str(x['attempt_number']))}: {escape(str(x['attempt_state']))}</li>"
        for x in item.get("attempts",[])
    )
    evidence="".join(
        f"<li>{escape(str(x['evidence_kind']))} @ {escape(str(x['observed_at']))}</li>"
        for x in item.get("provider_evidence",[])
    )
    native=projection.get("native_visibility_state","not_linked")
    return (
      "<!doctype html><html><body><main>"
      f"<h1>Notification {escape(intent_id)}</h1>"
      f"<p>Delivery: {escape(str(projection.get('delivery_state','unknown')))}</p>"
      f"<p>External read evidence: {escape(str(projection.get('external_read_observed',False)))}</p>"
      f"<p>Authoritative native visibility: {escape(str(native))}</p>"
      f"<p>Fallback action required: {escape(str(projection.get('fallback_action_required',False)))}</p>"
      f"<section><h2>Attempts</h2><ol>{rows}</ol></section>"
      f"<section><h2>Provider evidence</h2><ol>{evidence}</ol></section>"
      "</main></body></html>"
    )
