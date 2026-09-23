#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import unicodedata
from pathlib import Path

MANIFEST_PATH="implementation/g8-human-operations-authorization/AUTHORIZATION_MANIFEST.json"
AUTH_ID="g8.human-operations@1"
EXECUTABLE_SUFFIXES={".py",".js",".mjs",".cjs",".ts",".tsx",".jsx",".sh",".bash",".go",".rs",".java",".kt",".cs",".rb",".php"}
PERSISTENCE_RECEIVERS=("database","db","repository","repo","prisma","postgres","postgresql","pg","sqlalchemy","psycopg","cursor")
PERSISTENCE_WRITES=("insert","update","delete","save","upsert","commit","persist","executemany")
SQL_MUTATION_RE=re.compile(r"\b(?:insert\s+into\s+[^\s;()]+|update\s+[^\s;()]+\s+set\b|delete\s+from\s+[^\s;()]+|merge\s+into\s+[^\s;()]+|truncate(?:\s+table)?\s+[^\s;()]+|alter\s+(?:table|schema)\s+[^\s;()]+|drop\s+(?:table|schema|view|function|procedure)\s+[^\s;()]+|create\s+(?:table|schema|view|function|procedure)\s+[^\s;()]+)",re.IGNORECASE)


def git(root:Path,*args:str)->str:
    return subprocess.check_output(["git","-C",str(root),*args],text=True).strip()


def allowed(path:str,policy:dict)->bool:
    return path in set(policy.get("allowed_exact_paths") or []) or any(path.startswith(prefix) for prefix in policy.get("allowed_prefixes") or [])


def candidate_text(root:Path,path:str,head:str)->str:
    try:
        return subprocess.check_output(["git","-C",str(root),"show",f"{head}:{path}"],text=True,stderr=subprocess.DEVNULL)
    except subprocess.CalledProcessError:
        return ""


def semantic_fold(value:str)->str:
    normalized=unicodedata.normalize("NFKC",value).casefold()
    normalized=re.sub(r"\\u\\{?([0-9a-fA-F]{4,6})\\}?",lambda m:chr(int(m.group(1),16)),normalized)
    normalized=re.sub(r"\\x([0-9a-fA-F]{2})",lambda m:chr(int(m.group(1),16)),normalized)
    return re.sub(r"[^a-z0-9]+","",normalized)


def semantic_errors(path:str,text:str,policy:dict)->list[str]:
    if Path(path).suffix.lower() not in EXECUTABLE_SUFFIXES:
        return []
    errors:list[str]=[]
    folded=semantic_fold(text)

    for marker in policy.get("forbidden_code_markers") or []:
        folded_marker=semantic_fold(str(marker))
        if folded_marker and folded_marker in folded:
            errors.append(f"forbidden G9+ semantic marker '{marker}' in {path}")

    if SQL_MUTATION_RE.search(text):
        errors.append(f"direct SQL/schema mutation is forbidden in G8 application executable artifact: {path}")

    receivers=set(PERSISTENCE_RECEIVERS)
    assignment_re=re.compile(r"\b(?:const\s+|let\s+|var\s+)?([A-Za-z_$][\w$]*)\s*=\s*(?:(?:self|this)\s*\.\s*)?([A-Za-z_$][\w$]*)\b")
    changed=True
    while changed:
        changed=False
        for alias,source in assignment_re.findall(text):
            if source.casefold() in {name.casefold() for name in receivers} and alias not in receivers:
                receivers.add(alias)
                changed=True

    receiver="|".join(sorted((re.escape(x) for x in receivers),key=len,reverse=True))
    method="|".join(re.escape(x) for x in PERSISTENCE_WRITES)
    if receiver:
        checks=[
            re.compile(rf"\b(?:{receiver})\s*\.\s*(?:{method})\b",re.IGNORECASE),
            re.compile(rf"\b(?:{receiver})\s*\[\s*['\"](?:{method})['\"]\s*\]",re.IGNORECASE),
            re.compile(rf"\bgetattr\s*\(\s*(?:{receiver})\s*,\s*['\"](?:{method})['\"]\s*\)",re.IGNORECASE),
        ]
        if any(rx.search(text) for rx in checks):
            errors.append(f"direct persistence write is forbidden in G8 application executable artifact: {path}")
    return errors


