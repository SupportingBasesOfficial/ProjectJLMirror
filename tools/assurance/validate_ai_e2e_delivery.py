#!/usr/bin/env python3
from __future__ import annotations

import json
import re
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
EXPECTED_GATE_NAMES = (
    "Developer/runtime bootstrap",
    "Identity + tenant + protected application shell",
    "Monitoring Source onboarding",
    "Resource inventory",
    "Metrics current + history",
    "Problem + Health",
    "Monitoring to Alerting transport",
    "Alert policy + lifecycle",
    "Human operations",
    "Notification + delivery",
    "ITSM golden path",
    "Automation golden path",
    "AIOps golden path",
    "Commercial FinOps product administration",
    "Production release gate",
)
EXPECTED_AUTHORITY_PREREQUISITES = {
    "G7": "separate_alert_policy_evaluation_authorization",
    "G8": "responsibility_ack_visibility_authorization",
}
EXPECTED_LAYERS = (
    "authority","data_model","migration","tenant_isolation","domain","application",
    "api_bff","frontend","unit_tests","integration_tests","e2e_tests","adversarial_tests",
    "observability","runtime","deployment","exact_head_evidence",
)
EXPECTED_OPTIMIZATION_TARGET = "lead_time_from_accepted_requirement_to_verified_executable_user_outcome"
EXPECTED_OPTIMIZATION_SENTENCE = "Optimize for **lead time from accepted requirement to verified executable user outcome**, not lines of code, commit count or number of parallel agents."
FENCE_OPEN_RE = re.compile(r"^[ ]{0,3}(`{3,}|~{3,})")
FENCE_CLOSE_RE = re.compile(r"^[ ]{0,3}(`{3,}|~{3,})[ \t]*$")
RAW_CONTAINER_START_RE = re.compile(
    r"^[ ]{0,3}<(?P<tag>script|pre|style|textarea|xmp|iframe|noembed|noframes|plaintext)(?:\s|>|$)",
    re.IGNORECASE,
)
GENERIC_BLOCK_START_RE = re.compile(
    r"^[ ]{0,3}</?(?:address|article|aside|base|basefont|blockquote|body|caption|center|col|colgroup|dd|details|dialog|dir|div|dl|dt|fieldset|figcaption|figure|footer|form|frame|frameset|h[1-6]|head|header|hr|html|legend|li|link|main|menu|menuitem|nav|ol|optgroup|option|p|param|search|section|summary|table|tbody|td|tfoot|th|thead|title|tr|track|ul)(?:\s|/?>|$)",
    re.IGNORECASE,
)
RAW_PROCESSING_OPEN_RE = re.compile(r"^[ ]{0,3}<\?")
RAW_CDATA_OPEN_RE = re.compile(r"^[ ]{0,3}<!\[CDATA\[")
RAW_DECLARATION_OPEN_RE = re.compile(r"^[ ]{0,3}<![A-Z]")
RAW_GENERIC_COMPLETE_TAG_RE = re.compile(
    r"^[ ]{0,3}</?[A-Za-z][A-Za-z0-9-]*(?:\s+(?:[A-Za-z_:][A-Za-z0-9_.:-]*(?:\s*=\s*(?:\"[^\"]*\"|'[^']*'|[^\s\"'=<>`]+))?))*\s*/?>[ \t]*$"
)


def require(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)


def _visible_markdown_lines(text: str) -> list[str]:
    """Return Markdown lines that can participate in rendered semantic structure."""
    lines: list[str] = []
    fence_char: str | None = None
    fence_len = 0
    in_comment = False
    raw_container: str | None = None
    generic_html_block = False
    raw_until_token: str | None = None

    for raw in text.splitlines():
        if fence_char is not None:
            closing = FENCE_CLOSE_RE.match(raw)
            if closing:
                marker = closing.group(1)
                if marker[0] == fence_char and len(marker) >= fence_len:
                    fence_char = None
                    fence_len = 0
            continue

        if raw_until_token is not None:
            if raw_until_token in raw:
                raw_until_token = None
            continue

        if raw_container is not None:
            if raw_container == "plaintext":
                continue
            if re.search(rf"</{re.escape(raw_container)}\s*>", raw, re.IGNORECASE):
                raw_container = None
            continue

        if generic_html_block:
            if not raw.strip():
                generic_html_block = False
            continue

        remainder = raw
        rendered = ""
        while remainder:
            if in_comment:
                end = remainder.find("-->")
                if end < 0:
                    remainder = ""
                    break
                remainder = remainder[end + 3 :]
                in_comment = False
                continue
            start = remainder.find("<!--")
            if start < 0:
                rendered += remainder
                break
            rendered += remainder[:start]
            remainder = remainder[start + 4 :]
            in_comment = True

        if not rendered.strip():
            continue

        fence = FENCE_OPEN_RE.match(rendered)
        if fence:
            marker = fence.group(1)
            fence_char = marker[0]
            fence_len = len(marker)
            continue

        raw_start = RAW_CONTAINER_START_RE.match(rendered)
        if raw_start:
            tag = raw_start.group("tag").lower()
            if tag != "plaintext" and re.search(rf"</{re.escape(tag)}\s*>", rendered, re.IGNORECASE):
                continue
            raw_container = tag
            continue

        if RAW_PROCESSING_OPEN_RE.match(rendered):
            if "?>" not in rendered:
                raw_until_token = "?>"
            continue
        if RAW_CDATA_OPEN_RE.match(rendered):
            if "]]>" not in rendered:
                raw_until_token = "]]>"
            continue
        if RAW_DECLARATION_OPEN_RE.match(rendered):
            if ">" not in rendered:
                raw_until_token = ">"
            continue

        if GENERIC_BLOCK_START_RE.match(rendered) or RAW_GENERIC_COMPLETE_TAG_RE.match(rendered):
            generic_html_block = True
            continue

        lines.append(rendered.rstrip())
    return lines


