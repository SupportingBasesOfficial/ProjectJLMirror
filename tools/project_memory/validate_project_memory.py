from __future__ import annotations

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MEMORY = ROOT / "docs" / "00-foundation" / "project-memory"
WORKFLOW = ROOT / ".github" / "workflows" / "project-memory-governance.yml"

REQUIRED_FILES = (
    "PROJECT-IDENTITY.md","E2E-SYSTEM-MAP.md","DOMAIN-AUTHORITY-MAP.md","CANONICAL-INVARIANTS.md",
    "DECISION-REGISTER.md","IMPLEMENTATION-STATE.md","ACCEPTED-PR-CHAIN.md","ROADMAP-DEPENDENCY-GRAPH.md",
    "GLOSSARY.md","HUMAN-OPERATIONS-MODEL.md","OPEN-QUESTIONS-AND-DEFERRED.md","RECOVERY-PLAYBOOK-FOR-NEW-CHAT.md",
)
BASELINE_DECISION_MEANINGS = {
    "JLM-DEC-001":"JLMirror is provider-neutral, not a Zabbix UI","JLM-DEC-002":"Tenant isolation is foundational",
    "JLM-DEC-003":"Provider identity is not platform identity","JLM-DEC-004":"Source generation participates in provider-evidence scope",
    "JLM-DEC-005":"PostgreSQL is durable business truth","JLM-DEC-006":"Async delivery is at-least-once",
    "JLM-DEC-007":"Browser access crosses mandatory BFF boundary","JLM-DEC-008":"Problem State and Health Projection are distinct Monitoring concepts",
    "JLM-DEC-009":"Healthy requires authoritative completeness","JLM-DEC-010":"Monitoring->Alerting events are invalidation/resync only",
    "JLM-DEC-011":"Alert is platform-owned actionable occurrence","JLM-DEC-012":"Alert v1 lifecycle is `active \\| resolved`; resolved is terminal",
    "JLM-DEC-013":"Effectful Alert lifecycle transitions require immutable policy ID/version","JLM-DEC-014":"Alert source family is explicit",
    "JLM-DEC-015":"Human operations use orthogonal state dimensions, not one giant status","JLM-DEC-016":"Critical human workflows must provide authoritative visibility evidence",
    "JLM-DEC-017":"Repository truth outranks assistant/chat memory",
}
BASELINE_DECISION_IDS=tuple(BASELINE_DECISION_MEANINGS)
DECISION_ID_RE=re.compile(r"JLM-DEC-\d{3}")
DECISION_SUPERSESSION_CLAUSE_RE=re.compile(r"\bsuperseded\s+by\b",re.IGNORECASE)
DECISION_SUPERSESSION_TARGET_RE=re.compile(r"\bsuperseded\s+by\s+([^\s|,;.]+)",re.IGNORECASE)
FENCE_OPEN_RE=re.compile(r"^[ ]{0,3}(`{3,}|~{3,})")
FENCE_CLOSE_RE=re.compile(r"^[ ]{0,3}(`{3,}|~{3,})[ \t]*$")
RAW_HTML_CONTAINER_OPEN_RE=re.compile(r"^[ ]{0,3}<(?P<tag>script|pre|style|textarea)(?:\s|>|$)",re.IGNORECASE)
RAW_HTML_BLOCK_OPEN_RE=re.compile(r"^[ ]{0,3}</?(?:address|article|aside|base|basefont|blockquote|body|caption|center|col|colgroup|dd|details|dialog|dir|div|dl|dt|fieldset|figcaption|figure|footer|form|frame|frameset|h[1-6]|head|header|hr|html|iframe|legend|li|link|main|menu|menuitem|nav|noframes|ol|optgroup|option|p|param|search|section|summary|table|tbody|td|tfoot|th|thead|title|tr|track|ul)(?:\s|/?>|$)",re.IGNORECASE)
RAW_HTML_PROCESSING_OPEN_RE=re.compile(r"^[ ]{0,3}<\?")
RAW_HTML_CDATA_OPEN_RE=re.compile(r"^[ ]{0,3}<!\[CDATA\[")
RAW_HTML_DECLARATION_OPEN_RE=re.compile(r"^[ ]{0,3}<![A-Z]")
RAW_HTML_GENERIC_TAG_RE=re.compile(
    r"^[ ]{0,3}</?[A-Za-z][A-Za-z0-9-]*(?:\s+(?:[A-Za-z_:][A-Za-z0-9_.:-]*(?:\s*=\s*(?:\"[^\"]*\"|'[^']*'|[^\s\"'=<>`]+))?))*\s*/?>[ \t]*$"
)
CANONICAL_RESOLVE_BODY = "\n".join((
    "set -euo pipefail",
    'if [[ "$EVENT_NAME" == "pull_request" ]]; then',
    '  resolved_sha="$PR_HEAD_SHA"',
    "else",
    '  resolved_sha="$EVENT_SHA"',
    "fi",
    'test -n "$resolved_sha"',
    "printf 'sha=%s\\n' \"$resolved_sha\" >> \"$GITHUB_OUTPUT\"",
))

