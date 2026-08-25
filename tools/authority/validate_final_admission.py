#!/usr/bin/env python3
"""Observer-only validator for the Wave 1 revision-bound final-admission contract."""

from __future__ import annotations

import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE_PATH = ROOT / "src" / "jlmirror_authority" / "control_plane.py"
MODEL_PATH = ROOT / "src" / "jlmirror_authority" / "model.py"
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
    "resource_scope_mode": "required_for_resource_forbidden_otherwise",
    "required_common_bindings": [
        "admission_revision",
        "authorization_policy_revision",
        "principal_authority_revision",
        "principal_id",
        "principal_credential_generation",
        "action",
        "resource_scope",
        "executing_runtime_authority_revision",
        "executing_runtime_profile_id",
        "executing_runtime_generation",
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
    "cross_tenant_executing_runtime_profile": "runtime.control-plane@1",
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
    "RESOURCE SCOPE ABSENCE != RESOURCE AUTHORITY",
    "DESTINATION RUNTIME GENERATION != EXECUTING RUNTIME AUTHORITY",
    "FINAL ADMISSION SNAPSHOT != DURABLE EFFECT AUTHORITY",
)

REQUIRED_TEST_NAMES = (
    "test_serial_green_without_final_admission_authority_fails_closed",
    "test_malformed_or_noncurrent_final_admission_fails_closed",
    "test_final_principal_or_action_binding_mismatch_fails_closed",
    "test_resource_declaration_requires_explicit_scope",
    "test_non_resource_declaration_rejects_resource_scope",
    "test_same_action_different_resource_scope_cannot_reuse_final_evidence",
    "test_tenant_final_admission_requires_executing_runtime_binding",
    "test_tenant_final_admission_rejects_wrong_executing_runtime_profile",
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


def validate_source_contract_text(text: str, model_text: str) -> list[str]:
    try:
        tree = ast.parse(text)
        model_tree = ast.parse(model_text)
    except SyntaxError as exc:
        return [f"authority source is not parseable: {exc}"]

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
        evidence_text = ast.unparse(evidence)
        for token in (
            "executing_runtime_authority_revision",
            "executing_runtime_profile_id",
            "executing_runtime_generation",
            "every final admission must bind current executing-runtime authority",
        ):
            if token not in evidence_text:
                findings.append(f"FinalAdmissionEvidence does not fail closed on runtime binding: {token}")

    declaration = _named_class(model_tree, "AuthorizationDeclaration")
    if declaration is None:
        findings.append("AuthorizationDeclaration class is missing")
    else:
        declaration_text = ast.unparse(declaration)
        for token in (
            "ScopeClass.RESOURCE",
            "resource_scope is None",
            "resource_scope is valid only for scope=resource",
        ):
            if token not in declaration_text:
                findings.append(f"AuthorizationDeclaration resource-scope contract missing: {token}")

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
        resource_scope_refs = [
            node
            for node in ast.walk(helper)
            if isinstance(node, ast.Attribute) and node.attr == "resource_scope"
        ]
        if len(resource_scope_refs) < 2:
            findings.append("final-admission helper does not bind exact resource_scope")
        helper_text = ast.unparse(helper)
        for token in (
            "executing_runtime_authority_revision",
            "executing_runtime_profile_id",
            "executing_runtime_generation",
            "runtime_binding.runtime_profile_id",
        ):
            if token not in helper_text:
                findings.append(f"final-admission helper does not bind executing runtime: {token}")

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
        "executing-runtime authority",
        "resource scope",
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
        model_source = MODEL_PATH.read_text(encoding="utf-8")
    except OSError as exc:
        findings.append(f"authority source unreadable: {exc}")
    else:
        findings.extend(validate_source_contract_text(source, model_source))
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
    print("RESULT: PASS — final admission binds resource and current executing-runtime authority")
    print("NOTE: PASS is conformance evidence only; final-admission mechanism remains a replaceable C2 choice.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
