#!/usr/bin/env python3
from __future__ import annotations
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
M=ROOT/"implementation/g10-itsm-authorization/AUTHORIZATION_MANIFEST.json"

def require(ok,msg):
    if not ok: raise AssertionError(msg)

def main()->int:
    d=json.loads(M.read_text(encoding="utf-8"))
    p=d["implementation_path_policy"]
    m=d["incident_v1"]
    require(d["authorization_id"]=="g10.itsm-incident@1","id drift")
    require(m["object_type"]=="incident","object surface widened")
    require(m["external_provider_selected"] is False,"provider selection widened")
    require(m["reopen_authorized"] is False,"reopen widened")
    require(len(p["exact_sql_allowed_relations"])==6,"relation surface widened")
    forbidden=set(d["explicitly_not_authorized"])
    for x in ("change_rfc","approval_budget_quote","task_subtask","named_external_itsm_vendor"):
        require(x in forbidden,f"missing exclusion {x}")
    print("g10_authorization_falsification=PASS incident=allowed change_approval_task_vendor=blocked g11_plus=blocked")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
