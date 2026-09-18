#!/usr/bin/env python3
from __future__ import annotations
import argparse,json,re,subprocess,sys,unicodedata
from pathlib import Path

MANIFEST_PATH="implementation/g9-notification-delivery-authorization/AUTHORIZATION_MANIFEST.json"
AUTH_ID="g9.notification-delivery@1"
EXECUTABLE_SUFFIXES={".py",".js",".mjs",".cjs",".ts",".tsx",".jsx",".sh",".bash",".go",".rs",".java",".kt",".cs",".rb",".php"}
SQL_MUTATION_RE=re.compile(r"\b(?:insert\s+into\s+[^\s;()]+|update\s+[^\s;()]+\s+set\b|delete\s+from\s+[^\s;()]+|merge\s+into\s+[^\s;()]+|truncate(?:\s+table)?\s+[^\s;()]+|alter\s+(?:table|schema)\s+[^\s;()]+|drop\s+(?:table|schema|view|function|procedure)\s+[^\s;()]+|create\s+(?:table|schema|view|function|procedure)\s+[^\s;()]+)",re.I)

def git(root,*args): return subprocess.check_output(["git","-C",str(root),*args],text=True).strip()
def allowed(path,p): return path in set(p["allowed_exact_paths"]) or any(path.startswith(x) for x in p["allowed_prefixes"])
def candidate(root,path,head):
    try:return subprocess.check_output(["git","-C",str(root),"show",f"{head}:{path}"],text=True,stderr=subprocess.DEVNULL)
    except subprocess.CalledProcessError:return ""
def fold(v):
    n=unicodedata.normalize("NFKC",v).casefold()
    return re.sub(r"[^a-z0-9]+","",n)

def semantic_errors(path,text,p):
    if Path(path).suffix.lower() not in EXECUTABLE_SUFFIXES:return []
    out=[]; f=fold(text)
    for m in p.get("forbidden_code_markers") or []:
      if fold(m) in f: out.append(f"forbidden G10+ semantic marker '{m}' in {path}")
    if SQL_MUTATION_RE.search(text):
      out.append(f"direct SQL/schema mutation is forbidden in G9 application executable artifact: {path}")
    return out

def sql_errors(text,p):
    out=[]; f=fold(text)
    for m in ("notification_intent_id","notification_attempt_id","provider_evidence","dispatch_outbox","callback_inbox","tenant_id"):
      if fold(m) not in f: out.append(f"G9 exact SQL missing marker: {m}")
    allowed_rel={x.casefold() for x in p["exact_sql_allowed_relations"]}
    for schema,table in re.findall(r'\bcreate\s+table(?:\s+if\s+not\s+exists)?\s+"?([a-zA-Z_][\w]*)"?\s*\.\s*"?([a-zA-Z_][\w]*)"?',text,re.I):
      rel=f"{schema}.{table}".casefold()
      if schema.casefold()=="notification" and rel not in allowed_rel:
        out.append(f"G9 exact SQL creates unauthorized notification relation: {schema}.{table}")
    for pattern in (
      r"\b(?:insert\s+into|update|delete\s+from)\s+alerting\.",
      r"\b(?:insert\s+into|update|delete\s+from)\s+human_operations\.",
      r"\bcreate\s+(?:table|schema)\s+(?:alerting|human_operations|monitoring)\."
    ):
      if re.search(pattern,text,re.I): out.append(f"G9 SQL contains forbidden cross-domain mutation: {pattern}")
    return out

def workflow_errors(text,p):
    out=[]
    try:w=json.loads(text)
    except json.JSONDecodeError:return ["G9 runtime workflow must use canonical JSON-compatible structure"]
    if w.get("name")!=p["runtime_workflow_name"]:out.append("runtime name drift")
    if w.get("permissions")!={}:out.append("runtime permissions must be zero")
    if set((w.get("on") or {}).keys())!={"pull_request","workflow_dispatch"}:out.append("runtime trigger drift")
    jobs=w.get("jobs") or {}
    if set(jobs)!={"g9-runtime"}:return out+["runtime must contain exactly g9-runtime"]
    steps=jobs["g9-runtime"].get("steps") or []
    allowed_actions=set(p["runtime_allowed_actions"]); runs=[]
    for step in steps:
      if "uses" in step:
        if step["uses"] not in allowed_actions:out.append(f"unauthorized action: {step['uses']}")
        if set(step)!={"uses"}:out.append("action step input overrides forbidden")
      elif "run" in step:
        if set(step)!={"run"}:out.append("run step must be canonical command only")
        runs.append(str(step["run"]).strip())
      else:out.append("runtime step malformed")
    if runs!=[p["runtime_entrypoint"]]:out.append("runtime entrypoint drift")
    return out

def main()->int:
    ap=argparse.ArgumentParser()
    for arg in ("base","head","head-ref","labels-json","head-repo","base-repo"):ap.add_argument("--"+arg,required=True)
    ap.add_argument("--repo-root",default=".")
    a=ap.parse_args(); root=Path(a.repo_root).resolve(); errors=[]
    manifest=json.loads(subprocess.check_output(["git","-C",str(root),"show",f"{a.base}:{MANIFEST_PATH}"],text=True))
    p=manifest["implementation_path_policy"]
    if manifest.get("implementation_authority_after_merge")!="granted_for_exact_g9_notification_delivery_only":errors.append("base does not grant exact G9 authority")
    if a.head_repo!=a.base_repo:errors.append("implementation PR must use canonical repository")
    if not a.head_ref.startswith(p["implementation_pr_head_prefix"]):errors.append("head prefix drift")
    labels=set(json.loads(a.labels_json))
    if p["implementation_pr_required_label"] not in labels:errors.append("required G9 label missing")
    changed=[x for x in git(root,"diff","--name-only","--no-renames",f"{a.base}...{a.head}").splitlines() if x]
    if not changed:errors.append("implementation diff empty")
    forbidden=tuple(x.lower() for x in p["forbidden_path_tokens"]); scan=tuple(p["semantic_scan_prefixes"])
    for path in changed:
      if not allowed(path,p):errors.append(f"path outside G9 authority: {path}");continue
      if path!=p["exact_sql_path"] and any(x in path.lower() for x in forbidden):errors.append(f"forbidden path token in {path}")
      if path.startswith(scan):errors.extend(semantic_errors(path,candidate(root,path,a.head),p))
    sql=candidate(root,p["exact_sql_path"],a.head)
    if not sql:errors.append("exact G9 SQL required")
    else:errors.extend(sql_errors(sql,p))
    wf=candidate(root,p["runtime_workflow"],a.head)
    if not wf:errors.append("G9 runtime workflow required")
    else:errors.extend(workflow_errors(wf,p))
    claim=candidate(root,p["implementation_claim_path"],a.head)
    if not claim:errors.append("G9 implementation claim required")
    else:
      try:
        d=json.loads(claim)
        if d.get("authorization_id")!=AUTH_ID or d.get("slice_id")!=AUTH_ID:errors.append("G9 claim identity drift")
      except Exception:errors.append("G9 claim JSON invalid")
    for e in errors:print(f"G9_SCOPE_ERROR: {e}",file=sys.stderr)
    if errors:return 1
    print(f"g9_scope=PASS base={a.base} head={a.head} exact_scope=notification-delivery")
    return 0
if __name__=="__main__":raise SystemExit(main())
