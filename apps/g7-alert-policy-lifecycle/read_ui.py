from __future__ import annotations

from dataclasses import dataclass
from html import escape
from typing import Protocol


@dataclass(frozen=True)
class AuthContext:
    tenant_id: str
    subject_id: str
    scopes: frozenset[str]


class ReadPort(Protocol):
    def list_alerts(self, tenant_id: str, limit: int) -> list[dict]: ...
    def get_alert(self, tenant_id: str, alert_id: str) -> dict | None: ...


def _require_read(auth: AuthContext) -> None:
    if not auth.tenant_id or not auth.subject_id or "alerts:read" not in auth.scopes:
        raise PermissionError("alerts read scope required")


def list_api(port: ReadPort, auth: AuthContext, limit: int = 50) -> dict:
    _require_read(auth)
    bounded = max(1, min(int(limit), 100))
    return {"items": port.list_alerts(auth.tenant_id, bounded), "limit": bounded}


def detail_api(port: ReadPort, auth: AuthContext, alert_id: str) -> dict:
    _require_read(auth)
    item = port.get_alert(auth.tenant_id, alert_id)
    if item is None:
        raise KeyError(alert_id)
    return item


def render_list(port: ReadPort, auth: AuthContext) -> str:
    payload = list_api(port, auth)
    rows = []
    for item in payload["items"]:
        rows.append(
            "<tr>"
            f"<td>{escape(str(item['alert_id']))}</td>"
            f"<td>{escape(str(item['lifecycle_state']))}</td>"
            f"<td>{escape(str(item['source_kind']))}</td>"
            f"<td>{escape(str(item['source_subject_id']))}</td>"
            f"<td>{escape(str(item['policy_id']))}@{escape(str(item['policy_version']))}</td>"
            "</tr>"
        )
    return (
        "<!doctype html><html><body><main>"
        "<h1>Alerts</h1><table><thead><tr>"
        "<th>Alert</th><th>Lifecycle</th><th>Source</th><th>Subject</th><th>Policy</th>"
        "</tr></thead><tbody>" + "".join(rows) + "</tbody></table>"
        "</main></body></html>"
    )


def render_detail(port: ReadPort, auth: AuthContext, alert_id: str) -> str:
    item = detail_api(port, auth, alert_id)
    transitions = "".join(
        f"<li>{escape(str(row['to_lifecycle_state']))} @ {escape(str(row['occurred_at']))}</li>"
        for row in item.get("transitions", [])
    )
    return (
        "<!doctype html><html><body><main>"
        f"<h1>{escape(str(item['alert_id']))}</h1>"
        f"<p>Lifecycle: {escape(str(item['lifecycle_state']))}</p>"
        f"<p>Source: {escape(str(item['source_kind']))} / {escape(str(item['source_subject_id']))}</p>"
        f"<p>Policy: {escape(str(item['policy_id']))}@{escape(str(item['policy_version']))}</p>"
        f"<ol>{transitions}</ol>"
        "</main></body></html>"
    )
