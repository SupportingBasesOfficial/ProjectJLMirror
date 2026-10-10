from __future__ import annotations

from dataclasses import dataclass,field
from hashlib import sha256

SEVERITIES=["LOW","MEDIUM","HIGH","CRITICAL"]
SEVERITY_ORDER={s:i for i,s in enumerate(SEVERITIES)}
VALID_ACTIONS={"open_ticket","notify","automation"}


@dataclass(frozen=True)
class ApplicationErrorEvent:
    tenant_id:str
    application_id:str
    error_code:str
    error_message:str
    occurred_at:str          # ISO 8601 from source system
    source_principal_id:str  # machine principal that pushed this event
    principal_id:str|None=None         # user active in source system at error time
    operation:str|None=None            # function/process/route where error occurred
    session_context:str|None=None      # opaque request/session id from source
    severity_hint:str|None=None        # LOW|MEDIUM|HIGH|CRITICAL (advisory)
    raw_payload:dict|None=None         # structured or unstructured extra context


@dataclass(frozen=True)
class IncidentResponsePolicy:
    tenant_id:str
    severity_threshold:str="HIGH"
    auto_open_ticket:bool=False
    manual_override_only:bool=False
    notify_channels:tuple=()
    automation_triggers:tuple=()


def validate_event(event:ApplicationErrorEvent)->None:
    if not event.tenant_id: raise ValueError("tenant_id required")
    if not event.application_id or len(event.application_id)>128:
        raise ValueError("application_id invalid")
    if not event.error_code or len(event.error_code)>128:
        raise ValueError("error_code invalid")
    if not event.error_message or len(event.error_message)>4000:
        raise ValueError("error_message invalid")
    if not event.occurred_at or len(event.occurred_at)>64:
        raise ValueError("occurred_at required")
    if not event.source_principal_id:
        raise ValueError("source_principal_id required")
    if event.severity_hint is not None and event.severity_hint not in SEVERITIES:
        raise ValueError(f"severity_hint must be one of {SEVERITIES}")
    if event.principal_id is not None and len(event.principal_id)>256:
        raise ValueError("principal_id too long")
    if event.operation is not None and len(event.operation)>256:
        raise ValueError("operation too long")
    if event.session_context is not None and len(event.session_context)>512:
        raise ValueError("session_context too long")


def severity_meets_threshold(hint:str|None,threshold:str)->bool:
    if hint is None: return False
    return SEVERITY_ORDER.get(hint,-1)>=SEVERITY_ORDER.get(threshold,999)


def evaluate_policy(event:ApplicationErrorEvent,policy:IncidentResponsePolicy)->list[str]:
    if policy.manual_override_only: return []
    if not severity_meets_threshold(event.severity_hint,policy.severity_threshold): return []
    actions:list[str]=[]
    if policy.auto_open_ticket: actions.append("open_ticket")
    for ch in policy.notify_channels:
        if event.severity_hint in ch.get("on_severities",[]):
            actions.append("notify")
            break
    for tr in policy.automation_triggers:
        if tr.get("trigger")=="ALERT_OPEN":
            actions.append("automation")
            break
    return actions


def minute_bucket(occurred_at:str)->str:
    return occurred_at[:16]  # "YYYY-MM-DDTHH:MM" — 1-minute precision


def deterministic_id(prefix:str,*parts:str)->str:
    return prefix+sha256("\x1f".join(parts).encode()).hexdigest()
