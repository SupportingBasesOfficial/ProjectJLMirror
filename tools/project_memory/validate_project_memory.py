from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MEMORY = ROOT / "docs" / "00-foundation" / "project-memory"
WORKFLOW = ROOT / ".github" / "workflows" / "project-memory-governance.yml"

REQUIRED_FILES = (
    "PROJECT-IDENTITY.md",
    "E2E-SYSTEM-MAP.md",
    "DOMAIN-AUTHORITY-MAP.md",
    "CANONICAL-INVARIANTS.md",
    "DECISION-REGISTER.md",
    "IMPLEMENTATION-STATE.md",
    "ACCEPTED-PR-CHAIN.md",
    "ROADMAP-DEPENDENCY-GRAPH.md",
    "GLOSSARY.md",
    "HUMAN-OPERATIONS-MODEL.md",
    "OPEN-QUESTIONS-AND-DEFERRED.md",
    "RECOVERY-PLAYBOOK-FOR-NEW-CHAT.md",
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
    "JLM-DEC-012": "Alert v1 lifecycle is `active | resolved`; resolved is terminal",
    "JLM-DEC-013": "Effectful Alert lifecycle transitions require immutable policy ID/version",
    "JLM-DEC-014": "Alert source family is explicit",
    "JLM-DEC-015": "Human operations use orthogonal state dimensions, not one giant status",
    "JLM-DEC-016": "Critical human workflows must provide authoritative visibility evidence",
    "JLM-DEC-017": "Repository truth outranks assistant/chat memory",
}
BASELINE_DECISION_IDS = tuple(BASELINE_DECISION_MEANINGS)
DECISION_ID_RE = re.compile(r"JLM-DEC-\d{3}")
DECISION_DEFINITION_RE = re.compile(r"^\|\s*(JLM-DEC-\d{3})\s*\|", re.MULTILINE)
DECISION_SUPERSESSION_CLAUSE_RE = re.compile(r"\bsuperseded\s+by\b", re.IGNORECASE)
DECISION_SUPERSESSION_TARGET_RE = re.compile(r"\bsuperseded\s+by\s+([^\s|,;.]+)", re.IGNORECASE)


def read(name: str) -> str:
    path = MEMORY / name
    if not path.is_file():
        raise AssertionError(f"project_memory_missing_file:{name}")
    text = path.read_text(encoding="utf-8")
    if len(text.strip()) < 200:
        raise AssertionError(f"project_memory_file_too_small:{name}")
    return text


def decision_definition_ids(decisions: str) -> list[str]:
    return DECISION_DEFINITION_RE.findall(decisions)


def _decision_definition_rows(decisions: str) -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    for line in decisions.splitlines():
        match = re.match(r"^\|\s*(JLM-DEC-\d{3})\s*\|", line)
        if match:
            rows.append((match.group(1), line))
    return rows


def _validate_baseline_decision_meanings(decisions: str) -> None:
    rows = dict(_decision_definition_rows(decisions))
    for decision_id, expected_meaning in BASELINE_DECISION_MEANINGS.items():
        row = rows.get(decision_id)
        if row is None:
            continue
        pattern = rf"^\|\s*{re.escape(decision_id)}\s*\|\s*{re.escape(expected_meaning)}\s*\|"
        if re.match(pattern, row) is None:
            raise AssertionError(f"project_memory_baseline_decision_meaning_changed:{decision_id}")


def decision_supersession_edges(decisions: str) -> dict[str, str]:
    edges: dict[str, str] = {}
    for source, row in _decision_definition_rows(decisions):
        clauses = DECISION_SUPERSESSION_CLAUSE_RE.findall(row)
        if not clauses:
            continue
        targets = DECISION_SUPERSESSION_TARGET_RE.findall(row)
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


def validate_decision_register(decisions: str) -> int:
    ids = decision_definition_ids(decisions)
    if len(ids) != len(set(ids)):
        raise AssertionError("project_memory_duplicate_decision_definition_id")
    defined = set(ids)
    missing_baseline = [decision_id for decision_id in BASELINE_DECISION_IDS if decision_id not in defined]
    if missing_baseline:
        raise AssertionError("project_memory_missing_baseline_decision:" + ",".join(missing_baseline))
    _validate_baseline_decision_meanings(decisions)
    edges = decision_supersession_edges(decisions)
    for target in edges.values():
        if target not in defined:
            raise AssertionError(f"project_memory_missing_supersession_target:{target}")
    _validate_supersession_acyclic(edges)
    return len(ids)


