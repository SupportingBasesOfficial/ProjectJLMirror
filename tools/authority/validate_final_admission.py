#!/usr/bin/env python3
"""Observer-only validator for the Wave 1 revision-bound final-admission contract."""

from __future__ import annotations

import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE_PATH = ROOT / "src" / "jlmirror_authority" / "control_plane.py"
MANIFEST_PATH = ROOT / "implementation" / "wave-1" / "FINAL_ADMISSION_MANIFEST.json"
BOUNDARY_PATH = ROOT / "implementation" / "wave-1" / "AUTHORITY_BOUNDARY.md"
ASSURANCE_PATH = ROOT / "implementation" / "wave-1" / "ASSURANCE.md"
TEST_PATH = ROOT / "tests" / "wave1" / "test_atomic_final_admission.py"
PROFILE = "jlmirror-wave1-final-admission/v1"

EXPECTED_MANIFEST = {
    "contract_id": "wave-1.final-admission-authority@1",
    "scope": "protected_operation_admission_only",
    "serial_currentness_is_final_authority": False,
    "caller_supplied_time_is_final_currentness": False,
    "authority_owned_currentness_required": True,
    "decision_mode": "atomic_or_revision_bound_logical_snapshot",
    "required_common_bindings": [
        "admission_revision",
        "authorization_policy_revision",
        "principal_authority_revision",
        "principal_id",
        "principal_credential_generation",
        "action",
    ],
    "required_tenant_bindings_when_applicable": [
        "tenant_id",
        "cell_id",
        "placement_authority_revision",
        "placement_version",
        "runtime_generation",
        "runtime_profile_id",
        "runtime_isolation_class",
        "configuration_generation",
        "workload_credential_generation",
        "network_policy_generation",
        "environment_class",
        "isolation_class",
        "fence_scope_id",
        "fence_epoch",
    ],
    "required_privileged_human_bindings_when_applicable": [
        "authentication_strength_policy_revision"
    ],
    "required_cross_tenant_bindings_when_applicable": [
        "executing_runtime_authority_revision",
        "executing_runtime_profile_id",
        "executing_runtime_generation",
    ],
    "finalizer_forbidden_inputs": ["caller_supplied_now"],
    "fallback_to_serial_checks": False,
    "final_snapshot_is_durable_effect_authority": False,
    "residual_mechanism_class": "C2_replaceable_implementation_choice",
}

REQUIRED_EVIDENCE_FIELDS = {
    "granted",
    "current",
    *EXPECTED_MANIFEST["required_common_bindings"],
    *EXPECTED_MANIFEST["required_tenant_bindings_when_applicable"],
    *EXPECTED_MANIFEST["required_privileged_human_bindings_when_applicable"],
    *EXPECTED_MANIFEST["required_cross_tenant_bindings_when_applicable"],
}

EXPECTED_FINALIZER_ARGUMENTS = [
    "self",
    "principal",
    "context",
    "declaration",
    "expected_runtime_binding",
    "authentication_strength_evidence",
]

REQUIRED_DOC_LAWS = (
    "SERIAL CURRENTNESS CHECKS != FINAL ADMISSION AUTHORITY",
    "CALLER-SUPPLIED NOW != FINAL CURRENTNESS CLOCK",
    "FINAL ADMISSION SNAPSHOT != DURABLE EFFECT AUTHORITY",
)

REQUIRED_TEST_NAMES = (
    "test_serial_green_without_final_admission_authority_fails_closed",
    "test_malformed_or_noncurrent_final_admission_fails_closed",
    "test_final_principal_or_action_binding_mismatch_fails_closed",
    "test_any_tenant_placement_generation_or_fence_drift_fails_closed",
    "test_cross_tenant_strength_revision_drift_fails_closed",
    "test_cross_tenant_runtime_generation_or_profile_drift_fails_closed",
    "test_cross_tenant_valid_final_snapshot_uses_no_caller_time",
)


def _manifest_findings(manifest: object) -> list[str]:
    if not isinstance(manifest, dict):
        return ["final-admission manifest must be a JSON object"]
    findings: list[str] = []
    if set(manifest) != set(EXPECTED_MANIFEST):
        findings.append("final-admission manifest field set drift")
    for key, expected in EXPECTED_MANIFEST.items():
        if manifest.get(key) != expected:
            findings.append(f"final-admission manifest field drift: {key}")
    return findings


def _named_class(tree: ast.AST, name: str) -> ast.ClassDef | None:
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == name:
            return node
    return None


def _named_function(tree: ast.AST, name: str) -> ast.FunctionDef | ast.AsyncFunctionDef | None:
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return node
    return None


def _function_arg_names(node: ast.FunctionDef | ast.AsyncFunctionDef) -> list[str]:
    return [
        *(arg.arg for arg in node.args.posonlyargs),
        *(arg.arg for arg in node.args.args),
        *(arg.arg for arg in node.args.kwonlyargs),
    ]


def _call_name(call: ast.Call) -> str | None:
    if isinstance(call.func, ast.Name):
        return call.func.id
    if isinstance(call.func, ast.Attribute):
        return call.func.attr
    return None