def exact_sql_errors(text:str,policy:dict)->list[str]:
    errors:list[str]=[]
    folded=semantic_fold(text)
    for marker in (
        "responsibility_assignment_id",
        "acknowledgement_id",
        "visibility_requirement_id",
        "visibility_receipt_id",
        "current_action",
        "tenant_id",
    ):
        if semantic_fold(marker) not in folded:
            errors.append(f"G8 exact SQL missing required human-operations marker: {marker}")

    allowed_relations={str(r).casefold() for r in policy.get("exact_sql_allowed_relations") or []}
    created_relations=re.findall(
        r'\bcreate\s+table(?:\s+if\s+not\s+exists)?\s+"?([a-zA-Z_][\w]*)"?\s*\.\s*"?([a-zA-Z_][\w]*)"?',
        text,re.IGNORECASE,
    )
    for schema,table in created_relations:
        relation=f"{schema}.{table}".casefold()
        if schema.casefold()=="human_operations" and relation not in allowed_relations:
            errors.append(f"G8 exact SQL creates non-authorized Human Operations relation: {schema}.{table}")

    for pattern in (
        r"\binsert\s+into\s+alerting\.",
        r"\bupdate\s+alerting\.",
        r"\bdelete\s+from\s+alerting\.",
        r"\binsert\s+into\s+monitoring\.",
        r"\bupdate\s+monitoring\.",
        r"\bdelete\s+from\s+monitoring\.",
        r"\bcreate\s+(?:table|schema)\s+(?:alerting|monitoring|system)\.",
    ):
        if re.search(pattern,text,re.IGNORECASE):
            errors.append(f"G8 exact SQL contains forbidden non-Human-Operations mutation: {pattern}")

    for marker in (
        "notification_intent","delivery_attempt","delivery_state","provider_accepted",
        "external_read_receipt","whatsapp","send_email","send_sms","teams_webhook","slack_webhook",
        "awaiting_budget_approval","approval_state","incident_id","ticket_id",
        "provider_write_back","unacknowledge","alert_reopen"
    ):
        if semantic_fold(marker) in folded:
            errors.append(f"G8 exact SQL contains forbidden G9+ marker: {marker}")
    return errors


def runtime_workflow_errors(text:str,policy:dict)->list[str]:
    errors:list[str]=[]
    try:
        workflow=json.loads(text)
    except json.JSONDecodeError:
        return ["G8 runtime workflow must use canonical JSON-compatible workflow structure"]

    if workflow.get("name")!=policy.get("runtime_workflow_name"):
        errors.append("G8 runtime workflow name drift")
    if workflow.get("permissions")!={}:
        errors.append("G8 runtime workflow must default to zero permissions")

    triggers=workflow.get("on")
    if not isinstance(triggers,dict) or set(triggers)!={"pull_request","workflow_dispatch"}:
        errors.append("G8 runtime workflow trigger surface drift")

    jobs=workflow.get("jobs")
    if not isinstance(jobs,dict) or set(jobs)!={"g8-runtime"}:
        errors.append("G8 runtime workflow must contain exactly g8-runtime job")
        return errors

    steps=jobs["g8-runtime"].get("steps") if isinstance(jobs["g8-runtime"],dict) else None
    if not isinstance(steps,list) or not steps:
        return errors+["G8 runtime workflow steps missing"]

    allowed_actions=set(policy.get("runtime_allowed_actions") or [])
    runs:list[str]=[]
    for step in steps:
        if not isinstance(step,dict):
            errors.append("G8 runtime workflow step must be an object")
            continue
        use=step.get("uses")
        run=step.get("run")
        if use is not None:
            if use not in allowed_actions:
                errors.append(f"G8 runtime workflow uses unauthorized action: {use}")
            if set(step)!={"uses"}:
                errors.append("G8 runtime action steps may not override inputs")
        elif run is not None:
            if set(step)!={"run"}:
                errors.append("G8 runtime run step may contain only canonical command")
            if isinstance(run,str):
                runs.append(run.strip())
        else:
            errors.append("G8 runtime workflow step must contain uses or run")

    if runs!=[policy.get("runtime_entrypoint")]:
        errors.append("G8 runtime workflow must execute exactly the canonical runtime entrypoint once")
    return errors


