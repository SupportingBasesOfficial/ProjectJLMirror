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
    def get_incident(self,tenant_id:str,incident_id:str)->dict: ...
    def list_alert_incidents(self,tenant_id:str,alert_id:str)->list[dict]: ...


def _require(auth:AuthContext,scope:str)->None:
    if not auth.tenant_id or not auth.principal_id or scope not in auth.scopes:
        raise PermissionError(scope)


def incident_api(port:ReadPort,auth:AuthContext,incident_id:str)->dict:
    _require(auth,"itsm:read")
    return port.get_incident(auth.tenant_id,incident_id)


def alert_incidents_api(port:ReadPort,auth:AuthContext,alert_id:str)->dict:
    _require(auth,"itsm:read")
    return {"items":port.list_alert_incidents(auth.tenant_id,alert_id)}


def render_incident(port:ReadPort,auth:AuthContext,incident_id:str)->str:
    item=incident_api(port,auth,incident_id)
    assignments="".join(
        f"<li>{escape(str(x['assignee_principal_id']))}</li>"
        for x in item.get("assignments",[])
    )
    comments="".join(
        f"<li>{escape(str(x['body']))}</li>"
        for x in item.get("comments",[])
    )
    sync=item.get("provider_sync") or {}
    return (
      "<!doctype html><html><body><main>"
      f"<h1>Incident {escape(incident_id)}</h1>"
      f"<p>State: {escape(str(item.get('lifecycle_state')))}</p>"
      f"<p>Originating Alert: {escape(str(item.get('alert_id')))}</p>"
      f"<p>Provider sync: {escape(str(sync.get('sync_state','pending')))}</p>"
      f"<section><h2>Assignment history</h2><ol>{assignments}</ol></section>"
      f"<section><h2>Comments</h2><ol>{comments}</ol></section>"
      "</main></body></html>"
    )
