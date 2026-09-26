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

def strip_sql_comments(text):
    out=[]; i=0; quote=None; escape_string=False; body_delim=None
    while i<len(text):
      ch=text[i]
      if quote=="'":
        out.append(ch)
        if escape_string and ch=="\\" and i+1<len(text):
          out.append(text[i+1]); i+=2; continue
        if ch=="'" and i+1<len(text) and text[i+1]=="'":
          out.append(text[i+1]); i+=2; continue
        if ch=="'":
          quote=None; escape_string=False
        i+=1; continue
      if quote=='"':
        out.append(ch)
        if ch=='"' and i+1<len(text) and text[i+1]=='"':
          out.append(text[i+1]); i+=2; continue
        if ch=='"': quote=None
        i+=1; continue
      if ch in "Ee" and i+1<len(text) and text[i+1]=="'" and (i==0 or not (text[i-1].isalnum() or text[i-1]=="_")):
        out.append(ch); out.append("'"); quote="'"; escape_string=True; i+=2; continue
      if ch=="'":
        quote="'"; escape_string=False; out.append(ch); i+=1; continue
      if ch=='"':
        quote='"'; out.append(ch); i+=1; continue
      if ch=="$":
        delim_match=re.match(r"\$\$|\$[A-Za-z_][A-Za-z0-9_]*\$",text[i:])
        if delim_match:
          delim=delim_match.group(0)
          if body_delim==delim:
            out.append(delim); body_delim=None; i+=len(delim); continue
          if body_delim is not None:
            end=text.find(delim,i+len(delim))
            if end<0:
              out.append(text[i:]); break
            out.append(text[i:end+len(delim)])
            i=end+len(delim); continue
          prefix="".join(out)
          if re.search(r"(?:\bAS|\bDO(?:\s+LANGUAGE\s+(?:\"[^\"]+\"|[A-Za-z_][A-Za-z0-9_]*))?)\s*$",prefix,re.I):
            out.append(delim); body_delim=delim; i+=len(delim); continue
          end=text.find(delim,i+len(delim))
          if end<0:
            out.append(text[i:]); break
          out.append(text[i:end+len(delim)])
          i=end+len(delim); continue
      if text.startswith("--",i):
        end=text.find("\n",i)
        if end<0: break
        out.append("\n"); i=end+1; continue
      if text.startswith("/*",i):
        start=i; depth=1; i+=2
        while i<len(text) and depth:
          if text.startswith("/*",i):
            depth+=1; i+=2; continue
          if text.startswith("*/",i):
            depth-=1; i+=2; continue
          i+=1
        segment=text[start:i]
        out.append("\n"*segment.count("\n"))
        continue
      out.append(ch); i+=1
    return "".join(out)

def mask_sql_literals(text):
    out=[]; i=0; body_delim=None
    while i<len(text):
      if text[i] in "Ee" and i+1<len(text) and text[i+1]=="'" and (i==0 or not (text[i-1].isalnum() or text[i-1]=="_")):
        out.extend((" "," ")); i+=2
        while i<len(text):
          if text[i]=="\\" and i+1<len(text):
            out.extend((" "," ")); i+=2; continue
          if text[i]=="'" and i+1<len(text) and text[i+1]=="'":
            out.extend((" "," ")); i+=2; continue
          if text[i]=="'":
            out.append(" "); i+=1; break
          out.append("\n" if text[i]=="\n" else " "); i+=1
        continue
      if text[i]=="'":
        out.append(" "); i+=1
        while i<len(text):
          if text[i]=="'" and i+1<len(text) and text[i+1]=="'":
            out.extend((" "," ")); i+=2; continue
          if text[i]=="'":
            out.append(" "); i+=1; break
          out.append("\n" if text[i]=="\n" else " "); i+=1
        continue
      if text[i]=="$":
        delim_match=re.match(r"\$\$|\$[A-Za-z_][A-Za-z0-9_]*\$",text[i:])
        if delim_match:
          delim=delim_match.group(0)
          if body_delim==delim:
            out.append(delim); body_delim=None; i+=len(delim); continue
          if body_delim is not None:
            end=text.find(delim,i+len(delim))
            if end>=0:
              segment=text[i:end+len(delim)]
              out.extend("\n" if c=="\n" else " " for c in segment)
              i=end+len(delim); continue
          prefix="".join(out)
          if re.search(r"(?:\bAS|\bDO(?:\s+LANGUAGE\s+(?:\"[^\"]+\"|[A-Za-z_][A-Za-z0-9_]*))?)\s*$",prefix,re.I):
            out.append(delim); body_delim=delim; i+=len(delim); continue
          end=text.find(delim,i+len(delim))
          if end>=0:
            segment=text[i:end+len(delim)]
            out.extend("\n" if c=="\n" else " " for c in segment)
            i=end+len(delim); continue
      out.append(text[i]); i+=1
    return "".join(out)