def main()->int:
    parser=argparse.ArgumentParser()
    parser.add_argument("--repo-root",default=".")
    parser.add_argument("--base",required=True)
    parser.add_argument("--head",required=True)
    parser.add_argument("--head-ref",required=True)
    parser.add_argument("--labels-json",required=True)
    parser.add_argument("--head-repo",required=True)
    parser.add_argument("--base-repo",required=True)
    args=parser.parse_args()

    root=Path(args.repo_root).resolve()
    errors:list[str]=[]
    manifest=json.loads(subprocess.check_output(
        ["git","-C",str(root),"show",f"{args.base}:{MANIFEST_PATH}"],text=True
    ))
    policy=manifest["implementation_path_policy"]

    if manifest.get("implementation_authority_after_merge")!="granted_for_exact_g8_human_operations_only":
        errors.append("base does not grant exact G8 implementation authority")
    if args.head_repo!=args.base_repo:
        errors.append("implementation PR must use canonical repository")
    if not args.head_ref.startswith(policy["implementation_pr_head_prefix"]):
        errors.append("implementation head prefix is not canonical G8 prefix")

    try:
        labels=set(json.loads(args.labels_json))
    except Exception:
        labels=set()
        errors.append("labels-json is invalid")
    if policy["implementation_pr_required_label"] not in labels:
        errors.append("implementation PR missing required G8 label")

    changed=[p for p in git(root,"diff","--name-only","--no-renames",f"{args.base}...{args.head}").splitlines() if p]
    if not changed:
        errors.append("implementation diff is empty")

    forbidden_tokens=tuple(str(x).lower() for x in policy.get("forbidden_path_tokens") or [])
    scan_prefixes=tuple(policy.get("semantic_scan_prefixes") or [])
    for path in changed:
        if not allowed(path,policy):
            errors.append(f"path outside G8 implementation authority: {path}")
            continue
        if path!=policy.get("exact_sql_path") and any(token in path.lower() for token in forbidden_tokens):
            errors.append(f"forbidden G9+ path token in {path}")
        if path.startswith(scan_prefixes):
            errors.extend(semantic_errors(path,candidate_text(root,path,args.head),policy))

    sql_path=policy["exact_sql_path"]
    sql_text=candidate_text(root,sql_path,args.head)
    if not sql_text:
        errors.append("G8 exact Human Operations SQL is required")
    else:
        errors.extend(exact_sql_errors(sql_text,policy))

    workflow_path=policy["runtime_workflow"]
    workflow_text=candidate_text(root,workflow_path,args.head)
    if not workflow_text:
        errors.append("G8 runtime workflow is required")
    else:
        errors.extend(runtime_workflow_errors(workflow_text,policy))

    claim_text=candidate_text(root,policy["implementation_claim_path"],args.head)
    if not claim_text:
        errors.append("G8 implementation claim is required")
    else:
        try:
            claim=json.loads(claim_text)
            if claim.get("authorization_id")!=AUTH_ID:
                errors.append("G8 claim authorization id drift")
            if claim.get("slice_id")!=AUTH_ID:
                errors.append("G8 claim slice id drift")
        except Exception:
            errors.append("G8 implementation claim is invalid JSON")

    for error in errors:
        print(f"G8_SCOPE_ERROR: {error}",file=sys.stderr)
    if errors:
        return 1

    print(f"g8_scope=PASS base={args.base} head={args.head} exact_scope=human-operations")
    return 0


if __name__=="__main__":
    raise SystemExit(main())