def read(name:str)->str:
    path=MEMORY/name
    if not path.is_file(): raise AssertionError(f"project_memory_missing_file:{name}")
    text=path.read_text(encoding="utf-8")
    if len(text.strip())<200: raise AssertionError(f"project_memory_file_too_small:{name}")
    return text

def _visible_markdown_lines(text:str)->list[str]:
    visible=[]; in_comment=False; fence_char=None; fence_len=0; raw_html_container=None; raw_html_until_blank=False; raw_html_until_token=None
    for raw in text.splitlines():
        if raw_html_container is not None:
            if re.search(rf"</{re.escape(raw_html_container)}\s*>",raw,re.IGNORECASE): raw_html_container=None
            continue
        if raw_html_until_token is not None:
            if raw_html_until_token in raw: raw_html_until_token=None
            continue
        if raw_html_until_blank:
            if not raw.strip(): raw_html_until_blank=False
            continue
        if fence_char is not None:
            closing=FENCE_CLOSE_RE.match(raw)
            if closing:
                marker=closing.group(1)
                if marker[0]==fence_char and len(marker)>=fence_len: fence_char=None; fence_len=0
            continue
        container=RAW_HTML_CONTAINER_OPEN_RE.match(raw)
        if container:
            tag=container.group("tag").lower()
            if re.search(rf"</{re.escape(tag)}\s*>",raw,re.IGNORECASE) is None: raw_html_container=tag
            continue
        if RAW_HTML_CDATA_OPEN_RE.match(raw):
            if "]]>" not in raw: raw_html_until_token="]] >".replace(" ","")
            continue
        if RAW_HTML_PROCESSING_OPEN_RE.match(raw):
            if "?>" not in raw: raw_html_until_token="?>"
            continue
        if RAW_HTML_DECLARATION_OPEN_RE.match(raw):
            if ">" not in raw: raw_html_until_token=">"
            continue
        if RAW_HTML_BLOCK_OPEN_RE.match(raw) or RAW_HTML_GENERIC_TAG_RE.match(raw): raw_html_until_blank=True; continue
        remainder=raw; rendered=""
        while remainder:
            if in_comment:
                end=remainder.find("-->")
                if end<0: remainder=""; break
                remainder=remainder[end+3:]; in_comment=False; continue
            start=remainder.find("<!--")
            if start<0: rendered+=remainder; break
            rendered+=remainder[:start]; remainder=remainder[start+4:]; in_comment=True
        if not rendered.strip(): continue
        fence=FENCE_OPEN_RE.match(rendered)
        if fence:
            marker=fence.group(1); fence_char=marker[0]; fence_len=len(marker); continue
        visible.append(rendered.rstrip())
    return visible

def _decision_definition_rows(decisions:str)->list[tuple[str,str]]:
    rows=[]
    for line in _visible_markdown_lines(decisions):
        m=re.match(r"^\|\s*(JLM-DEC-\d{3})\s*\|",line)
        if m: rows.append((m.group(1),line))
    return rows

def decision_definition_ids(decisions:str)->list[str]: return [x for x,_ in _decision_definition_rows(decisions)]
def _validate_baseline_decision_meanings(decisions:str)->None:
    rows=dict(_decision_definition_rows(decisions))
    for did,meaning in BASELINE_DECISION_MEANINGS.items():
        row=rows.get(did)
        if row is not None and re.match(rf"^\|\s*{re.escape(did)}\s*\|\s*{re.escape(meaning)}\s*\|",row) is None:
            raise AssertionError(f"project_memory_baseline_decision_meaning_changed:{did}")