def semantic_errors(path,text,p):
    if Path(path).suffix.lower() not in EXECUTABLE_SUFFIXES:return []
    out=[]; f=fold(text)
    for m in p.get("forbidden_code_markers") or []:
      if fold(m) in f:out.append(f"forbidden G11+ semantic marker '{m}' in {path}")
    if SQL_MUTATION_RE.search(text):
      out.append(f"direct SQL/schema mutation is forbidden in G10 application executable artifact: {path}")
    return out

def function_block(text,name):
    executable=strip_sql_comments(text)
    start_match=re.search(
      rf"\bCREATE\s+(?:OR\s+REPLACE\s+)?FUNCTION\s+(?:itsm|\"itsm\")\s*\.\s*(?:{re.escape(name)}|\"{re.escape(name)}\")\s*\(",
      executable,re.I
    )
    if not start_match:return ""
    next_match=re.search(
      r"\bCREATE\s+(?:OR\s+REPLACE\s+)?FUNCTION\s+(?:(?:[A-Za-z_][A-Za-z0-9_]*|\"[^\"]+\")\s*\.\s*)?(?:[A-Za-z_][A-Za-z0-9_]*|\"[^\"]+\")\s*\(",
      executable[start_match.end():],re.I
    )
    if not next_match:return executable[start_match.start():]
    end=start_match.end()+next_match.start()
    return executable[start_match.start():end]

def function_occurrences(text,name):
    executable=strip_sql_comments(text)
    return list(re.finditer(
      rf"\bCREATE\s+(?:OR\s+REPLACE\s+)?FUNCTION\s+(?:itsm|\"itsm\")\s*\.\s*(?:{re.escape(name)}|\"{re.escape(name)}\")\s*\(",
      executable,re.I
    ))

def inside_static_false(block,pos):
    prefix=block[:pos]
    false_starts=[m.start() for m in re.finditer(r"\bIF\s+(?:FALSE|0\s*=\s*1|1\s*=\s*0)\s+THEN\b",prefix,re.I)]
    if not false_starts:return False
    last=false_starts[-1]
    return not re.search(r"\bEND\s+IF\s*;",prefix[last:],re.I)

def inside_any_if(block,pos):
    prefix=block[:pos]
    tokens=list(re.finditer(r"\bIF\b[^;]*?\bTHEN\b|\bEND\s+IF\s*;",prefix,re.I|re.S))
    depth=0
    for token in tokens:
        if re.fullmatch(r"\bEND\s+IF\s*;",token.group(0),re.I|re.S):
            depth=max(0,depth-1)
        else:
            depth+=1
    return depth>0

def inside_any_case(block,pos):
    prefix=block[:pos]
    tokens=list(re.finditer(r"\bEND\s+CASE\s*;|\bCASE\b",prefix,re.I))
    depth=0
    for token in tokens:
        if re.fullmatch(r"\bEND\s+CASE\s*;",token.group(0),re.I):
            depth=max(0,depth-1)
        else:
            depth+=1
    return depth>0

def inside_any_loop(block,pos):
    prefix=block[:pos]
    tokens=list(re.finditer(r"\bEND\s+LOOP\s*;|\bLOOP\b",prefix,re.I))
    depth=0
    for token in tokens:
        if re.fullmatch(r"\bEND\s+LOOP\s*;",token.group(0),re.I):
            depth=max(0,depth-1)
        else:
            depth+=1
    return depth>0

def inside_exception_handler(block,pos):
    prefix=block[:pos]
    tokens=list(re.finditer(r"\bBEGIN\b|\bEXCEPTION\b|\bEND\s*;",prefix,re.I))
    stack=[]
    for token in tokens:
        value=token.group(0).upper()
        if value=="BEGIN":
            stack.append(False)
        elif value=="EXCEPTION":
            if re.search(r"\bRAISE\s*$",prefix[:token.start()],re.I):
                continue
            if stack: stack[-1]=True
        else:
            if stack: stack.pop()
    return any(stack)

def unconditional_terminator_before(block,pos):
    for match in re.finditer(r"\b(?:RETURN|RAISE)\b",block[:pos],re.I):
        if not inside_any_if(block,match.start()) and not inside_any_case(block,match.start()) and not inside_any_loop(block,match.start()) and not inside_exception_handler(block,match.start()):
            return True
    return False

