from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MEMORY = ROOT / "docs" / "00-foundation" / "project-memory"

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


def read(name: str) -> str:
    path = MEMORY / name
    if not path.is_file():
        raise AssertionError(f"project_memory_missing_file:{name}")
    text = path.read_text(encoding="utf-8")
    if len(text.strip()) < 200:
        raise AssertionError(f"project_memory_file_too_small:{name}")
    return text


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

    decisions = texts["DECISION-REGISTER.md"]
    ids = re.findall(r"JLM-DEC-\d{3}", decisions)
    if len(ids) < 10:
        raise AssertionError("project_memory_decision_register_too_small")
    if len(ids) != len(set(ids)):
        raise AssertionError("project_memory_duplicate_decision_id")

    state = texts["IMPLEMENTATION-STATE.md"]
    if not re.search(r"Canonical main SHA at this snapshot: `([0-9a-f]{40})`", state):
        raise AssertionError("project_memory_invalid_snapshot_sha")
    for token in ("AUTHORIZED", "IMPLEMENTED", "FOUNDATION", "BLOCKED", "#147", "#148"):
        if token not in state:
            raise AssertionError(f"project_memory_state_missing:{token}")

    human = texts["HUMAN-OPERATIONS-MODEL.md"]
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

    return len(REQUIRED_FILES), len(set(ids))


if __name__ == "__main__":
    files, decisions = validate()
    print(f"project_memory=PASS files={files} decisions={decisions}")
