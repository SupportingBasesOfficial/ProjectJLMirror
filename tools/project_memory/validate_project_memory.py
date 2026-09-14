from __future__ import annotations

import ast
import os
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MEMORY = ROOT / "docs" / "00-foundation" / "project-memory"
WORKFLOW = ROOT / ".github" / "workflows" / "project-memory-governance.yml"
DECISION_REGISTER_REL = "docs/00-foundation/project-memory/DECISION-REGISTER.md"

REQUIRED_FILES = (
    "PROJECT-IDENTITY.md", "E2E-SYSTEM-MAP.md", "DOMAIN-AUTHORITY-MAP.md", "CANONICAL-INVARIANTS.md",
    "DECISION-REGISTER.md", "IMPLEMENTATION-STATE.md", "ACCEPTED-PR-CHAIN.md", "ROADMAP-DEPENDENCY-GRAPH.md",
    "GLOSSARY.md", "HUMAN-OPERATIONS-MODEL.md", "OPEN-QUESTIONS-AND-DEFERRED.md", "RECOVERY-PLAYBOOK-FOR-NEW-CHAT.md",
)
BASELINE_DECISION_MEANINGS = {
    "JLM-DEC-001": "JLMirror is provider-neutral, not a Zabbix UI",
    "JLM-DEC-002": "Tenant isolation is foundational",
    "JLM-DEC-003": "Provider identity is not platform identity",
    "JLM-DEC-004": "Source generation participates in provider-evidence scope",
    "JLM-DEC-005": "PostgreSQL is durable business truth",
    "JLM-DEC-006": "Async delivery is at-least-once",
    "JLM-DEC-007": "Browser access crosses mandatory BFF boundary",
    "JLM-DEC-008": "Problem State and Health Projection are distinct Monitoring concepts",
    "JLM-DEC-009": "Healthy requires authoritative completeness",
    "JLM-DEC-010": "Monitoring->Alerting events are invalidation/resync only",
    "JLM-DEC-011": "Alert is platform-owned actionable occurrence",
    "JLM-DEC-012": "Alert v1 lifecycle is `active \\| resolved`; resolved is terminal",
    "JLM-DEC-013": "Effectful Alert lifecycle transitions require immutable policy ID/version",
    "JLM-DEC-014": "Alert source family is explicit",
    "JLM-DEC-015": "Human operations use orthogonal state dimensions, not one giant status",
    "JLM-DEC-016": "Critical human workflows must provide authoritative visibility evidence",
    "JLM-DEC-017": "Repository truth outranks assistant/chat memory",
}
BASELINE_DECISION_IDS = tuple(BASELINE_DECISION_MEANINGS)
DECISION_ID_RE = re.compile(r"JLM-DEC-\d{3}")
DECISION_SUPERSESSION_CLAUSE_RE = re.compile(r"\bsuperseded\s+by\b", re.IGNORECASE)
DECISION_SUPERSESSION_TARGET_RE = re.compile(r"\bsuperseded\s+by\s+([^\s|,;.]+)", re.IGNORECASE)
FENCE_OPEN_RE = re.compile(r"^[ ]{0,3}(`{3,}|~{3,})")
FENCE_CLOSE_RE = re.compile(r"^[ ]{0,3}(`{3,}|~{3,})[ \t]*$")
RAW_HTML_CONTAINER_OPEN_RE = re.compile(r"^[ ]{0,3}<(?P<tag>script|pre|style|textarea)(?:\s|>|$)", re.IGNORECASE)
RAW_HTML_BLOCK_OPEN_RE = re.compile(
    r"^[ ]{0,3}</?(?:address|article|aside|base|basefont|blockquote|body|caption|center|col|colgroup|dd|details|dialog|dir|div|dl|dt|fieldset|figcaption|figure|footer|form|frame|frameset|h[1-6]|head|header|hr|html|iframe|legend|li|link|main|menu|menuitem|nav|noframes|ol|optgroup|option|p|param|search|section|summary|table|tbody|td|tfoot|th|thead|title|tr|track|ul)(?:\s|/?>|$)",
    re.IGNORECASE,
)
RAW_HTML_PROCESSING_OPEN_RE = re.compile(r"^[ ]{0,3}<\?")
RAW_HTML_CDATA_OPEN_RE = re.compile(r"^[ ]{0,3}<!\[CDATA\[")
RAW_HTML_DECLARATION_OPEN_RE = re.compile(r"^[ ]{0,3}<![A-Z]")
RAW_HTML_GENERIC_TAG_RE = re.compile(
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
EXPECTED_STEP_NAMES = (
    "Resolve exact analyzed HEAD",
    "Checkout exact analyzed HEAD",
    "Verify exact commit identity",
    "Validate canonical project memory",
    "Test canonical project memory",
    "Falsify canonical project-memory guardrails",
    "Validate repository structure and workflow safety",
)


def read(name: str) -> str:
    path = MEMORY / name
    if not path.is_file():
        raise AssertionError(f"project_memory_missing_file:{name}")
    text = path.read_text(encoding="utf-8")
    if len(text.strip()) < 200:
        raise AssertionError(f"project_memory_file_too_small:{name}")
    return text


def _visible_markdown_lines(text: str) -> list[str]:
    visible: list[str] = []
    in_comment = False
    fence_char: str | None = None
    fence_len = 0
    raw_html_container: str | None = None
    raw_html_until_blank = False
    raw_html_until_token: str | None = None
    for raw in text.splitlines():
        if raw_html_container is not None:
            if re.search(rf"</{re.escape(raw_html_container)}\s*>", raw, re.IGNORECASE):
                raw_html_container = None
            continue
        if raw_html_until_token is not None:
            if raw_html_until_token in raw:
                raw_html_until_token = None
            continue
        if raw_html_until_blank:
            if not raw.strip():
                raw_html_until_blank = False
            continue
        if fence_char is not None:
            closing = FENCE_CLOSE_RE.match(raw)
            if closing:
                marker = closing.group(1)
                if marker[0] == fence_char and len(marker) >= fence_len:
                    fence_char = None
                    fence_len = 0
            continue
        container = RAW_HTML_CONTAINER_OPEN_RE.match(raw)
        if container:
            tag = container.group("tag").lower()
            if re.search(rf"</{re.escape(tag)}\s*>", raw, re.IGNORECASE) is None:
                raw_html_container = tag
            continue
        if RAW_HTML_CDATA_OPEN_RE.match(raw):
            if "]]>" not in raw:
                raw_html_until_token = "]] >".replace(" ", "")
            continue
        if RAW_HTML_PROCESSING_OPEN_RE.match(raw):
            if "?>" not in raw:
                raw_html_until_token = "?>"
            continue
        if RAW_HTML_DECLARATION_OPEN_RE.match(raw):
            if ">" not in raw:
                raw_html_until_token = ">"
            continue
        if RAW_HTML_BLOCK_OPEN_RE.match(raw) or RAW_HTML_GENERIC_TAG_RE.match(raw):
            raw_html_until_blank = True
            continue
        remainder = raw
        rendered = ""
        while remainder:
            if in_comment:
                end = remainder.find("-->")
                if end < 0:
                    remainder = ""
                    break
                remainder = remainder[end + 3:]
                in_comment = False
                continue
            start = remainder.find("<!--")
            if start < 0:
                rendered += remainder
                break
            rendered += remainder[:start]
            remainder = remainder[start + 4:]
            in_comment = True
        if not rendered.strip():
            continue
        fence = FENCE_OPEN_RE.match(rendered)
        if fence:
            marker = fence.group(1)
            fence_char = marker[0]
            fence_len = len(marker)
            continue
        visible.append(rendered.rstrip())
    return visible


def _split_markdown_table_row(line: str) -> list[str] | None:
    if not line.startswith("|"):
        return None
    cells: list[str] = []
    buf: list[str] = []
    i = 1
    terminated = False
    while i < len(line):
        ch = line[i]
        if ch == "\\" and i + 1 < len(line):
            buf.extend((ch, line[i + 1]))
            i += 2
            continue
        if ch == "|":
            cells.append("".join(buf).strip())
            buf = []
            terminated = True
            i += 1
            continue
        buf.append(ch)
        terminated = False
        i += 1
    if not terminated or "".join(buf).strip():
        return None
    return cells


def _decision_records(decisions: str) -> list[tuple[str, str, str, str, str]]:
    records: list[tuple[str, str, str, str, str]] = []
    for line in _visible_markdown_lines(decisions):
        cells = _split_markdown_table_row(line)
        if not cells:
            continue
        first = cells[0].strip()
        if not first.startswith("JLM-DEC-"):
            continue
        if not DECISION_ID_RE.fullmatch(first):
            raise AssertionError(f"project_memory_decision_id_invalid:{first}")
        if len(cells) != 4 or any(not cell.strip() for cell in cells):
            raise AssertionError(f"project_memory_decision_row_invalid:{first}")
        records.append((first, cells[1].strip(), cells[2].strip(), cells[3].strip(), line))
    return records


def _decision_definition_rows(decisions: str) -> list[tuple[str, str]]:
    return [(decision_id, row) for decision_id, _meaning, _status, _source, row in _decision_records(decisions)]


def decision_definition_ids(decisions: str) -> list[str]:
    return [decision_id for decision_id, _row in _decision_definition_rows(decisions)]


def _decision_number(decision_id: str) -> int:
    return int(decision_id.rsplit("-", 1)[1])


def _validate_baseline_decision_meanings(decisions: str) -> None:
    meanings = {decision_id: meaning for decision_id, meaning, _status, _source, _row in _decision_records(decisions)}
    for decision_id, meaning in BASELINE_DECISION_MEANINGS.items():
        if decision_id in meanings and meanings[decision_id] != meaning:
            raise AssertionError(f"project_memory_baseline_decision_meaning_changed:{decision_id}")


def decision_supersession_edges(decisions: str) -> dict[str, str]:
    edges: dict[str, str] = {}
    for source, _meaning, status, source_authority, row in _decision_records(decisions):
        searchable = " | ".join((status, source_authority, row))
        clauses = DECISION_SUPERSESSION_CLAUSE_RE.findall(searchable)
        if not clauses:
            continue
        targets = DECISION_SUPERSESSION_TARGET_RE.findall(searchable)
        if len(clauses) != 1 or len(targets) != 1 or not DECISION_ID_RE.fullmatch(targets[0]):
            raise AssertionError(f"project_memory_malformed_supersession:{source}")
        edges[source] = targets[0]
    return edges


def decision_supersession_targets(decisions: str) -> list[str]:
    return list(decision_supersession_edges(decisions).values())


def _validate_supersession_acyclic(edges: dict[str, str]) -> None:
    state: dict[str, int] = {}
    def visit(node: str) -> None:
        marker = state.get(node, 0)
        if marker == 1:
            raise AssertionError(f"project_memory_supersession_cycle:{node}")
        if marker == 2:
            return
        state[node] = 1
        target = edges.get(node)
        if target is not None:
            if target == node:
                raise AssertionError(f"project_memory_supersession_self_reference:{node}")
            if target in edges:
                visit(target)
        state[node] = 2
    for source in edges:
        visit(source)


def validate_decision_history(current: str, prior: str) -> None:
    prior_records = _decision_records(prior)
    current_records = _decision_records(current)
    prior_map = {decision_id: meaning for decision_id, meaning, _status, _source, _row in prior_records}
    current_map = {decision_id: meaning for decision_id, meaning, _status, _source, _row in current_records}
    for decision_id, meaning in prior_map.items():
        if decision_id not in current_map:
            raise AssertionError(f"project_memory_prior_decision_missing:{decision_id}")
        if current_map[decision_id] != meaning:
            raise AssertionError(f"project_memory_prior_decision_meaning_changed:{decision_id}")


def validate_decision_register(decisions: str, prior_decisions: str | None = None) -> int:
    records = _decision_records(decisions)
    ids = [record[0] for record in records]
    if len(ids) != len(set(ids)):
        raise AssertionError("project_memory_duplicate_decision_definition_id")
    defined = set(ids)
    missing = [decision_id for decision_id in BASELINE_DECISION_IDS if decision_id not in defined]
    if missing:
        raise AssertionError("project_memory_missing_baseline_decision:" + ",".join(missing))
    _validate_baseline_decision_meanings(decisions)
    edges = decision_supersession_edges(decisions)
    for target in edges.values():
        if target not in defined:
            raise AssertionError(f"project_memory_missing_supersession_target:{target}")
    _validate_supersession_acyclic(edges)
    for source, target in edges.items():
        if _decision_number(target) <= _decision_number(source):
            raise AssertionError(f"project_memory_supersession_target_not_newer:{source}->{target}")
    if prior_decisions is not None:
        validate_decision_history(decisions, prior_decisions)
    return len(ids)


def validate_human_operations(human: str) -> None:
    for token in (
        "Internal and customer-side authority", "authoritative visibility", "JLMirror-controlled authenticated surface",
        "continue tracking and presenting whether/when the customer has viewed", "RESPONSIBLE PERSON != CURRENT ACTION OWNER", "DELIVERED != VIEWED",
    ):
        if token not in human:
            raise AssertionError(f"project_memory_human_model_missing:{token}")


def _normalize_yaml_key(raw_key: str) -> str:
    raw_key = raw_key.strip()
    if raw_key.startswith("'") and raw_key.endswith("'"):
        return raw_key[1:-1].replace("''", "'")
    if raw_key.startswith('"') and raw_key.endswith('"'):
        try:
            parsed = ast.literal_eval(raw_key)
        except (SyntaxError, ValueError):
            return raw_key
        return parsed if isinstance(parsed, str) else raw_key
    return raw_key


def _yaml_key_value(candidate: str) -> tuple[str, str] | None:
    match = re.match(r"(?P<key>'(?:''|[^'])*'|\"(?:\\.|[^\"])*\"|[^:#][^:]*?)\s*:\s*(?P<value>.*)$", candidate)
    return None if not match else (_normalize_yaml_key(match.group("key")), match.group("value").strip())


def _project_memory_job_lines(workflow: str) -> list[str]:
    lines = workflow.splitlines()
    start = next((i for i, line in enumerate(lines) if line == "  project-memory:"), None)
    if start is None:
        raise AssertionError("project_memory_workflow_job_missing")
    end = len(lines)
    for i in range(start + 1, len(lines)):
        line = lines[i]
        if line.strip() and len(line) - len(line.lstrip(" ")) <= 2:
            end = i
            break
    return lines[start + 1:end]


def _project_memory_job_keys(workflow: str) -> set[str]:
    keys: set[str] = set()
    for line in _project_memory_job_lines(workflow):
        indent = len(line) - len(line.lstrip(" "))
        stripped = line.strip()
        if indent != 4 or not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("?"):
            raise AssertionError("project_memory_workflow_job_explicit_key_not_allowed")
        pair = _yaml_key_value(stripped)
        if pair:
            keys.add(pair[0])
    return keys


def _project_memory_job_mapping(workflow: str, parent: str) -> dict[str, str]:
    lines = _project_memory_job_lines(workflow)
    result: dict[str, str] = {}
    in_parent = False
    for line in lines:
        indent = len(line) - len(line.lstrip(" "))
        stripped = line.strip()
        if indent == 4:
            if stripped.startswith("?"):
                raise AssertionError("project_memory_workflow_job_explicit_key_not_allowed")
            pair = _yaml_key_value(stripped) if stripped and not stripped.startswith("#") else None
            in_parent = bool(pair and pair[0] == parent and pair[1] == "")
            continue
        if in_parent and indent == 6 and stripped and not stripped.startswith("#"):
            pair = _yaml_key_value(stripped)
            if pair:
                result[pair[0]] = pair[1]
        elif in_parent and stripped and indent <= 4:
            in_parent = False
    return result


def _project_memory_workflow_steps(workflow: str) -> list[dict[str, str]]:
    job_lines = _project_memory_job_lines(workflow)
    steps_start = next((i for i, line in enumerate(job_lines) if line == "    steps:"), None)
    if steps_start is None:
        raise AssertionError("project_memory_workflow_steps_missing")
    blocks: list[list[str]] = []
    current: list[str] | None = None
    for line in job_lines[steps_start + 1:]:
        indent = len(line) - len(line.lstrip(" "))
        stripped = line.strip()
        if indent == 6 and stripped.startswith("- "):
            if current is not None:
                blocks.append(current)
            current = [line]
            continue
        if current is not None:
            current.append(line)
    if current is not None:
        blocks.append(current)
    steps: list[dict[str, str]] = []
    for block in blocks:
        parsed: dict[str, str] = {"__block__": "\n".join(block)}
        nested: str | None = None
        block_key: str | None = None
        block_body: list[str] = []
        for idx, line in enumerate(block):
            indent = len(line) - len(line.lstrip(" "))
            stripped = line.strip()
            if idx == 0:
                pair = _yaml_key_value(stripped[2:].strip())
                if pair:
                    parsed[pair[0]] = pair[1]
                continue
            if block_key is not None:
                if indent >= 10:
                    block_body.append(line[10:] if len(line) >= 10 else "")
                    continue
                parsed[f"{block_key}.body"] = "\n".join(block_body)
                block_key = None
                block_body = []
            if not stripped or stripped.startswith("#"):
                continue
            if indent == 8:
                nested = None
                if stripped.startswith("?"):
                    raise AssertionError("project_memory_workflow_step_explicit_key_not_allowed")
                pair = _yaml_key_value(stripped)
                if pair:
                    parsed[pair[0]] = pair[1]
                    if pair[1] == "":
                        nested = pair[0]
                    if pair[1] in {"|", "|-", ">", ">-"}:
                        block_key = pair[0]
                continue
            if indent == 10 and nested is not None:
                pair = _yaml_key_value(stripped)
                if pair:
                    parsed[f"{nested}.{pair[0]}"] = pair[1]
        if block_key is not None:
            parsed[f"{block_key}.body"] = "\n".join(block_body)
        steps.append(parsed)
    return steps


def _unique_step(steps: list[dict[str, str]], name: str) -> dict[str, str]:
    matches = [step for step in steps if step.get("name") == name]
    if len(matches) != 1:
        raise AssertionError(f"project_memory_workflow_step_identity_invalid:{name}")
    return matches[0]


def validate_project_memory_workflow(workflow: str) -> None:
    if "if" in _project_memory_job_keys(workflow):
        raise AssertionError("project_memory_workflow_job_condition_not_allowed")
    job_env = _project_memory_job_mapping(workflow, "env")
    expected_job_env = {
        "EVENT_NAME": "${{ github.event_name }}",
        "PR_HEAD_SHA": "${{ github.event.pull_request.head.sha }}",
        "PR_BASE_SHA": "${{ github.event.pull_request.base.sha }}",
        "EVENT_SHA": "${{ github.sha }}",
        "EVENT_BEFORE_SHA": "${{ github.event.before }}",
    }
    if job_env != expected_job_env:
        raise AssertionError("project_memory_workflow_job_env_binding_invalid")
    steps = _project_memory_workflow_steps(workflow)
    names = [step.get("name", "") for step in steps]
    if names != list(EXPECTED_STEP_NAMES):
        raise AssertionError("project_memory_workflow_step_order_invalid")
    if sum(1 for step in steps if step.get("uses", "").startswith("actions/checkout@")) != 1:
        raise AssertionError("project_memory_workflow_checkout_count_invalid")
    if any("if" in step for step in steps):
        raise AssertionError("project_memory_workflow_condition_not_allowed")
    if any("continue-on-error" in step for step in steps):
        raise AssertionError("project_memory_workflow_continue_on_error_not_allowed")
    resolve = _unique_step(steps, "Resolve exact analyzed HEAD")
    if resolve.get("id") != "target" or resolve.get("shell") != "bash" or resolve.get("run.body", "") != CANONICAL_RESOLVE_BODY:
        raise AssertionError("project_memory_workflow_resolve_head_binding_invalid")
    checkout = _unique_step(steps, "Checkout exact analyzed HEAD")
    if (
        checkout.get("uses") != "actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1"
        or checkout.get("with.ref") != "${{ steps.target.outputs.sha }}"
        or checkout.get("with.persist-credentials") != "false"
        or checkout.get("with.fetch-depth") != "0"
        or checkout.get("with.allow-unsafe-pr-checkout") != "false"
    ):
        raise AssertionError("project_memory_workflow_checkout_binding_invalid")
    verify = _unique_step(steps, "Verify exact commit identity")
    if (
        verify.get("env.EXPECTED_SHA") != "${{ steps.target.outputs.sha }}"
        or verify.get("shell") != "bash"
        or 'test "$(git rev-parse HEAD)" = "$EXPECTED_SHA"' not in verify.get("run.body", "")
    ):
        raise AssertionError("project_memory_workflow_verify_head_binding_invalid")
    required = {
        "Validate canonical project memory": "python3 tools/project_memory/validate_project_memory.py",
        "Test canonical project memory": "python3 -m unittest discover -s tests/project_memory -p 'test_*.py'",
        "Falsify canonical project-memory guardrails": "PYTHONPATH=tools/assurance:tools/project_memory python3 tools/assurance/test_validate_d4c_selection.py",
        "Validate repository structure and workflow safety": "python3 tools/assurance/validate_repository.py",
    }
    for name, run in required.items():
        if _unique_step(steps, name).get("run") != run:
            raise AssertionError(f"project_memory_workflow_missing_executable_step:{name}")


def _prior_history_sha() -> str | None:
    event_name = os.environ.get("EVENT_NAME", "")
    candidate = ""
    if event_name == "pull_request":
        candidate = os.environ.get("PR_BASE_SHA", "")
    elif event_name == "push":
        candidate = os.environ.get("EVENT_BEFORE_SHA", "")
    if not re.fullmatch(r"[0-9a-f]{40}", candidate) or candidate == "0" * 40:
        return None
    return candidate


def _load_prior_decision_register_from_git() -> str | None:
    prior_sha = _prior_history_sha()
    if prior_sha is None:
        return None
    verify = subprocess.run(["git", "cat-file", "-e", f"{prior_sha}^{{commit}}"], cwd=ROOT, capture_output=True, text=True)
    if verify.returncode != 0:
        raise AssertionError("project_memory_prior_commit_unavailable")
    listed = subprocess.run(["git", "ls-tree", "--name-only", prior_sha, "--", DECISION_REGISTER_REL], cwd=ROOT, capture_output=True, text=True)
    if listed.returncode != 0:
        raise AssertionError("project_memory_prior_tree_unavailable")
    if not listed.stdout.strip():
        return None
    shown = subprocess.run(["git", "show", f"{prior_sha}:{DECISION_REGISTER_REL}"], cwd=ROOT, capture_output=True, text=True)
    if shown.returncode != 0:
        raise AssertionError("project_memory_prior_decision_register_unavailable")
    return shown.stdout


def validate() -> tuple[int, int]:
    texts = {name: read(name) for name in REQUIRED_FILES}
    for token in ("provider-neutral", "multi-tenant", "Zabbix 7.4", "not a Zabbix UI"):
        if token not in texts["PROJECT-IDENTITY.md"]:
            raise AssertionError(f"project_memory_identity_missing:{token}")
    for token in ("Problem State", "Health Projection", "Alerting Policy/Evaluation", "Responsibility / ACK", "View/Read Evidence", "ITSM", "Automation", "AIOps"):
        if token not in texts["E2E-SYSTEM-MAP.md"]:
            raise AssertionError(f"project_memory_e2e_missing:{token}")
    for token in ("PROVIDER ID != PLATFORM ID", "JWT VALID != CURRENT AUTHORIZATION", "PROBLEM != ALERT", "ACKNOWLEDGEMENT != RESOLUTION", "DELIVERED != VIEWED", "HISTORICAL GENERATION != CURRENT AUTHORITY"):
        if token not in texts["CANONICAL-INVARIANTS.md"]:
            raise AssertionError(f"project_memory_invariant_missing:{token}")
    if not WORKFLOW.is_file():
        raise AssertionError("project_memory_workflow_missing")
    validate_project_memory_workflow(WORKFLOW.read_text(encoding="utf-8"))
    prior_decisions = _load_prior_decision_register_from_git()
    decision_count = validate_decision_register(texts["DECISION-REGISTER.md"], prior_decisions)
    state = texts["IMPLEMENTATION-STATE.md"]
    if not re.search(r"Canonical main SHA at this snapshot: `([0-9a-f]{40})`", state):
        raise AssertionError("project_memory_invalid_snapshot_sha")
    for token in ("AUTHORIZED", "IMPLEMENTED", "FOUNDATION", "BLOCKED", "#147", "#148"):
        if token not in state:
            raise AssertionError(f"project_memory_state_missing:{token}")
    validate_human_operations(texts["HUMAN-OPERATIONS-MODEL.md"])
    recovery = texts["RECOVERY-PLAYBOOK-FOR-NEW-CHAT.md"]
    for name in ("PROJECT-IDENTITY.md", "IMPLEMENTATION-STATE.md", "CANONICAL-INVARIANTS.md", "DOMAIN-AUTHORITY-MAP.md", "ROADMAP-DEPENDENCY-GRAPH.md"):
        if name not in recovery:
            raise AssertionError(f"project_memory_recovery_missing:{name}")
    roadmap = texts["ROADMAP-DEPENDENCY-GRAPH.md"]
    if "Alert Policy/Evaluation authorization" not in roadmap or "Alert lifecycle runtime" not in roadmap:
        raise AssertionError("project_memory_roadmap_missing_alert_dependency")
    if "automatic Alert create/resolve remains blocked" not in texts["OPEN-QUESTIONS-AND-DEFERRED.md"]:
        raise AssertionError("project_memory_deferred_missing_alert_block")
    return len(REQUIRED_FILES), decision_count


if __name__ == "__main__":
    files, decisions = validate()
    print(f"project_memory=PASS files={files} decisions={decisions}")