def _visible_markdown_text(text: str) -> str:
    """Return only rendered/visible Markdown text for normative prose checks."""
    return "\n".join(_visible_markdown_lines(text))


def _validate_heading_sequence(text: str, expected: tuple[str, ...], prefix: str, missing_prefix: str, order_error: str) -> None:
    visible = _visible_markdown_lines(text)
    expected_lines = [f"### {heading}" for heading in expected]
    expected_ids = [heading.split(" ", 1)[0] for heading in expected]
    for heading, line in zip(expected, expected_lines):
        require(line in visible, f"{missing_prefix}:{heading}")

    identifier_re = re.compile(rf"^###\s+({re.escape(prefix)}\d+)\b")
    identified = [(match.group(1), line) for line in visible if (match := identifier_re.match(line))]
    require([item[0] for item in identified] == expected_ids, order_error)
    require([item[1] for item in identified] == expected_lines, order_error)


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
    constitution_visible = _visible_markdown_text(constitution)
    for token in (
        "schema/migration -> persistence authority -> domain logic -> application/service -> API/BFF -> frontend",
        "Definition of Done: E2E-16","Tenant isolation","E2E tests","Adversarial tests","Deployment",
        "READY_FOR_MERGE is not merge authorization",
    ):
        require(token in constitution_visible, f"constitution_missing:{token}")

    model = texts["VERTICAL-SLICE-DELIVERY-MODEL.md"]
    model_visible = _visible_markdown_text(model)
    _validate_heading_sequence(model, EXPECTED_SLICE_HEADINGS, "S", "slice_heading_missing", "slice_heading_order_or_duplicate")
    for token in ("database_scope", "api_scope", "frontend_scope", "browser E2E", "AI task packet"):
        require(token in model_visible, f"slice_model_missing:{token}")

    roadmap = texts["PRODUCT-EXECUTION-ROADMAP.md"]
    roadmap_visible = _visible_markdown_text(roadmap)
    _validate_heading_sequence(roadmap, EXPECTED_GATE_HEADINGS, "G", "roadmap_heading_missing", "roadmap_heading_order_or_duplicate")
    require(EXPECTED_OPTIMIZATION_SENTENCE in roadmap_visible, "roadmap_optimization_target_missing")

    bootstrap = texts["DAY-1-IMPLEMENTATION-BOOTSTRAP.md"]
    bootstrap_visible = _visible_markdown_text(bootstrap)
    for token in (
        "Do not begin by asking the AI to \"build JLMirror\"","Connect the real frontend",
        "Run the slice locally E2E","Container proof","Stop at merge gate",
    ):
        require(token in bootstrap_visible, f"bootstrap_missing:{token}")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    schema_version = manifest.get("schema_version")
    require(type(schema_version) is int and schema_version == 1, "manifest_schema")
    require(manifest.get("program_id") == "jlmirror.ai-e2e-delivery@1", "manifest_program")
    require(manifest.get("delivery_model") == "vertical_slice", "manifest_delivery_model")
    require(manifest.get("definition_of_done") == "E2E-16", "manifest_dod")
    require(manifest.get("merge_authority") == "separate_explicit_owner_authorization", "manifest_merge_authority")
    require(manifest.get("optimization_target") == EXPECTED_OPTIMIZATION_TARGET, "manifest_optimization_target")
    gates = manifest.get("gates")
    require(isinstance(gates, list) and len(gates) == 15, "manifest_gate_count")
    ids = [g.get("id") for g in gates]
    require(ids == [f"G{i}" for i in range(15)], "manifest_gate_order")
    for index, gate in enumerate(gates):
        gate_id = f"G{index}"
        require(gate.get("name") == EXPECTED_GATE_NAMES[index], f"gate_name_exact:{gate_id}")
        expected_deps = [] if index == 0 else [f"G{index - 1}"]
        require(gate.get("depends_on") == expected_deps, f"gate_dependencies_exact:{gate_id}")
        require(gate.get("requires_e2e") is True, f"gate_requires_e2e:{gate_id}")
        expected_authority = EXPECTED_AUTHORITY_PREREQUISITES.get(gate_id)
        if expected_authority is None:
            require("authority_prerequisite" not in gate, f"gate_unexpected_authority_prerequisite:{gate_id}")
        else:
            require(gate.get("authority_prerequisite") == expected_authority, f"gate_authority_prerequisite_exact:{gate_id}")
    require(manifest.get("slice_stages") == [f"S{i}" for i in range(11)], "manifest_slice_stages")
    required_layers = manifest.get("required_layers")
    require(required_layers == list(EXPECTED_LAYERS), "manifest_e2e16_exact_layers")
    require(len(set(required_layers)) == 16, "manifest_e2e16_unique_layers")
    return len(REQUIRED_DOCS), len(gates), len(required_layers)


if __name__ == "__main__":
    docs, gates, layers = validate()
    print(f"ai_e2e_delivery=PASS docs={docs} gates={gates} dod_layers={layers}")