def validate_source_contract_text(text: str) -> list[str]:
    try:
        tree = ast.parse(text)
    except SyntaxError as exc:
        return [f"control-plane source is not parseable: {exc}"]

    findings: list[str] = []
    evidence = _named_class(tree, "FinalAdmissionEvidence")
    if evidence is None:
        findings.append("FinalAdmissionEvidence class is missing")
    else:
        fields = {
            node.target.id
            for node in evidence.body
            if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name)
        }
        missing = sorted(REQUIRED_EVIDENCE_FIELDS - fields)
        if missing:
            findings.append(
                "FinalAdmissionEvidence missing required authority bindings: " + ", ".join(missing)
            )

    port = _named_class(tree, "FinalAdmissionAuthorityPort")
    port_method = None
    if port is None:
        findings.append("FinalAdmissionAuthorityPort class is missing")
    else:
        for node in port.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "finalize_current_admission":
                port_method = node
                break
        if port_method is None:
            findings.append("FinalAdmissionAuthorityPort.finalize_current_admission is missing")
        else:
            args = _function_arg_names(port_method)
            if args != EXPECTED_FINALIZER_ARGUMENTS:
                findings.append("final-admission port argument contract drift")
            if "now" in args:
                findings.append("caller/request now is forbidden at final-admission port")

    helper = _named_function(tree, "_finalize_current_admission")
    if helper is None:
        findings.append("_finalize_current_admission enforcement helper is missing")
    else:
        port_calls = [
            node
            for node in ast.walk(helper)
            if isinstance(node, ast.Call) and _call_name(node) == "finalize_current_admission"
        ]
        if len(port_calls) != 1:
            findings.append("final-admission helper must invoke exactly one final-admission port call")
        else:
            keyword_names = [kw.arg for kw in port_calls[0].keywords]
            expected_keywords = EXPECTED_FINALIZER_ARGUMENTS[1:]
            if keyword_names != expected_keywords:
                findings.append("final-admission port call keyword contract drift")
            if "now" in keyword_names:
                findings.append("caller/request now reaches final-admission port")
        if not any(
            isinstance(node, ast.Name) and node.id == "FinalAdmissionEvidence"
            for node in ast.walk(helper)
        ):
            findings.append("final-admission helper does not enforce FinalAdmissionEvidence type")

    authorize = _named_function(tree, "authorize_protected_operation")
    if authorize is None:
        findings.append("authorize_protected_operation is missing")
    else:
        args = _function_arg_names(authorize)
        if "final_admission_authority" not in args:
            findings.append("authorize_protected_operation lacks final_admission_authority boundary")
        final_calls = [
            node
            for node in ast.walk(authorize)
            if isinstance(node, ast.Call) and _call_name(node) == "_finalize_current_admission"
        ]
        if len(final_calls) != 1:
            findings.append("authorize_protected_operation must invoke exactly one final admission helper")
        serial_returns = [
            node
            for node in ast.walk(authorize)
            if isinstance(node, ast.Return)
            and isinstance(node.value, ast.Call)
            and _call_name(node.value) == "_evaluate_current_authorization"
        ]
        if serial_returns:
            findings.append("serial authorization evaluation is returned as final admission authority")
        if not authorize.body or not isinstance(authorize.body[-1], ast.Return):
            findings.append("authorize_protected_operation must terminate in explicit final admission return")
        else:
            value = authorize.body[-1].value
            if not isinstance(value, ast.Call) or _call_name(value) != "_finalize_current_admission":
                findings.append("authorize_protected_operation final return bypasses final admission helper")

    return findings


def _docs_findings() -> list[str]:
    findings: list[str] = []
    try:
        boundary = BOUNDARY_PATH.read_text(encoding="utf-8")
        assurance = ASSURANCE_PATH.read_text(encoding="utf-8")
    except OSError as exc:
        return [f"final-admission governance document unreadable: {exc}"]
    for law in REQUIRED_DOC_LAWS:
        if law not in boundary:
            findings.append(f"authority boundary missing final-admission law: {law}")
    for token in (
        "FinalAdmissionAuthorityPort",
        "FinalAdmissionEvidence",
        "serial currentness checks",
        "caller/request `now`",
    ):
        if token not in assurance:
            findings.append(f"assurance boundary missing final-admission invariant: {token}")
    return findings


def _test_findings() -> list[str]:
    try:
        text = TEST_PATH.read_text(encoding="utf-8")
        tree = ast.parse(text)
    except (OSError, SyntaxError) as exc:
        return [f"final-admission adversarial tests unreadable: {exc}"]
    names = {
        node.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    return [
        f"final-admission adversarial test missing: {name}"
        for name in REQUIRED_TEST_NAMES
        if name not in names
    ]


def validate() -> list[str]:
    findings: list[str] = []
    try:
        manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        findings.append(f"final-admission manifest unreadable: {exc}")
    else:
        findings.extend(_manifest_findings(manifest))
    try:
        source = SOURCE_PATH.read_text(encoding="utf-8")
    except OSError as exc:
        findings.append(f"control-plane source unreadable: {exc}")
    else:
        findings.extend(validate_source_contract_text(source))
    findings.extend(_docs_findings())
    findings.extend(_test_findings())
    return findings


def main() -> int:
    findings = validate()
    print(f"JLMIRROR Wave 1 final admission profile: {PROFILE}")
    print(f"Repository root: {ROOT}")
    if findings:
        print(f"RESULT: FAIL — {len(findings)} finding(s)")
        for finding in findings:
            print(f"- {finding}")
        return 1
    print("RESULT: PASS — serial checks cannot substitute for revision-bound final admission authority")
    print("NOTE: PASS is conformance evidence only; final-admission mechanism remains a replaceable C2 choice.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
