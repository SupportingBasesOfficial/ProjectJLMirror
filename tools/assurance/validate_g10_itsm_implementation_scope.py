#!/usr/bin/env python3
from __future__ import annotations
import argparse,json,re,subprocess,sys,unicodedata
from pathlib import Path

MANIFEST_PATH="implementation/g10-itsm-authorization/AUTHORIZATION_MANIFEST.json"
AUTH_ID="g10.itsm-incident@1"
EXECUTABLE_SUFFIXES={".py",".js",".mjs",".cjs",".ts",".tsx",".jsx",".sh",".bash",".go",".rs",".java",".kt",".cs",".rb",".php"}
SQL_MUTATION_RE=re.compile(r"\b(?:insert\s+into\s+[^\s;()]+|update\s+[^\s;()]+\s+set\b|delete\s+from\s+[^\s;()]+|merge\s+into\s+[^\s;()]+|truncate(?:\s+table)?\s+[^\s;()]+|alter\s+(?:table|schema)\s+[^\s;()]+|drop\s+(?:table|schema|view|function|procedure)\s+[^\s;()]+|create\s+(?:table|schema|view|function|procedure)\s+[^\s;()]+)",re.I)

def git(root,*args): return subprocess.check_output(["git","-C",str(root),*args],text=True).strip()
def allowed(path,p): return path in set(p["allowed_exact_paths"]) or any(path.startswith(x) for x in p["allowed_prefixes"])
def candidate(root,path,head):
    try:return subprocess.check_output(["git","-C",str(root),"show",f"{head}:{path}"],text=True,stderr=subprocess.DEVNULL)
    except subprocess.CalledProcessError:return ""
def fold(v):
    return re.sub(r"[^a-z0-9]+","",unicodedata.normalize("NFKC",v).casefold())

def semantic_errors(path,text,p):
    if Path(path).suffix.lower() not in EXECUTABLE_SUFFIXES:return []
    out=[]; f=fold(text)
    for m in p.get("forbidden_code_markers") or []:
      if fold(m) in f:out.append(f"forbidden G11+ semantic marker '{m}' in {path}")
    if SQL_MUTATION_RE.search(text):
      out.append(f"direct SQL/schema mutation is forbidden in G10 application executable artifact: {path}")
    return out

def function_block(text,name):
    marker=f"CREATE OR REPLACE FUNCTION itsm.{name}"
    start=text.find(marker)
    if start<0:return ""
    next_start=text.find("CREATE OR REPLACE FUNCTION itsm.",start+len(marker))
    return text[start:] if next_start<0 else text[start:next_start]

def sql_errors(text,p):
    out=[]; f=fold(text)
    for m in ("incident_id","alert_id","incident_transition","incident_assignment","incident_comment","provider_link","sync_outbox","tenant_id"):
      if fold(m) not in f:out.append(f"G10 exact SQL missing marker: {m}")

    incident_read=function_block(text,"g10_get_incident")
    alert_match=re.search(
      r"SELECT\s+to_jsonb\s*\(\s*x\s*\)\s+INTO\s+v_alert\s+FROM\s*\((.*?)\)\s*x\s*;",
      incident_read,re.I|re.S
    )
    if not alert_match:
      out.append("G10 Incident detail must contain a bounded Alert-summary projection")
    else:
      alert_projection=alert_match.group(1)
      if not re.search(r"(?<![A-Za-z0-9_])opened_at(?![A-Za-z0-9_])",alert_projection,re.I):
        out.append("G10 Incident Alert summary must project opened_at")
      if re.search(r"(?<![A-Za-z0-9_])(?:[A-Za-z_][A-Za-z0-9_]*\s*\.\s*)?created_at(?![A-Za-z0-9_])",alert_projection,re.I):
        out.append("G10 Incident Alert summary must not reference nonexistent Alert created_at")

    discovery=function_block(text,"g10_next_sync_candidate")
    pending_branch=r"\(\s*o\.sync_state\s*=\s*'pending'\s+AND\s+o\.available_at\s*<=\s*transaction_timestamp\s*\(\s*\)\s*\)"
    expired_branch=r"\(\s*o\.sync_state\s*=\s*'dispatching'\s+AND\s+o\.claim_expires_at\s*<=\s*transaction_timestamp\s*\(\s*\)\s*\)"
    reachable_expired=(
      re.search(pending_branch+r"\s*OR\s*"+expired_branch,discovery,re.I|re.S)
      or re.search(expired_branch+r"\s*OR\s*"+pending_branch,discovery,re.I|re.S)
    )
    if not reachable_expired:
      out.append("G10 worker discovery must contain a reachable OR branch for expired dispatching sync claims")

    membership_guard=re.search(
      r"IF\s+EXISTS\s*\(\s*SELECT\s+1\s+FROM\s+pg_auth_members\s+WHERE\s+"
      r"(?:roleid\s*=\s*v_role\.oid\s+OR\s+member\s*=\s*v_role\.oid|"
      r"member\s*=\s*v_role\.oid\s+OR\s+roleid\s*=\s*v_role\.oid)"
      r"\s*\)\s*THEN\s+RAISE\s+EXCEPTION\s+'g10\.role_unsafe_membership:%'",
      text,re.I|re.S
    )
    if not membership_guard:
      out.append("G10 privileged-role membership detection must fail closed with g10.role_unsafe_membership")

    create=function_block(text,"g10_create_incident")
    lock_match=re.search(
      r"pg_advisory_xact_lock\s*\(\s*hashtextextended\s*\([^;]*p_logical_action_id[^;]*\)\s*\)",
      create,re.I|re.S
    )
    lookup_match=re.search(
      r"SELECT\s+\*\s+INTO\s+v_existing\s+FROM\s+itsm\.incident\b[^;]*logical_action_id\s*=\s*p_logical_action_id",
      create,re.I|re.S
    )
    if not lock_match or not lookup_match or lock_match.start()>=lookup_match.start():
      out.append("G10 Incident create must acquire the logical-action advisory lock before equivalence lookup")
    elif re.search(r"\bRETURN\b",create[:lock_match.start()],re.I):
      out.append("G10 Incident create logical-action lock must be reachable before any return")

    transition=function_block(text,"g10_transition_incident")
    replay_guard=re.search(
      r"IF\s+FOUND\s+THEN\s+"
      r"IF\s+v_existing_transition\.to_state\s+IS\s+DISTINCT\s+FROM\s+p_target_state\s+THEN\s+"
      r"RAISE\s+EXCEPTION\s+'g10\.transition_equivalence_conflict'\s*;\s*"
      r"END\s+IF\s*;\s*"
      r"RETURN\s+jsonb_build_object\s*\([^;]*'duplicate'\s*,\s*TRUE[^;]*\)\s*;\s*"
      r"END\s+IF\s*;",
      transition,re.I|re.S
    )
    if not replay_guard:
      out.append("G10 transition replay must reject divergent target before duplicate success")
    else:
      conflict_pos=transition.find("g10.transition_equivalence_conflict")
      duplicate_positions=[m.start() for m in re.finditer(r"'duplicate'\s*,\s*TRUE",transition,re.I)]
      if any(pos<conflict_pos for pos in duplicate_positions):
        out.append("G10 transition replay must not expose duplicate success before equivalence conflict check")

    allowed_rel={x.casefold() for x in p["exact_sql_allowed_relations"]}
    for schema,table in re.findall(r'\bcreate\s+table(?:\s+if\s+not\s+exists)?\s+"?([a-zA-Z_][\w]*)"?\s*\.\s*"?([a-zA-Z_][\w]*)"?',text,re.I):
      rel=f"{schema}.{table}".casefold()
      if schema.casefold()=="itsm" and rel not in allowed_rel:
        out.append(f"G10 exact SQL creates unauthorized itsm relation: {schema}.{table}")
    for pattern in (
      r"\b(?:insert\s+into|update|delete\s+from)\s+alerting\.",
      r"\b(?:insert\s+into|update|delete\s+from)\s+human_operations\.",
      r"\b(?:insert\s+into|update|delete\s+from)\s+notification\.",
      r"\bcreate\s+(?:table|schema)\s+(?:alerting|human_operations|notification|monitoring)\."
    ):
      if re.search(pattern,text,re.I):out.append(f"G10 SQL contains forbidden cross-domain mutation: {pattern}")
    return out