def sql_errors(text,p):
    executable=strip_sql_comments(text)
    out=[]
    if re.search(r"\bSET\s+(?:(?:LOCAL|SESSION)\s+)?standard_conforming_strings\b",text,re.I):
      out.append("G10 exact SQL cannot mutate standard_conforming_strings because comment/literal attestation requires fixed standard string semantics")
    f=fold(executable)
    for m in ("incident_id","alert_id","incident_transition","incident_assignment","incident_comment","provider_link","sync_outbox","tenant_id"):
      if fold(m) not in f:out.append(f"G10 exact SQL missing marker: {m}")

    validated_functions=("g10_get_incident","g10_next_sync_candidate","g10_create_incident","g10_transition_incident")
    context_scan=executable
    # Canonical SECURITY DEFINER/INVOKER function configuration is definition-time metadata,
    # not a mutable session statement. Mask only the exact attached function SET clauses.
    context_scan=re.sub(
      r"(CREATE\s+(?:OR\s+REPLACE\s+)?FUNCTION\b.*?\bLANGUAGE\s+plpgsql\b(?:\s+SECURITY\s+(?:DEFINER|INVOKER))?)"
      r"\s+SET\s+search_path\s*=\s*pg_catalog\s*,\s*itsm(?:\s*,\s*alerting)?\s+(?=AS\s+\$)",
      lambda m:m.group(1)+" ",
      context_scan,flags=re.I|re.S
    )
    # Canonical tenant RLS binding is transaction-local (third argument TRUE) and bounded
    # to the already-authorized jlmirror.tenant_id key. Any other set_config remains forbidden.
    context_scan=re.sub(
      r"\bPERFORM\s+(?:pg_catalog\s*\.\s*)?(?:set_config|\"set_config\")\s*\(\s*'jlmirror\.tenant_id'\s*,\s*p_tenant_id\s*,\s*TRUE\s*\)\s*;",
      " ",
      context_scan,flags=re.I
    )
    context_without_literals=mask_sql_literals(context_scan)
    executable_without_literals=mask_sql_literals(executable)
    if re.search(r'\b(?:pg_catalog\s*\.\s*)?(?:set_config|"set_config")\s*\(',context_without_literals,re.I):
      out.append("G10 exact SQL forbids noncanonical executable set_config because mutable session semantics must remain statically attestable")
    if re.search(r"\bSET\s+(?:(?:LOCAL|SESSION)\s+)?search_path\b",context_without_literals,re.I) or re.search(r"\bSET\s+SCHEMA\b",context_without_literals,re.I):
      out.append("G10 exact SQL forbids statement-level search_path/SET SCHEMA changes because mutation targets must remain explicitly qualified")
    if re.search(r"\bEXECUTE\b(?!\s+(?:FUNCTION\b|ON\s+FUNCTION\b))",context_without_literals,re.I):
      out.append("G10 exact SQL forbids dynamic EXECUTE because validated DDL and guard semantics must remain statically attestable")
    for name in validated_functions:
      for ident_match in re.finditer(
        r'\b(?:CREATE\s+(?:OR\s+REPLACE\s+)?|DROP\s+(?:IF\s+EXISTS\s+)?|ALTER\s+)FUNCTION\s+(?P<schema>"[^"]+"|[A-Za-z_][A-Za-z0-9_]*)\s*\.\s*(?P<fn>"[^"]+"|[A-Za-z_][A-Za-z0-9_]*)\s*\(',
        executable,re.I
      ):
        schema_token,fn_token=ident_match.group("schema"),ident_match.group("fn")
        if schema_token.startswith('"'):
          quoted_schema=schema_token[1:-1]
          if quoted_schema.casefold()=="itsm" and quoted_schema!="itsm":
            out.append(f'G10 quoted canonical schema identifier must preserve exact case: "{quoted_schema}"')
        if fn_token.startswith('"'):
          quoted_name=fn_token[1:-1]
          if quoted_name.casefold()==name.casefold() and quoted_name!=name:
            out.append(f'G10 quoted validated function identifier must preserve exact case: "{quoted_name}"')
      if len(function_occurrences(executable,name))!=1:
        out.append(f"G10 validated function must have exactly one definition: {name}")

      if re.search(rf"\bDROP\s+FUNCTION\b[^;]*\b(?:itsm|\"itsm\")\s*\.\s*(?:{re.escape(name)}|\"{re.escape(name)}\")\s*\(",executable,re.I|re.S):
        out.append(f"G10 validated function cannot be dropped/recreated inside the exact SQL artifact: {name}")

      if re.search(rf"\bALTER\s+(?:FUNCTION|ROUTINE)\b[^;]*\b(?:itsm|\"itsm\")\s*\.\s*(?:{re.escape(name)}|\"{re.escape(name)}\")\s*\([^;]*\)\s+RENAME\s+TO\b",executable,re.I|re.S):
        out.append(f"G10 validated function cannot be renamed inside the exact SQL artifact: {name}")
      if re.search(rf"\bALTER\s+(?:FUNCTION|ROUTINE)\b[^;]*\bRENAME\s+TO\s+(?:{re.escape(name)}|\"{re.escape(name)}\")\b",executable,re.I|re.S):
        out.append(f"G10 validated function name cannot be installed by rename: {name}")
      if re.search(rf"\bALTER\s+(?:FUNCTION|ROUTINE)\b[^;]*\b(?:itsm|\"itsm\")\s*\.\s*(?:{re.escape(name)}|\"{re.escape(name)}\")\s*\([^;]*\)\s+SET\s+SCHEMA\b",executable,re.I|re.S):
        out.append(f"G10 validated function cannot be moved to another schema: {name}")

      unqualified_ddl=(
        rf"\bCREATE\s+(?:OR\s+REPLACE\s+)?FUNCTION\s+(?!itsm\.){re.escape(name)}\s*\(",
        rf"\bDROP\s+FUNCTION\s+(?:IF\s+EXISTS\s+)?(?!itsm\.){re.escape(name)}\s*\(",
        rf"\bALTER\s+(?:FUNCTION|ROUTINE)\s+(?!itsm\.){re.escape(name)}\s*\("
      )
      if any(re.search(pattern,executable,re.I|re.S) for pattern in unqualified_ddl):
        out.append(f"G10 validated function DDL must be explicitly itsm-qualified: {name}")

    incident_read=function_block(executable,"g10_get_incident")
    incident_read_exec=mask_sql_literals(incident_read)
    alert_match=re.search(
      r"SELECT\s+to_jsonb\s*\(\s*x\s*\)\s+INTO\s+v_alert\s+FROM\s*\(\s*"
      r"SELECT\s+alert_id\s*,\s*lifecycle_state\s*,\s*(?:[A-Za-z_][A-Za-z0-9_]*\s*\.\s*)?opened_at\s*,\s*resolved_at\s+"
      r"FROM\s+alerting\.alert\s+WHERE\s+tenant_id\s*=\s*p_tenant_id\s+AND\s+alert_id\s*=\s*v_incident\s*->>\s*'alert_id'\s*"
      r"\)\s*x\s*;",
      incident_read,re.I|re.S
    )
    alert_exec=False
    if alert_match:
      span=incident_read_exec[alert_match.start():alert_match.end()]
      alert_exec=bool(
        re.search(r"SELECT\s+to_jsonb\s*\(\s*x\s*\)\s+INTO\s+v_alert\s+FROM\s*\(",span,re.I|re.S)
        and re.search(r"SELECT\s+alert_id\s*,\s*lifecycle_state\s*,\s*(?:[A-Za-z_][A-Za-z0-9_]*\s*\.\s*)?opened_at\s*,\s*resolved_at\s+FROM\s+alerting\.alert\b",span,re.I|re.S)
      )
    if not alert_match or not alert_exec:
      out.append("G10 Incident Alert summary must directly project executable alerting.alert.opened_at with canonical tenant+alert provenance")

    discovery=function_block(executable,"g10_next_sync_candidate")
    discovery_exec=mask_sql_literals(discovery)
    pending_branch=r"\(\s*o\.sync_state\s*=\s*'pending'\s+AND\s+o\.available_at\s*<=\s*transaction_timestamp\s*\(\s*\)\s*\)"
    expired_branch=r"\(\s*o\.sync_state\s*=\s*'dispatching'\s+AND\s+o\.claim_expires_at\s*<=\s*transaction_timestamp\s*\(\s*\)\s*\)"
    candidate_query=re.search(
      r"SELECT\s+to_jsonb\s*\(\s*x\s*\)\s+INTO\s+v_result\s+FROM\s*\((?P<body>.*?)\)\s*x\s*;\s*"
      r"RETURN\s+v_result\s*;",
      discovery,re.I|re.S
    )
    if not candidate_query:
      out.append("G10 worker discovery must populate and return v_result from the bounded candidate query")
    elif not re.match(r"SELECT\s+to_jsonb\s*\(\s*x\s*\)\s+INTO\s+v_result\s+FROM\s*\(",discovery_exec[candidate_query.start():],re.I|re.S) or not re.search(r"RETURN\s+v_result\s*;",discovery_exec[candidate_query.start():candidate_query.end()],re.I|re.S):
      out.append("G10 worker discovery evidence must be executable SQL, not literal contents")
    elif inside_static_false(discovery_exec,candidate_query.start()) or inside_any_if(discovery_exec,candidate_query.start()) or inside_any_case(discovery_exec,candidate_query.start()) or inside_any_loop(discovery_exec,candidate_query.start()) or inside_exception_handler(discovery_exec,candidate_query.start()) or unconditional_terminator_before(discovery_exec,candidate_query.start()):
      out.append("G10 worker candidate query must be top-level reachable on the valid-input path before any unconditional terminator")
    else:
      candidate_body=candidate_query.group("body")
      canonical_source=re.search(
        r"\bFROM\s+itsm\.incident_sync_outbox\s+o\b",
        candidate_body,re.I
      )
      reachable_expired=re.search(
        r"WHERE\s+o\.tenant_id\s*=\s*p_tenant_id\s+AND\s*\(\s*"+
        pending_branch+r"\s*OR\s*"+expired_branch+
        r"\s*\)\s*(?:ORDER\s+BY\b.*?\s+)?LIMIT\s+1\s*$",
        candidate_body,re.I|re.S
      )
      source_to_filter=(candidate_body[canonical_source.end():reachable_expired.start()] if canonical_source and reachable_expired else "")
      canonical_payload_join=re.fullmatch(
        r"\s*(?:JOIN\s+itsm\.incident\s+i\s+ON\s+i\.tenant_id\s*=\s*o\.tenant_id\s+AND\s+i\.incident_id\s*=\s*o\.incident_id\s*)?",
        source_to_filter,re.I|re.S
      )
      if not canonical_source or not reachable_expired or canonical_source.start()>=reachable_expired.start() or not canonical_payload_join:
        out.append("G10 returned worker candidate must read the canonical sync-outbox relation with only the tenant-bound Incident payload join and the complete tenant-scoped pending OR expired-dispatching filter")

    membership_loop=None; membership_do_body=""; membership_loop_start=-1; membership_post_start=-1
    for do_match in re.finditer(r"\bDO\s+\$\$(?P<body>.*?)\$\$\s*;",executable,re.I|re.S):
      do_body=do_match.group("body")
      candidate_loop=re.search(
        r"FOR\s+v_role\s+IN\s+SELECT\s+\*\s+FROM\s+pg_catalog\.pg_roles\s+WHERE\s+rolname\s+IN\s*\("
        r"\s*'jlmirror_g10_itsm_executor'\s*,\s*'jlmirror_g10_itsm_app_invoker'\s*,\s*'jlmirror_g10_itsm_worker_invoker'\s*"
        r"\)\s+LOOP(?P<body>.*?)END\s+LOOP\s*;",
        do_body,re.I|re.S
      )
      if candidate_loop:
        membership_loop=candidate_loop
        membership_do_body=do_body
        membership_loop_start=candidate_loop.start()
        membership_post_start=do_match.start("body")+candidate_loop.end()
        break
    loop_body=membership_loop.group("body") if membership_loop else ""
    membership_do_exec=mask_sql_literals(membership_do_body)
    loop_exec=mask_sql_literals(loop_body)
    attribute_guard=re.search(
      r"IF\s+v_role\.rolcanlogin\s+OR\s+v_role\.rolsuper\s+OR\s+v_role\.rolcreatedb\s+OR\s+v_role\.rolcreaterole\s+"
      r"OR\s+v_role\.rolinherit\s+OR\s+v_role\.rolreplication\s+OR\s+v_role\.rolbypassrls\s+THEN\s+"
      r"RAISE\s+EXCEPTION\s+[^;]+,\s*v_role\.rolname\s*;\s*END\s+IF\s*;",
      loop_exec,re.I|re.S
    )
    membership_guard=re.search(
      r"IF\s+EXISTS\s*\(\s*SELECT\s+1\s+FROM\s+pg_catalog\.pg_auth_members\s+WHERE\s+"
      r"(?:roleid\s*=\s*v_role\.oid\s+OR\s+member\s*=\s*v_role\.oid|"
      r"member\s*=\s*v_role\.oid\s+OR\s+roleid\s*=\s*v_role\.oid)"
      r"\s*\)\s*THEN\s+RAISE\s+EXCEPTION\s+",
      loop_exec,re.I|re.S
    )
    if not membership_loop or not attribute_guard or not membership_guard:
      out.append("G10 privileged-role preflight must use the exact literal three-role loop with complete unsafe-attribute and membership guards")
    elif inside_any_if(membership_do_exec,membership_loop_start) or inside_any_case(membership_do_exec,membership_loop_start) or inside_any_loop(membership_do_exec,membership_loop_start) or inside_exception_handler(membership_do_exec,membership_loop_start) or unconditional_terminator_before(membership_do_exec,membership_loop_start):
      out.append("G10 privileged-role membership loop must be top-level and reachable during installation")
    elif inside_any_if(loop_exec,attribute_guard.start()) or inside_any_case(loop_exec,attribute_guard.start()) or inside_any_loop(loop_exec,attribute_guard.start()) or inside_exception_handler(loop_exec,attribute_guard.start()) or unconditional_terminator_before(loop_exec,attribute_guard.start()):
      out.append("G10 privileged-role unsafe-attribute guard must be top-level and executable for every protected role")
    elif inside_any_if(loop_exec,membership_guard.start()) or inside_any_case(loop_exec,membership_guard.start()) or inside_any_loop(loop_exec,membership_guard.start()) or inside_exception_handler(loop_exec,membership_guard.start()) or re.search(r"\b(?:CONTINUE|EXIT)\b(?:\s+WHEN\s+[^;]+)?\s*;",loop_exec[:membership_guard.start()],re.I|re.S):
      out.append("G10 privileged-role membership guard must be top-level and executable for every role in the exact three-role loop")

    if membership_post_start>=0:
      post_membership=executable[membership_post_start:]
      protected_roles=r"(?:jlmirror_g10_itsm_executor|jlmirror_g10_itsm_app_invoker|jlmirror_g10_itsm_worker_invoker|\"jlmirror_g10_itsm_executor\"|\"jlmirror_g10_itsm_app_invoker\"|\"jlmirror_g10_itsm_worker_invoker\")"
      membership_mutation=False
      for stmt in re.finditer(r"\b(?P<verb>GRANT|REVOKE)\b(?P<body>[^;]*);",post_membership,re.I|re.S):
        body=stmt.group("body")
        body_without_quoted=re.sub(r'"(?:[^"]|"")*"',lambda m:" "*len(m.group(0)),body)
        target_kw="TO" if stmt.group("verb").upper()=="GRANT" else "FROM"
        target_match=re.search(rf"\b{target_kw}\b",body_without_quoted,re.I)
        if not target_match:
          continue
        before_target=body_without_quoted[:target_match.start()]
        if re.search(r"\bON\b",before_target,re.I):
          continue
        if re.search(protected_roles,body,re.I):
          membership_mutation=True
          break
      membership_change=(
        r"\bCREATE\s+(?:ROLE|USER)\b[^;]*\b(?:IN\s+ROLE|ROLE|ADMIN)\b[^;]*;",
        r"\bALTER\s+GROUP\b[^;]*\b(?:ADD|DROP)\s+USER\b[^;]*;"
      )
      role_attribute_change=re.search(
        rf"\bALTER\s+(?:ROLE|USER)\s+{protected_roles}(?=\s|;)[^;]*;",
        post_membership,re.I|re.S
      )
      protected_role_create=re.search(
        rf"\bCREATE\s+(?:ROLE|USER|GROUP)\s+{protected_roles}(?=\s|;)[^;]*;",
        post_membership,re.I|re.S
      )
      if membership_mutation or any(re.search(pattern,post_membership,re.I) for pattern in membership_change) or role_attribute_change or protected_role_create:
        out.append("G10 protected roles cannot be created, have membership changed, or have role attributes changed after the final installation membership preflight")

    create=function_block(executable,"g10_create_incident")
    create_exec=mask_sql_literals(create)
    lock_match=re.search(
      r"\bPERFORM\s+pg_advisory_xact_lock\s*\(\s*hashtextextended\s*\(\s*p_tenant_id\s*\|\|\s*chr\s*\(\s*31\s*\)\s*\|\|\s*p_logical_action_id\s*,\s*10\s*\)\s*\)\s*;",
      create_exec,re.I|re.S
    )
    lookup_match=re.search(
      r"SELECT\s+\*\s+INTO\s+v_existing\s+FROM\s+itsm\.incident\s+"
      r"WHERE\s+tenant_id\s*=\s*p_tenant_id\s+AND\s+logical_action_id\s*=\s*p_logical_action_id\s*;",
      create_exec,re.I|re.S
    )
    if not lock_match or not lookup_match or lock_match.start()>=lookup_match.start():
      out.append("G10 Incident create must acquire the logical-action advisory lock before equivalence lookup")
    elif unconditional_terminator_before(create_exec,lock_match.start()) or inside_any_if(create_exec,lock_match.start()) or inside_any_case(create_exec,lock_match.start()) or inside_any_loop(create_exec,lock_match.start()) or inside_exception_handler(create_exec,lock_match.start()):
      out.append("G10 Incident create logical-action lock must be top-level and dominate the equivalence lookup on the valid-input path")
    elif unconditional_terminator_before(create_exec,lookup_match.start()) or inside_any_if(create_exec,lookup_match.start()) or inside_any_case(create_exec,lookup_match.start()) or inside_any_loop(create_exec,lookup_match.start()) or inside_exception_handler(create_exec,lookup_match.start()):
      out.append("G10 Incident create equivalence lookup must be top-level reachable on the valid-input path")

    create_replay_bound=re.search(
      r"SELECT\s+\*\s+INTO\s+v_existing\s+FROM\s+itsm\.incident\s+"
      r"WHERE\s+tenant_id\s*=\s*p_tenant_id\s+AND\s+logical_action_id\s*=\s*p_logical_action_id\s*;\s*"
      r"IF\s+FOUND\s+THEN\s+"
      r"IF\s+v_existing\.content_hash\s*(?:<>|IS\s+DISTINCT\s+FROM)\s*v_hash\s+THEN\s+"
      r"RAISE\s+EXCEPTION\s+'g10\.incident_equivalence_conflict'\s*;\s*END\s+IF\s*;\s*"
      r"RETURN\s+jsonb_build_object\s*\((?P<return_body>.*?)\)\s*;\s*END\s+IF\s*;",
      create,re.I|re.S
    )
    if not create_replay_bound:
      out.append("G10 Incident create replay handler must reject content mismatch before duplicate success")
    else:
      create_return_body=create_replay_bound.group("return_body")
      if not re.search(r"'duplicate'\s*,\s*TRUE\b",create_return_body,re.I|re.S):
        out.append("G10 Incident create replay handler must return duplicate=true only after equivalence is proven")

    transition=function_block(executable,"g10_transition_incident")
    transition_exec=mask_sql_literals(transition)
    replay_bound=re.search(
      r"SELECT\s+\*\s+INTO\s+v_existing_transition\s+FROM\s+itsm\.incident_transition\s+"
      r"WHERE\s+tenant_id\s*=\s*p_tenant_id\s+AND\s+incident_id\s*=\s*p_incident_id\s+"
      r"AND\s+logical_action_id\s*=\s*p_logical_action_id\s*;\s*"
      r"IF\s+FOUND\s+THEN\s+"
      r"IF\s+v_existing_transition\.to_state\s+IS\s+DISTINCT\s+FROM\s+p_target_state\s+THEN\s+"
      r"RAISE\s+EXCEPTION\s+'g10\.transition_equivalence_conflict'\s*;\s*END\s+IF\s*;\s*"
      r"RETURN\s+jsonb_build_object\s*\((?P<return_body>.*?)\)\s*;\s*END\s+IF\s*;",
      transition,re.I|re.S
    )
    if not replay_bound:
      out.append("G10 transition replay must bind FOUND to the same tenant+incident+logical-action lookup before conflict/duplicate handling")
    elif not re.match(r"SELECT\s+\*\s+INTO\s+v_existing_transition\b",transition_exec[replay_bound.start():],re.I|re.S) or not re.search(r"RETURN\s+jsonb_build_object\s*\(",transition_exec[replay_bound.start():replay_bound.end()],re.I|re.S):
      out.append("G10 transition replay evidence must be executable SQL, not literal contents")
    elif inside_any_if(transition_exec,replay_bound.start()) or inside_any_case(transition_exec,replay_bound.start()) or inside_any_loop(transition_exec,replay_bound.start()) or inside_exception_handler(transition_exec,replay_bound.start()) or unconditional_terminator_before(transition_exec,replay_bound.start()):
      out.append("G10 transition replay lookup/conflict block must be top-level reachable on the main transition path")
    elif not re.search(r"'duplicate'\s*,\s*TRUE",replay_bound.group("return_body"),re.I):
      out.append("G10 transition replay lookup must return explicit duplicate success only after equivalence validation")

    allowed_rel={x.casefold() for x in p["exact_sql_allowed_relations"]}
    for schema,table in re.findall(r'\bcreate\s+table(?:\s+if\s+not\s+exists)?\s+"?([a-zA-Z_][\w]*)"?\s*\.\s*"?([a-zA-Z_][\w]*)"?',executable,re.I):
      rel=f"{schema}.{table}".casefold()
      if schema.casefold()=="itsm" and rel not in allowed_rel:
        out.append(f"G10 exact SQL creates unauthorized itsm relation: {schema}.{table}")
    external_schema=r'(?:"(?:alerting|human_operations|notification|monitoring)"|(?:alerting|human_operations|notification|monitoring))'
    cross_domain_write_privileges=r"(?:ALL(?:\s+PRIVILEGES)?|INSERT|UPDATE|DELETE|TRUNCATE|REFERENCES|TRIGGER)"
    cross_domain_schema_write_privileges=r"(?:ALL(?:\s+PRIVILEGES)?|CREATE)"
    cross_domain_patterns=(
      rf"\bINSERT\s+INTO\s+{external_schema}\s*\.",
      rf"\bUPDATE\s+(?:ONLY\s+)?{external_schema}\s*\.",
      rf"\bDELETE\s+FROM\s+(?:ONLY\s+)?{external_schema}\s*\.",
      rf"\bMERGE\s+INTO\s+(?:ONLY\s+)?{external_schema}\s*\.",
      rf"\bCOPY\s+{external_schema}\s*\.\s*(?:\"[^\"]+\"|[A-Za-z_][A-Za-z0-9_]*)\s*(?:\([^;]*?\))?\s+FROM\b",
      rf"\bTRUNCATE\b[^;]*{external_schema}\s*\.",
      rf"\b(?:CREATE|DROP)\s+(?:TABLE|VIEW|MATERIALIZED\s+VIEW|SEQUENCE|FUNCTION|PROCEDURE|ROUTINE|TYPE|DOMAIN)\s+(?:IF\s+(?:NOT\s+)?EXISTS\s+)?{external_schema}\s*\.",
      rf"\bALTER\s+(?:TABLE|VIEW|MATERIALIZED\s+VIEW|SEQUENCE)\s+(?:IF\s+EXISTS\s+)?(?:ONLY\s+)?{external_schema}\s*\.",
      rf"\bCREATE\s+(?:UNIQUE\s+)?INDEX\b[^;]*\bON\s+(?:ONLY\s+)?{external_schema}\s*\.",
      rf"\bCREATE\s+(?:CONSTRAINT\s+)?TRIGGER\b[^;]*\bON\s+(?:ONLY\s+)?{external_schema}\s*\.",
      rf"\bDROP\s+TRIGGER\b[^;]*\bON\s+(?:ONLY\s+)?{external_schema}\s*\.",
      rf"\bCREATE\s+(?:OR\s+REPLACE\s+)?RULE\b[^;]*\bAS\s+ON\s+(?:SELECT|INSERT|UPDATE|DELETE)\s+TO\s+(?:ONLY\s+)?{external_schema}\s*\.",
      rf"\bDROP\s+RULE\b[^;]*\bON\s+(?:ONLY\s+)?{external_schema}\s*\.",
      rf"\bCREATE\s+POLICY\b[^;]*\bON\s+(?:ONLY\s+)?{external_schema}\s*\.",
      rf"\bALTER\s+POLICY\b[^;]*\bON\s+(?:ONLY\s+)?{external_schema}\s*\.",
      rf"\bDROP\s+POLICY\b[^;]*\bON\s+(?:ONLY\s+)?{external_schema}\s*\.",
      rf"\b(?:CREATE|ALTER|DROP)\s+SCHEMA\s+(?:IF\s+(?:NOT\s+)?EXISTS\s+)?{external_schema}\b",
      rf"\bGRANT\b(?=[^;]*\b{cross_domain_write_privileges}\b[^;]*\bON\b)[^;]*\bON\s+(?:TABLE\s+)?(?:ONLY\s+)?{external_schema}\s*\.",
      rf"\bGRANT\b(?=[^;]*\b{cross_domain_write_privileges}\b[^;]*\bON\b)[^;]*\bON\s+ALL\s+TABLES\s+IN\s+SCHEMA\s+{external_schema}\b",
      rf"\bGRANT\b(?=[^;]*\b{cross_domain_schema_write_privileges}\b[^;]*\bON\b)[^;]*\bON\s+SCHEMA\s+{external_schema}\b"
    )
    for pattern in cross_domain_patterns:
      if re.search(pattern,executable_without_literals,re.I|re.S):
        out.append(f"G10 SQL contains forbidden cross-domain mutation: {pattern}")
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