def decision_supersession_edges(decisions:str)->dict[str,str]:
    edges={}
    for source,row in _decision_definition_rows(decisions):
        clauses=DECISION_SUPERSESSION_CLAUSE_RE.findall(row)
        if not clauses: continue
        targets=DECISION_SUPERSESSION_TARGET_RE.findall(row)
        if len(clauses)!=1 or len(targets)!=1 or not DECISION_ID_RE.fullmatch(targets[0]): raise AssertionError(f"project_memory_malformed_supersession:{source}")
        edges[source]=targets[0]
    return edges
def decision_supersession_targets(decisions:str)->list[str]: return list(decision_supersession_edges(decisions).values())
def _validate_supersession_acyclic(edges:dict[str,str])->None:
    state={}
    def visit(node):
        marker=state.get(node,0)
        if marker==1: raise AssertionError(f"project_memory_supersession_cycle:{node}")
        if marker==2:return
        state[node]=1; target=edges.get(node)
        if target is not None:
            if target==node: raise AssertionError(f"project_memory_supersession_self_reference:{node}")
            if target in edges: visit(target)
        state[node]=2
    for source in edges: visit(source)
def validate_decision_register(decisions:str)->int:
    ids=decision_definition_ids(decisions)
    if len(ids)!=len(set(ids)): raise AssertionError("project_memory_duplicate_decision_definition_id")
    defined=set(ids); missing=[d for d in BASELINE_DECISION_IDS if d not in defined]
    if missing: raise AssertionError("project_memory_missing_baseline_decision:"+",".join(missing))
    _validate_baseline_decision_meanings(decisions); edges=decision_supersession_edges(decisions)
    for target in edges.values():
        if target not in defined: raise AssertionError(f"project_memory_missing_supersession_target:{target}")
    _validate_supersession_acyclic(edges); return len(ids)
def validate_human_operations(human:str)->None:
    for token in ("Internal and customer-side authority","authoritative visibility","JLMirror-controlled authenticated surface","continue tracking and presenting whether/when the customer has viewed","RESPONSIBLE PERSON != CURRENT ACTION OWNER","DELIVERED != VIEWED"):
        if token not in human: raise AssertionError(f"project_memory_human_model_missing:{token}")

def _normalize_yaml_key(raw_key:str)->str:
    raw_key=raw_key.strip()
    if raw_key.startswith("'") and raw_key.endswith("'"): return raw_key[1:-1].replace("''", "'")
    if raw_key.startswith('"') and raw_key.endswith('"'):
        try: parsed=ast.literal_eval(raw_key)
        except (SyntaxError,ValueError): return raw_key
        return parsed if isinstance(parsed,str) else raw_key
    return raw_key
def _yaml_key_value(candidate:str)->tuple[str,str]|None:
    m=re.match(r"(?P<key>'(?:''|[^'])*'|\"(?:\\.|[^\"])*\"|[^:#][^:]*?)\s*:\s*(?P<value>.*)$",candidate)
    return None if not m else (_normalize_yaml_key(m.group("key")),m.group("value").strip())
def _project_memory_job_lines(workflow:str)->list[str]:
    lines=workflow.splitlines(); start=next((i for i,l in enumerate(lines) if l=="  project-memory:"),None)
    if start is None: raise AssertionError("project_memory_workflow_job_missing")
    end=len(lines)
    for i in range(start+1,len(lines)):
        line=lines[i]
        if line.strip() and len(line)-len(line.lstrip(" "))<=2: end=i; break
    return lines[start+1:end]
def _project_memory_job_keys(workflow:str)->set[str]:
    keys=set()
    for line in _project_memory_job_lines(workflow):
        indent=len(line)-len(line.lstrip(" ")); stripped=line.strip()
        if indent!=4 or not stripped or stripped.startswith("#"): continue
        if stripped.startswith("?"):
            raise AssertionError("project_memory_workflow_job_explicit_key_not_allowed")
        pair=_yaml_key_value(stripped)
        if pair: keys.add(pair[0])
    return keys
