"""Zabbix 7.x HTTP adapter — concrete implementations of all monitoring Protocols.

Speaks JSON-RPC 2.0 to the Zabbix API (``/api_jsonrpc.php``), authenticating via
a pre-issued API token passed as ``Authorization: Bearer <token>``.

Error mapping:
  - Network / connection failure  → ProviderUnavailableError
  - HTTP 401/403                  → ProviderAuthenticationError
  - JSON-RPC -32000 series (auth) → ProviderAuthenticationError
  - Malformed JSON / protocol err → ProviderProtocolError

Retries: exponential backoff (1 s, 2 s, stop) on transient network failures
and HTTP 5xx.  Auth and protocol errors are surfaced immediately without retry.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from decimal import Decimal, InvalidOperation
from typing import Any, Sequence

from jlmirror_monitoring.host_inventory import (
    ZabbixHostEvidence,
    ZabbixHostInterfaceEvidence,
    ZabbixHostSnapshot,
    ZabbixInventoryEvidence,
    ZabbixNamedRefEvidence,
    ZabbixTagEvidence,
)
from jlmirror_monitoring.metric_current_state import ZabbixCurrentValueEvidence
from jlmirror_monitoring.metric_definitions import (
    ZabbixItemEvidence,
    ZabbixItemOperationalState,
    ZabbixItemSnapshot,
    ZabbixNativeValueType,
)
from jlmirror_monitoring.metric_history import ZabbixHistoryEvidence
from jlmirror_monitoring.problem_state import (
    ProviderTag,
    ZabbixProblemEvidence,
    ZabbixRecoveryEvidence,
)
from jlmirror_monitoring.validation_worker import (
    AdmittedProviderEndpoint,
    ProviderAuthenticationError,
    ProviderProtocolError,
    ProviderUnavailableError,
    ResolvedZabbixCredential,
    ZabbixHostGroup,
)

_JSONRPC_VERSION = "2.0"
_REQUEST_TIMEOUT = 30  # seconds per attempt
_MAX_ATTEMPTS = 3
_BACKOFF_SECONDS = (1.0, 2.0)

_INTERFACE_TYPE_MAP = {
    "1": "agent",
    "2": "snmp",
    "3": "ipmi",
    "4": "jmx",
}

_NATIVE_VALUE_TYPE_MAP = {
    "0": ZabbixNativeValueType.FLOAT,
    "1": ZabbixNativeValueType.CHARACTER,
    "2": ZabbixNativeValueType.LOG,
    "3": ZabbixNativeValueType.UNSIGNED,
    "4": ZabbixNativeValueType.TEXT,
}

_SEVERITY_VALID = frozenset({0, 1, 2, 3, 4, 5})

_INVENTORY_FIELDS = [
    "type", "type_full", "os", "os_full", "vendor", "model",
    "serialno_a", "serialno_b", "asset_tag", "hardware", "software", "location",
]


def _str_or_none(value: Any, max_len: int = 0) -> str | None:
    if value is None or value == "":
        return None
    s = str(value)
    if max_len and len(s) > max_len:
        return s[:max_len]
    return s


def _bool_field(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value) == "1"


class ZabbixAdapter:
    """Implements ZabbixHostGroupReader, ZabbixHostReader, ZabbixItemReader,
    ZabbixCurrentValueReader, ZabbixProblemReader and ZabbixHistoryReader."""

    def _call(
        self,
        api_url: str,
        auth_token: str,
        method: str,
        params: dict[str, Any],
    ) -> Any:
        body = json.dumps({
            "jsonrpc": _JSONRPC_VERSION,
            "id": 1,
            "method": method,
            "params": params,
        }).encode("utf-8")
        req = urllib.request.Request(
            api_url,
            data=body,
            headers={
                "Content-Type": "application/json-rpc",
                "Authorization": f"Bearer {auth_token}",
            },
            method="POST",
        )
        for attempt in range(_MAX_ATTEMPTS):
            try:
                with urllib.request.urlopen(req, timeout=_REQUEST_TIMEOUT) as resp:
                    raw = resp.read()
                    try:
                        data = json.loads(raw)
                    except json.JSONDecodeError as exc:
                        raise ProviderProtocolError("Zabbix returned non-JSON body") from exc
                    if "error" in data:
                        err = data["error"]
                        code = err.get("code", 0)
                        # -32602 = invalid params (often auth); -32500 application; -32602 also used for auth
                        if code in (-32602, -32500) and "auth" in str(err).lower():
                            raise ProviderAuthenticationError(f"Zabbix auth error: {err}")
                        raise ProviderProtocolError(f"Zabbix API error: {err}")
                    return data.get("result")
            except ProviderAuthenticationError:
                raise
            except ProviderProtocolError:
                raise
            except urllib.error.HTTPError as exc:
                if exc.code in (401, 403):
                    raise ProviderAuthenticationError(f"Zabbix HTTP {exc.code}") from exc
                if exc.code >= 500 and attempt < _MAX_ATTEMPTS - 1:
                    time.sleep(_BACKOFF_SECONDS[attempt])
                    continue
                raise ProviderProtocolError(f"Zabbix HTTP {exc.code}") from exc
            except urllib.error.URLError as exc:
                if attempt < _MAX_ATTEMPTS - 1:
                    time.sleep(_BACKOFF_SECONDS[attempt])
                    continue
                raise ProviderUnavailableError(f"Zabbix unreachable: {exc.reason}") from exc
            except OSError as exc:
                if attempt < _MAX_ATTEMPTS - 1:
                    time.sleep(_BACKOFF_SECONDS[attempt])
                    continue
                raise ProviderUnavailableError(f"Zabbix connection failed: {exc}") from exc
        raise ProviderUnavailableError("Zabbix: max retries exceeded")

    # ------------------------------------------------------------------
    # ZabbixHostGroupReader / shared by ZabbixHostReader & ZabbixItemReader
    # ------------------------------------------------------------------

    def hostgroup_get(
        self,
        endpoint: AdmittedProviderEndpoint,
        credential: ResolvedZabbixCredential,
        host_group_refs: Sequence[str],
    ) -> Sequence[ZabbixHostGroup]:
        params: dict[str, Any] = {"output": ["groupid", "name"]}
        if host_group_refs:
            params["groupids"] = list(host_group_refs)
        result = self._call(endpoint.api_url, credential.api_token, "hostgroup.get", params)
        if not isinstance(result, list):
            raise ProviderProtocolError("hostgroup.get did not return a list")
        groups: list[ZabbixHostGroup] = []
        for row in result:
            gid = str(row.get("groupid", ""))
            if not gid:
                raise ProviderProtocolError("hostgroup.get returned entry without groupid")
            groups.append(ZabbixHostGroup(groupid=gid, name=_str_or_none(row.get("name")) or None))
        return groups

    # ------------------------------------------------------------------
    # ZabbixHostReader
    # ------------------------------------------------------------------

    def host_get(
        self,
        endpoint: AdmittedProviderEndpoint,
        credential: ResolvedZabbixCredential,
        host_group_refs: Sequence[str],
        *,
        max_hosts: int,
    ) -> ZabbixHostSnapshot:
        result = self._call(
            endpoint.api_url,
            credential.api_token,
            "host.get",
            {
                "output": ["hostid", "host", "name"],
                "groupids": list(host_group_refs),
                "limit": max_hosts + 1,
                "selectInterfaces": ["interfaceid", "type", "main", "useip", "ip", "dns", "port"],
                "selectHostGroups": ["groupid", "name"],
                "selectParentTemplates": ["templateid", "name"],
                "selectTags": ["tag", "value"],
                "selectInventory": _INVENTORY_FIELDS,
            },
        )
        if not isinstance(result, list):
            raise ProviderProtocolError("host.get did not return a list")
        complete = len(result) <= max_hosts
        rows = result[:max_hosts]
        hosts: list[ZabbixHostEvidence] = []
        for row in rows:
            hosts.append(_parse_host(row))
        return ZabbixHostSnapshot(hosts=tuple(hosts), complete=complete)

    # ------------------------------------------------------------------
    # ZabbixItemReader
    # ------------------------------------------------------------------

    def item_get(
        self,
        endpoint: AdmittedProviderEndpoint,
        credential: ResolvedZabbixCredential,
        host_group_refs: Sequence[str],
        *,
        max_items: int,
    ) -> ZabbixItemSnapshot:
        result = self._call(
            endpoint.api_url,
            credential.api_token,
            "item.get",
            {
                "output": ["itemid", "hostid", "name", "key_", "units", "value_type", "state", "status"],
                "groupids": list(host_group_refs),
                "limit": max_items + 1,
            },
        )
        if not isinstance(result, list):
            raise ProviderProtocolError("item.get did not return a list")
        complete = len(result) <= max_items
        rows = result[:max_items]
        items: list[ZabbixItemEvidence] = []
        for row in rows:
            items.append(_parse_item(row))
        return ZabbixItemSnapshot(items=tuple(items), complete=complete)

    # ------------------------------------------------------------------
    # ZabbixCurrentValueReader
    # ------------------------------------------------------------------

    def read_current_values(
        self,
        endpoint: AdmittedProviderEndpoint,
        credential: ResolvedZabbixCredential,
        itemids: Sequence[str],
        *,
        max_items: int,
    ) -> Sequence[ZabbixCurrentValueEvidence]:
        if not itemids:
            return []
        result = self._call(
            endpoint.api_url,
            credential.api_token,
            "item.get",
            {
                "output": ["itemid", "lastvalue", "lastclock", "lastns"],
                "itemids": list(itemids),
                "limit": max_items,
            },
        )
        if not isinstance(result, list):
            raise ProviderProtocolError("item.get (current) did not return a list")
        observations: list[ZabbixCurrentValueEvidence] = []
        for row in result:
            iid = str(row.get("itemid", ""))
            raw = str(row.get("lastvalue", ""))
            lastclock_raw = row.get("lastclock", 0)
            lastns_raw = row.get("lastns", 0)
            try:
                lastclock = int(lastclock_raw)
                lastns = int(lastns_raw)
            except (TypeError, ValueError) as exc:
                raise ProviderProtocolError("item.get returned non-integer clock") from exc
            if lastclock <= 0:
                continue  # item has never been polled; skip silently
            observations.append(ZabbixCurrentValueEvidence(
                itemid=iid,
                raw_value=raw,
                lastclock=lastclock,
                lastns=lastns,
            ))
        return observations

    # ------------------------------------------------------------------
    # ZabbixProblemReader
    # ------------------------------------------------------------------

    def read_active_problems(
        self,
        endpoint: AdmittedProviderEndpoint,
        credential: ResolvedZabbixCredential,
        *,
        max_rows: int,
    ) -> tuple[Sequence[ZabbixProblemEvidence], bool]:
        result = self._call(
            endpoint.api_url,
            credential.api_token,
            "problem.get",
            {
                "output": ["eventid", "objectid", "clock", "name", "severity", "acknowledged"],
                "selectTags": ["tag", "value"],
                "suppressed": False,
                "limit": max_rows + 1,
            },
        )
        if not isinstance(result, list):
            raise ProviderProtocolError("problem.get did not return a list")
        complete = len(result) <= max_rows
        rows = result[:max_rows]
        problems: list[ZabbixProblemEvidence] = []
        for row in rows:
            problems.append(_parse_problem(row))
        return problems, complete

    def read_recovery_events(
        self,
        endpoint: AdmittedProviderEndpoint,
        credential: ResolvedZabbixCredential,
        problem_eventids: Sequence[str],
        *,
        max_rows: int,
    ) -> Sequence[ZabbixRecoveryEvidence]:
        if not problem_eventids:
            return []
        # Step 1: get the r_eventid for each problem eventid.
        problem_result = self._call(
            endpoint.api_url,
            credential.api_token,
            "problem.get",
            {
                "output": ["eventid", "r_eventid"],
                "eventids": list(problem_eventids),
                "recent": True,
            },
        )
        if not isinstance(problem_result, list):
            raise ProviderProtocolError("problem.get (recovery) did not return a list")
        # Collect pairs where a recovery event exists.
        pending: dict[str, str] = {}  # r_eventid → problem_eventid
        for row in problem_result:
            r_eid = str(row.get("r_eventid", "0"))
            if r_eid and r_eid != "0":
                pending[r_eid] = str(row["eventid"])
        if not pending:
            return []
        # Step 2: fetch recovery event clocks.
        event_result = self._call(
            endpoint.api_url,
            credential.api_token,
            "event.get",
            {
                "output": ["eventid", "clock"],
                "eventids": list(pending.keys()),
                "limit": max_rows,
            },
        )
        if not isinstance(event_result, list):
            raise ProviderProtocolError("event.get did not return a list")
        recoveries: list[ZabbixRecoveryEvidence] = []
        for row in event_result:
            r_eid = str(row.get("eventid", ""))
            problem_eid = pending.get(r_eid)
            if not problem_eid:
                continue
            try:
                clock = int(row.get("clock", 0))
            except (TypeError, ValueError) as exc:
                raise ProviderProtocolError("event.get returned non-integer clock") from exc
            if clock <= 0:
                raise ProviderProtocolError("event.get returned non-positive recovery clock")
            recoveries.append(ZabbixRecoveryEvidence(
                problem_eventid=problem_eid,
                recovery_eventid=r_eid,
                clock=clock,
            ))
        return recoveries

    # ------------------------------------------------------------------
    # ZabbixHistoryReader
    # ------------------------------------------------------------------

    def read_history(
        self,
        endpoint: AdmittedProviderEndpoint,
        credential: ResolvedZabbixCredential,
        *,
        history_value_type: int,
        itemids: Sequence[str],
        time_from: int,
        time_till: int,
        max_rows: int,
    ) -> Sequence[ZabbixHistoryEvidence]:
        if not itemids:
            return []
        result = self._call(
            endpoint.api_url,
            credential.api_token,
            "history.get",
            {
                "output": ["itemid", "clock", "ns", "value"],
                "history": history_value_type,
                "itemids": list(itemids),
                "time_from": time_from,
                "time_till": time_till,
                "limit": max_rows,
                "sortfield": "clock",
                "sortorder": "ASC",
            },
        )
        if not isinstance(result, list):
            raise ProviderProtocolError("history.get did not return a list")
        entries: list[ZabbixHistoryEvidence] = []
        for row in result:
            iid = str(row.get("itemid", ""))
            raw_val = str(row.get("value", ""))
            try:
                clock = int(row.get("clock", 0))
                ns = int(row.get("ns", 0))
            except (TypeError, ValueError) as exc:
                raise ProviderProtocolError("history.get returned non-integer clock") from exc
            entries.append(ZabbixHistoryEvidence(itemid=iid, clock=clock, ns=ns, raw_value=raw_val))
        return entries


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------

def _parse_host(row: dict[str, Any]) -> ZabbixHostEvidence:
    hostid = str(row.get("hostid", ""))
    technical_name = str(row.get("host", "") or "")
    display_name = str(row.get("name", "") or technical_name)

    raw_inv = row.get("inventory") or {}
    if isinstance(raw_inv, list):
        raw_inv = {}

    def _inv_field(key: str, max_len: int) -> str | None:
        v = raw_inv.get(key, "")
        return _str_or_none(v, max_len) if v else None

    inventory = ZabbixInventoryEvidence(
        device_type=_inv_field("type", 512),
        device_type_full=_inv_field("type_full", 2048),
        os=_inv_field("os", 512),
        os_full=_inv_field("os_full", 2048),
        vendor=_inv_field("vendor", 512),
        model=_inv_field("model", 512),
        serial_primary=_inv_field("serialno_a", 512),
        serial_secondary=_inv_field("serialno_b", 512),
        asset_tag=_inv_field("asset_tag", 512),
        hardware=_inv_field("hardware", 2048),
        software=_inv_field("software", 2048),
        location=_inv_field("location", 1024),
    )

    raw_interfaces = row.get("interfaces") or []
    interfaces: list[ZabbixHostInterfaceEvidence] = []
    for iface in raw_interfaces:
        itype_raw = str(iface.get("type", "1"))
        itype = _INTERFACE_TYPE_MAP.get(itype_raw, "unknown")
        interfaces.append(ZabbixHostInterfaceEvidence(
            interfaceid=str(iface.get("interfaceid", "")),
            interface_type=itype,
            main=_bool_field(iface.get("main", "0")),
            use_ip=_bool_field(iface.get("useip", "0")),
            ip=_str_or_none(iface.get("ip"), 255),
            dns=_str_or_none(iface.get("dns"), 255),
            port=_str_or_none(iface.get("port"), 32),
        ))

    raw_groups = row.get("hostgroups") or row.get("groups") or []
    groups: list[ZabbixNamedRefEvidence] = []
    for g in raw_groups:
        groups.append(ZabbixNamedRefEvidence(
            ref=str(g.get("groupid", "")),
            name=_str_or_none(g.get("name"), 512),
        ))

    raw_templates = row.get("parentTemplates") or []
    templates: list[ZabbixNamedRefEvidence] = []
    for t in raw_templates:
        templates.append(ZabbixNamedRefEvidence(
            ref=str(t.get("templateid", "")),
            name=_str_or_none(t.get("name"), 512),
        ))

    raw_tags = row.get("tags") or []
    tags: list[ZabbixTagEvidence] = []
    for tag_row in raw_tags:
        key = str(tag_row.get("tag", ""))
        val = str(tag_row.get("value", ""))
        if key:
            tags.append(ZabbixTagEvidence(tag=key, value=val))

    return ZabbixHostEvidence(
        hostid=hostid,
        technical_name=technical_name or hostid,
        display_name=display_name or technical_name or hostid,
        inventory=inventory,
        interfaces=tuple(interfaces),
        groups=tuple(groups),
        templates=tuple(templates),
        tags=tuple(tags),
    )


def _parse_item(row: dict[str, Any]) -> ZabbixItemEvidence:
    itemid = str(row.get("itemid", ""))
    hostid = str(row.get("hostid", ""))
    name = str(row.get("name", "") or "")
    key = str(row.get("key_", "") or "")
    unit = str(row.get("units", "") or "")
    value_type_raw = str(row.get("value_type", "0"))
    native_type = _NATIVE_VALUE_TYPE_MAP.get(value_type_raw)
    if native_type is None:
        # value_type=5 is binary (Zabbix 7.x); treat as text for now
        native_type = ZabbixNativeValueType.TEXT

    status_raw = str(row.get("status", "0"))
    state_raw = str(row.get("state", "0"))
    if status_raw == "1":
        op_state = ZabbixItemOperationalState.DISABLED
    elif state_raw == "1":
        op_state = ZabbixItemOperationalState.UNSUPPORTED
    else:
        op_state = ZabbixItemOperationalState.ENABLED

    return ZabbixItemEvidence(
        itemid=itemid,
        hostid=hostid,
        name=name,
        key=key,
        unit=unit,
        native_value_type=native_type,
        operational_state=op_state,
    )


def _parse_problem(row: dict[str, Any]) -> ZabbixProblemEvidence:
    eventid = str(row.get("eventid", ""))
    objectid = str(row.get("objectid", ""))
    try:
        clock = int(row.get("clock", 0))
    except (TypeError, ValueError) as exc:
        raise ProviderProtocolError("problem.get returned non-integer clock") from exc
    name = str(row.get("name", "") or "")
    try:
        severity = int(row.get("severity", 0))
    except (TypeError, ValueError) as exc:
        raise ProviderProtocolError("problem.get returned non-integer severity") from exc
    if severity not in _SEVERITY_VALID:
        raise ProviderProtocolError(f"problem.get returned unsupported severity: {severity}")
    acknowledged = _bool_field(row.get("acknowledged", "0"))
    raw_tags = row.get("tags") or []
    tags: list[ProviderTag] = []
    for tag_row in raw_tags:
        key = str(tag_row.get("tag", ""))
        val = str(tag_row.get("value", ""))
        if key:
            tags.append(ProviderTag(key=key, value=val))
    return ZabbixProblemEvidence(
        eventid=eventid,
        objectid=objectid,
        clock=clock,
        name=name,
        severity=severity,
        acknowledged=acknowledged,
        tags=tuple(tags),
    )