def workflow_errors(text,p):
    out=[]
    try:w=json.loads(text)
    except json.JSONDecodeError:return ["G10 runtime workflow must use canonical JSON-compatible structure"]
    if w.get("name")!=p["runtime_workflow_name"]:out.append("runtime name drift")
    if w.get("permissions")!={}:out.append("runtime permissions must be zero")
    if set((w.get("on") or {}).keys())!={"pull_request","workflow_dispatch"}:out.append("runtime trigger drift")
    jobs=w.get("jobs") or {}
    if set(jobs)!={"g10-runtime"}:return out+["runtime must contain exactly g10-runtime"]
    steps=jobs["g10-runtime"].get("steps") or []
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
    a=ap.parse_args();root=Path(a.repo_root).resolve();errors=[]
    manifest=json.loads(subprocess.check_output(["git","-C",str(root),"show",f"{a.base}:{MANIFEST_PATH}"],text=True))
    p=manifest["implementation_path_policy"]
    if manifest.get("implementation_authority_after_merge")!="granted_for_exact_g10_itsm_incident_only":errors.append("base does not grant exact G10 authority")
    if a.head_repo!=a.base_repo:errors.append("implementation PR must use canonical repository")
    if not a.head_ref.startswith(p["implementation_pr_head_prefix"]):errors.append("head prefix drift")
    labels=set(json.loads(a.labels_json))
    if p["implementation_pr_required_label"] not in labels:errors.append("required G10 label missing")
    changed=[x for x in git(root,"diff","--name-only","--no-renames",f"{a.base}...{a.head}").splitlines() if x]
    if not changed:errors.append("implementation diff empty")
    forbidden=tuple(x.lower() for x in p["forbidden_path_tokens"]);scan=tuple(p["semantic_scan_prefixes"])
    for path in changed:
      if not allowed(path,p):errors.append(f"path outside G10 authority: {path}");continue
      if path!=p["exact_sql_path"] and any(x in path.lower() for x in forbidden):errors.append(f"forbidden path token in {path}")
      if path.startswith(scan):errors.extend(semantic_errors(path,candidate(root,path,a.head),p))
    sql=candidate(root,p["exact_sql_path"],a.head)
    if not sql:errors.append("exact G10 SQL required")
    else:errors.extend(sql_errors(sql,p))
    wf=candidate(root,p["runtime_workflow"],a.head)
    if not wf:errors.append("G10 runtime workflow required")
    else:errors.extend(workflow_errors(wf,p))
    claim=candidate(root,p["implementation_claim_path"],a.head)
    if not claim:errors.append("G10 implementation claim required")
    else:
      try:
        d=json.loads(claim)
        if d.get("authorization_id")!=AUTH_ID or d.get("slice_id")!=AUTH_ID:errors.append("G10 claim identity drift")
      except Exception:errors.append("G10 claim JSON invalid")
    for e in errors:print(f"G10_SCOPE_ERROR: {e}",file=sys.stderr)
    if errors:return 1
    print(f"g10_scope=PASS base={a.base} head={a.head} exact_scope=itsm-incident")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