def _project_memory_job_mapping(workflow:str,parent:str)->dict[str,str]:
    lines=_project_memory_job_lines(workflow); result={}; in_parent=False
    for line in lines:
        indent=len(line)-len(line.lstrip(" ")); stripped=line.strip()
        if indent==4:
            if stripped.startswith("?"): raise AssertionError("project_memory_workflow_job_explicit_key_not_allowed")
            pair=_yaml_key_value(stripped) if stripped and not stripped.startswith("#") else None
            in_parent=bool(pair and pair[0]==parent and pair[1]=="")
            continue
        if in_parent and indent==6 and stripped and not stripped.startswith("#"):
            pair=_yaml_key_value(stripped)
            if pair: result[pair[0]]=pair[1]
        elif in_parent and stripped and indent<=4: in_parent=False
    return result
def _project_memory_workflow_steps(workflow:str)->list[dict[str,str]]:
    job_lines=_project_memory_job_lines(workflow); steps_start=next((i for i,l in enumerate(job_lines) if l=="    steps:"),None)
    if steps_start is None: raise AssertionError("project_memory_workflow_steps_missing")
    blocks=[]; current=None
    for line in job_lines[steps_start+1:]:
        indent=len(line)-len(line.lstrip(" ")); stripped=line.strip()
        if indent==6 and stripped.startswith("- "):
            if current is not None: blocks.append(current)
            current=[line]; continue
        if current is not None: current.append(line)
    if current is not None: blocks.append(current)
    steps=[]
    for block in blocks:
        current={"__block__":"\n".join(block)}; pending=None; nested=None; block_key=None; block_body=[]
        for idx,line in enumerate(block):
            indent=len(line)-len(line.lstrip(" ")); stripped=line.strip()
            if idx==0:
                pair=_yaml_key_value(stripped[2:].strip())
                if pair: current[pair[0]]=pair[1]
                continue
            if block_key is not None:
                if indent>=10: block_body.append(line[10:] if len(line)>=10 else ""); continue
                current[f"{block_key}.body"]="\n".join(block_body); block_key=None; block_body=[]
            if not stripped or stripped.startswith("#"): continue
            if indent==8:
                nested=None
                if stripped.startswith("? "): pending=_normalize_yaml_key(stripped[2:].strip()); continue
                if stripped.startswith(":") and pending is not None: current[pending]=stripped[1:].strip(); pending=None; continue
                pending=None; pair=_yaml_key_value(stripped)
                if pair:
                    current[pair[0]]=pair[1]
                    if pair[1]=="": nested=pair[0]
                    if pair[1] in {"|","|-",">",">-"}: block_key=pair[0]
                continue
            if indent==10 and nested is not None:
                pair=_yaml_key_value(stripped)
                if pair: current[f"{nested}.{pair[0]}"]=pair[1]
        if block_key is not None: current[f"{block_key}.body"]="\n".join(block_body)
        steps.append(current)
    return steps
def _unique_step(steps:list[dict[str,str]],name:str)->dict[str,str]:
    matches=[s for s in steps if s.get("name")==name]
    if len(matches)!=1: raise AssertionError(f"project_memory_workflow_step_identity_invalid:{name}")
    return matches[0]

