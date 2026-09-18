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
    def alert_human_operations(self,tenant_id:str,alert_id:str)->dict: ...
    def resource_responsibilities(self,tenant_id:str,resource_id:str)->list[dict]: ...


def _require(auth:AuthContext,scope:str)->None:
    if not auth.tenant_id or not auth.principal_id or scope not in auth.scopes:
        raise PermissionError(scope)


def alert_api(port:ReadPort,auth:AuthContext,alert_id:str)->dict:
    _require(auth,"human-operations:read")
    return port.alert_human_operations(auth.tenant_id,alert_id)


def resource_api(port:ReadPort,auth:AuthContext,resource_id:str)->dict:
    _require(auth,"human-operations:read")
    return {"items":port.resource_responsibilities(auth.tenant_id,resource_id)}


def render_alert(port:ReadPort,auth:AuthContext,alert_id:str)->str:
    item=alert_api(port,auth,alert_id)
    action=item.get("current_action") or {}
    owner=action.get("owner_principal_id") or "—"
    kind=action.get("action_kind") or "no_human_action_required"
    ack_rows="".join(
        f"<li>{escape(str(row['principal_id']))} @ {escape(str(row['acknowledged_at']))}</li>"
        for row in item.get("acknowledgements",[])
    )
    visibility_rows="".join(
        f"<li>{escape(str(row['viewer_side']))}: {escape(str(row['visibility_state']))}</li>"
        for row in item.get("visibility",[])
    )
    timeline="".join(
        f"<li>{escape(str(row['kind']))} @ {escape(str(row['occurred_at']))}</li>"
        for row in item.get("timeline",[])
    )
    return (
        "<!doctype html><html><body><main>"
        f"<h1>Human operations for {escape(alert_id)}</h1>"
        f"<section><h2>Current action</h2><p>{escape(kind)} — {escape(owner)}</p></section>"
        f"<section><h2>Acknowledgements</h2><ol>{ack_rows}</ol></section>"
        f"<section><h2>Visibility</h2><ol>{visibility_rows}</ol></section>"
        f"<section><h2>Timeline</h2><ol>{timeline}</ol></section>"
        "</main></body></html>"
    )
