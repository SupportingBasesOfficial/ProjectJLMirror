#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "docs" / "00-foundation" / "ai-e2e-delivery"
MANIFEST = ROOT / "implementation" / "e2e-delivery" / "EXECUTION_MANIFEST.json"
REQUIRED_DOCS = (
    "AI-E2E-DELIVERY-CONSTITUTION.md",
    "VERTICAL-SLICE-DELIVERY-MODEL.md",
    "PRODUCT-EXECUTION-ROADMAP.md",
    "DAY-1-IMPLEMENTATION-BOOTSTRAP.md",
)
EXPECTED_SLICE_HEADINGS = (
    "S0 — Authority ready",
    "S1 — Contract skeleton",
    "S2 — Persistence",
    "S3 — Domain/application",
    "S4 — API/BFF",
    "S5 — Frontend",
    "S6 — Integration",
    "S7 — Browser/user E2E",
    "S8 — Adversarial/recovery",
    "S9 — Runtime/deployment",
    "S10 — HARDEN and merge gate",
)
EXPECTED_GATE_HEADINGS = (
    "G0 — Developer/runtime bootstrap",
    "G1 — Identity + tenant + shell golden path",
    "G2 — Monitoring source onboarding golden path",
    "G3 — Resource inventory golden path",
    "G4 — Metrics golden path",
    "G5 — Problem + Health golden path",
    "G6 — Monitoring -> Alerting transport golden path",
    "G7 — Alert policy + lifecycle golden path",
    "G8 — Human operations golden path",
    "G9 — Notification/delivery golden path",
    "G10 — ITSM golden path",
    "G11 — Automation golden path",
    "G12 — AIOps golden path",
    "G13 — Commercial/FinOps/product administration",
    "G14 — Production release gate",
)
EXPECTED_AUTHORITY_PREREQUISITES = {
    "G7": "separate_alert_policy_evaluation_authorization",
    "G8": "responsibility_ack_visibility_authorization",
}
EXPECTED_LAYERS = (
    "authority",
    "data_model",
    "migration",
    "tenant_isolation",
    "domain",
    "application",
    "api_bff",
    "frontend",
    "unit_tests",
    "integration_tests",
    "e2e_tests",
    "adversarial_tests",
    "observability",
    "runtime",
    "deployment",
    "exact_head_evidence",
)


def require(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)


def validate(root: Path = ROOT) -> tuple[int, int, int]:
    root = root.resolve()
    docs_dir = root / "docs" / "00-foundation" / "ai-e2e-delivery"
    manifest_path = root / "implementation" / "e2e-delivery" / "EXECUTION_MANIFEST.json"

    texts = {}
    for name in REQUIRED_DOCS:
        path = docs_dir / name
        require(path.is_file(), f"missing_delivery_doc:{name}")
        text = path.read_text(encoding="utf-8")
        require(len(text.strip()) >= 800, f"delivery_doc_too_small:{name}")
        texts[name] = text

    constitution = texts["AI-E2E-DELIVERY-CONSTITUTION.md"]
    for token in (
        "schema/migration -> persistence authority -> domain logic -> application/service -> API/BFF -> frontend",
        "Definition of Done: E2E-16",
        "Tenant isolation",
        "E2E tests",
        "Adversarial tests",
        "Deployment",
        "READY_FOR_MERGE is not merge authorization",
    ):
        require(token in constitution, f"constitution_missing:{token}")

    model = texts["VERTICAL-SLICE-DELIVERY-MODEL.md"]
    for heading in EXPECTED_SLICE_HEADINGS:
        require(f"### {heading}" in model, f"slice_heading_missing:{heading}")
    for token in ("database_scope", "api_scope", "frontend_scope", "browser E2E", "AI task packet"):
        require(token in model, f"slice_model_missing:{token}")

    roadmap = texts["PRODUCT-EXECUTION-ROADMAP.md"]
    for heading in EXPECTED_GATE_HEADINGS:
        require(f"### {heading}" in roadmap, f"roadmap_heading_missing:{heading}")

    bootstrap = texts["DAY-1-IMPLEMENTATION-BOOTSTRAP.md"]
    for token in (
        "Do not begin by asking the AI to \"build JLMirror\"",
        "Connect the real frontend",
        "Run the slice locally E2E",
        "Container proof",
        "Stop at merge gate",
    ):
        require(token in bootstrap, f"bootstrap_missing:{token}")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    require(manifest.get("schema_version") == 1, "manifest_schema")
    require(manifest.get("program_id") == "jlmirror.ai-e2e-delivery@1", "manifest_program")
    require(manifest.get("delivery_model") == "vertical_slice", "manifest_delivery_model")
    require(manifest.get("definition_of_done") == "E2E-16", "manifest_dod")
    require(manifest.get("merge_authority") == "separate_explicit_owner_authorization", "manifest_merge_authority")

    gates = manifest.get("gates")
    require(isinstance(gates, list) and len(gates) == 15, "manifest_gate_count")
    ids = [g.get("id") for g in gates]
    require(ids == [f"G{i}" for i in range(15)], "manifest_gate_order")
    for index, gate in enumerate(gates):
        gate_id = f"G{index}"
        deps = gate.get("depends_on")
        expected_deps = [] if index == 0 else [f"G{index - 1}"]
        require(deps == expected_deps, f"gate_dependencies_exact:{gate_id}")
        require(gate.get("requires_e2e") is True, f"gate_requires_e2e:{gate_id}")
        expected_authority = EXPECTED_AUTHORITY_PREREQUISITES.get(gate_id)
        if expected_authority is None:
            require("authority_prerequisite" not in gate, f"gate_unexpected_authority_prerequisite:{gate_id}")
        else:
            require(gate.get("authority_prerequisite") == expected_authority, f"gate_authority_prerequisite_exact:{gate_id}")

    stages = manifest.get("slice_stages")
    require(stages == [f"S{i}" for i in range(11)], "manifest_slice_stages")

    required_layers = manifest.get("required_layers")
    require(required_layers == list(EXPECTED_LAYERS), "manifest_e2e16_exact_layers")
    require(len(set(required_layers)) == 16, "manifest_e2e16_unique_layers")

    return len(REQUIRED_DOCS), len(gates), len(required_layers)


if __name__ == "__main__":
    docs, gates, layers = validate()
    print(f"ai_e2e_delivery=PASS docs={docs} gates={gates} dod_layers={layers}")