def validate_project_memory_workflow(workflow:str)->None:
    if "if" in _project_memory_job_keys(workflow): raise AssertionError("project_memory_workflow_job_condition_not_allowed")
    job_env=_project_memory_job_mapping(workflow,"env")
    expected_job_env={"EVENT_NAME":"${{ github.event_name }}","PR_HEAD_SHA":"${{ github.event.pull_request.head.sha }}","EVENT_SHA":"${{ github.sha }}"}
    if job_env!=expected_job_env: raise AssertionError("project_memory_workflow_job_env_binding_invalid")
    steps=_project_memory_workflow_steps(workflow)
    if any("if" in s for s in steps): raise AssertionError("project_memory_workflow_condition_not_allowed")
    if any("continue-on-error" in s for s in steps): raise AssertionError("project_memory_workflow_continue_on_error_not_allowed")
    resolve=_unique_step(steps,"Resolve exact analyzed HEAD"); body=resolve.get("run.body","")
    if resolve.get("id")!="target" or resolve.get("shell")!="bash" or body!=CANONICAL_RESOLVE_BODY:
        raise AssertionError("project_memory_workflow_resolve_head_binding_invalid")
    checkout=_unique_step(steps,"Checkout exact analyzed HEAD")
    if checkout.get("uses")!="actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1" or checkout.get("with.ref")!="${{ steps.target.outputs.sha }}" or checkout.get("with.persist-credentials")!="false" or checkout.get("with.fetch-depth")!="0" or checkout.get("with.allow-unsafe-pr-checkout")!="false": raise AssertionError("project_memory_workflow_checkout_binding_invalid")
    verify=_unique_step(steps,"Verify exact commit identity"); verify_body=verify.get("run.body","")
    if verify.get("env.EXPECTED_SHA")!="${{ steps.target.outputs.sha }}" or verify.get("shell")!="bash" or 'test "$(git rev-parse HEAD)" = "$EXPECTED_SHA"' not in verify_body: raise AssertionError("project_memory_workflow_verify_head_binding_invalid")
    required={"Validate canonical project memory":"python3 tools/project_memory/validate_project_memory.py","Test canonical project memory":"python3 -m unittest discover -s tests/project_memory -p 'test_*.py'","Falsify canonical project-memory guardrails":"PYTHONPATH=tools/assurance:tools/project_memory python3 tools/assurance/test_validate_d4c_selection.py","Validate repository structure and workflow safety":"python3 tools/assurance/validate_repository.py"}
    for name,run in required.items():
        step=_unique_step(steps,name)
        if step.get("run")!=run: raise AssertionError(f"project_memory_workflow_missing_executable_step:{name}")

def validate()->tuple[int,int]:
    texts={name:read(name) for name in REQUIRED_FILES}
    for token in ("provider-neutral","multi-tenant","Zabbix 7.4","not a Zabbix UI"):
        if token not in texts["PROJECT-IDENTITY.md"]: raise AssertionError(f"project_memory_identity_missing:{token}")
    for token in ("Problem State","Health Projection","Alerting Policy/Evaluation","Responsibility / ACK","View/Read Evidence","ITSM","Automation","AIOps"):
        if token not in texts["E2E-SYSTEM-MAP.md"]: raise AssertionError(f"project_memory_e2e_missing:{token}")
    for token in ("PROVIDER ID != PLATFORM ID","JWT VALID != CURRENT AUTHORIZATION","PROBLEM != ALERT","ACKNOWLEDGEMENT != RESOLUTION","DELIVERED != VIEWED","HISTORICAL GENERATION != CURRENT AUTHORITY"):
        if token not in texts["CANONICAL-INVARIANTS.md"]: raise AssertionError(f"project_memory_invariant_missing:{token}")
    decision_count=validate_decision_register(texts["DECISION-REGISTER.md"]); state=texts["IMPLEMENTATION-STATE.md"]
    if not re.search(r"Canonical main SHA at this snapshot: `([0-9a-f]{40})`",state): raise AssertionError("project_memory_invalid_snapshot_sha")
    for token in ("AUTHORIZED","IMPLEMENTED","FOUNDATION","BLOCKED","#147","#148"):
        if token not in state: raise AssertionError(f"project_memory_state_missing:{token}")
    validate_human_operations(texts["HUMAN-OPERATIONS-MODEL.md"]); recovery=texts["RECOVERY-PLAYBOOK-FOR-NEW-CHAT.md"]
    for name in ("PROJECT-IDENTITY.md","IMPLEMENTATION-STATE.md","CANONICAL-INVARIANTS.md","DOMAIN-AUTHORITY-MAP.md","ROADMAP-DEPENDENCY-GRAPH.md"):
        if name not in recovery: raise AssertionError(f"project_memory_recovery_missing:{name}")
    roadmap=texts["ROADMAP-DEPENDENCY-GRAPH.md"]
    if "Alert Policy/Evaluation authorization" not in roadmap or "Alert lifecycle runtime" not in roadmap: raise AssertionError("project_memory_roadmap_missing_alert_dependency")
    if "automatic Alert create/resolve remains blocked" not in texts["OPEN-QUESTIONS-AND-DEFERRED.md"]: raise AssertionError("project_memory_deferred_missing_alert_block")
    if not WORKFLOW.is_file(): raise AssertionError("project_memory_workflow_missing")
    validate_project_memory_workflow(WORKFLOW.read_text(encoding="utf-8")); return len(REQUIRED_FILES),decision_count

if __name__=="__main__":
    files,decisions=validate(); print(f"project_memory=PASS files={files} decisions={decisions})")
