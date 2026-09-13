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


def require(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)


def validate() -> tuple[int, int, int]:
    texts = {}
    for name in REQUIRED_DOCS:
        path = DOCS / name
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
    for stage in [f"S{i}" for i in range(11)]:
        require(stage in model, f"slice_stage_missing:{stage}")
    for token in ("database_scope", "api_scope", "frontend_scope", "browser E2E", "AI task packet"):
        require(token in model, f"slice_model_missing:{token}")

    roadmap = texts["PRODUCT-EXECUTION-ROADMAP.md"]
    for gate in [f"G{i}" for i in range(15)]:
        require(gate in roadmap, f"roadmap_gate_missing:{gate}")
    require("G2 — Monitoring source onboarding golden path" in roadmap, "roadmap_missing_monitoring_source")
    require("G7 — Alert policy + lifecycle golden path" in roadmap, "roadmap_missing_alert_policy")
    require("G14 — Production release gate" in roadmap, "roadmap_missing_production_gate")

    bootstrap = texts["DAY-1-IMPLEMENTATION-BOOTSTRAP.md"]
    for token in (
        "Do not begin by asking the AI to \"build JLMirror\"",
        "Connect the real frontend",
        "Run the slice locally E2E",
        "Container proof",
        "Stop at merge gate",
    ):
        require(token in bootstrap, f"bootstrap_missing:{token}")

    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    require(manifest.get("schema_version") == 1, "manifest_schema")
    require(manifest.get("program_id") == "jlmirror.ai-e2e-delivery@1", "manifest_program")
    require(manifest.get("delivery_model") == "vertical_slice", "manifest_delivery_model")
    require(manifest.get("definition_of_done") == "E2E-16", "manifest_dod")
    require(manifest.get("merge_authority") == "separate_explicit_owner_authorization", "manifest_merge_authority")

    gates = manifest.get("gates")
    require(isinstance(gates, list) and len(gates) == 15, "manifest_gate_count")
    ids = [g.get("id") for g in gates]
    require(ids == [f"G{i}" for i in range(15)], "manifest_gate_order")
    seen = set()
    for gate in gates:
        deps = gate.get("depends_on")
        require(isinstance(deps, list), f"gate_dependencies:{gate.get('id')}")
        require(set(deps).issubset(seen), f"gate_forward_dependency:{gate.get('id')}")
        require(gate.get("requires_e2e") is True, f"gate_requires_e2e:{gate.get('id')}")
        seen.add(gate["id"])

    stages = manifest.get("slice_stages")
    require(stages == [f"S{i}" for i in range(11)], "manifest_slice_stages")

    required_layers = manifest.get("required_layers")
    require(isinstance(required_layers, list) and len(required_layers) == 16, "manifest_e2e16_layers")
    for layer in ("data_model", "domain", "api_bff", "frontend", "integration_tests", "e2e_tests", "deployment", "exact_head_evidence"):
        require(layer in required_layers, f"manifest_missing_layer:{layer}")

    return len(REQUIRED_DOCS), len(gates), len(required_layers)


if __name__ == "__main__":
    docs, gates, layers = validate()
    print(f"ai_e2e_delivery=PASS docs={docs} gates={gates} dod_layers={layers}")