def validate_human_operations(human: str) -> None:
    for token in (
        "Internal and customer-side authority",
        "authoritative visibility",
        "JLMirror-controlled authenticated surface",
        "continue tracking and presenting whether/when the customer has viewed",
        "RESPONSIBLE PERSON != CURRENT ACTION OWNER",
        "DELIVERED != VIEWED",
    ):
        if token not in human:
            raise AssertionError(f"project_memory_human_model_missing:{token}")


def validate_project_memory_workflow(workflow: str) -> None:
    active_lines = {line.strip() for line in workflow.splitlines() if line.strip() and not line.lstrip().startswith("#")}
    required_lines = {
        "allow-unsafe-pr-checkout: false",
        "persist-credentials: false",
        "ref: ${{ steps.target.outputs.sha }}",
        "run: python3 tools/project_memory/validate_project_memory.py",
        "run: python3 -m unittest discover -s tests/project_memory -p 'test_*.py'",
        "run: PYTHONPATH=tools/assurance:tools/project_memory python3 tools/assurance/test_validate_d4c_selection.py",
        "run: python3 tools/assurance/validate_repository.py",
    }
    missing = sorted(required_lines - active_lines)
    if missing:
        raise AssertionError("project_memory_workflow_missing_active_line:" + ",".join(missing))


def validate() -> tuple[int, int]:
    texts = {name: read(name) for name in REQUIRED_FILES}

    identity = texts["PROJECT-IDENTITY.md"]
    for token in ("provider-neutral", "multi-tenant", "Zabbix 7.4", "not a Zabbix UI"):
        if token not in identity:
            raise AssertionError(f"project_memory_identity_missing:{token}")

    e2e = texts["E2E-SYSTEM-MAP.md"]
    for token in (
        "Problem State",
        "Health Projection",
        "Alerting Policy/Evaluation",
        "Responsibility / ACK",
        "View/Read Evidence",
        "ITSM",
        "Automation",
        "AIOps",
    ):
        if token not in e2e:
            raise AssertionError(f"project_memory_e2e_missing:{token}")

    invariants = texts["CANONICAL-INVARIANTS.md"]
    for token in (
        "PROVIDER ID != PLATFORM ID",
        "JWT VALID != CURRENT AUTHORIZATION",
        "PROBLEM != ALERT",
        "ACKNOWLEDGEMENT != RESOLUTION",
        "DELIVERED != VIEWED",
        "HISTORICAL GENERATION != CURRENT AUTHORITY",
    ):
        if token not in invariants:
            raise AssertionError(f"project_memory_invariant_missing:{token}")

    decision_count = validate_decision_register(texts["DECISION-REGISTER.md"])

    state = texts["IMPLEMENTATION-STATE.md"]
    if not re.search(r"Canonical main SHA at this snapshot: `([0-9a-f]{40})`", state):
        raise AssertionError("project_memory_invalid_snapshot_sha")
    for token in ("AUTHORIZED", "IMPLEMENTED", "FOUNDATION", "BLOCKED", "#147", "#148"):
        if token not in state:
            raise AssertionError(f"project_memory_state_missing:{token}")

    validate_human_operations(texts["HUMAN-OPERATIONS-MODEL.md"])

    recovery = texts["RECOVERY-PLAYBOOK-FOR-NEW-CHAT.md"]
    for name in (
        "PROJECT-IDENTITY.md",
        "IMPLEMENTATION-STATE.md",
        "CANONICAL-INVARIANTS.md",
        "DOMAIN-AUTHORITY-MAP.md",
        "ROADMAP-DEPENDENCY-GRAPH.md",
    ):
        if name not in recovery:
            raise AssertionError(f"project_memory_recovery_missing:{name}")

    roadmap = texts["ROADMAP-DEPENDENCY-GRAPH.md"]
    if "Alert Policy/Evaluation authorization" not in roadmap or "Alert lifecycle runtime" not in roadmap:
        raise AssertionError("project_memory_roadmap_missing_alert_dependency")

    deferred = texts["OPEN-QUESTIONS-AND-DEFERRED.md"]
    if "automatic Alert create/resolve remains blocked" not in deferred:
        raise AssertionError("project_memory_deferred_missing_alert_block")

    if not WORKFLOW.is_file():
        raise AssertionError("project_memory_workflow_missing")
    validate_project_memory_workflow(WORKFLOW.read_text(encoding="utf-8"))

    return len(REQUIRED_FILES), decision_count


if __name__ == "__main__":
    files, decisions = validate()
    print(f"project_memory=PASS files={files} decisions={decisions}")
