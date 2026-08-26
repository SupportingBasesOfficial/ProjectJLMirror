from __future__ import annotations

import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AUTHORITY = ROOT / "src/jlmirror_release/authority.py"
VERIFICATION = ROOT / "src/jlmirror_release/verification.py"
TESTS = ROOT / "tests/wave3/test_release.py"
POLICY_TESTS = ROOT / "tests/wave3/test_release_policy_lineage.py"
MANIFEST = ROOT / "implementation/wave-3/IMPLEMENTATION_MANIFEST.json"

REQUIRED_LAWS = {
    "POST-EFFECT RUNTIME EVIDENCE != RUNTIME GATE-SET AUTHORITY",
    "SAME DEPLOYMENT OPERATION != REPINNABLE RUNTIME REQUIREMENTS",
    "RUNTIME REQUIREMENTS MUST PRECEDE EFFECTFUL DEPLOYMENT",
    "RUNTIME VERIFICATION POLICY CURRENTNESS != DIFFERENT PRE-EFFECT GATE POLICY LINEAGE",
}
REQUIRED_FORBIDDEN = {
    "post_effect_runtime_requirements_repin",
    "same_operation_id_for_changed_runtime_requirements",
    "runtime_verification_evidence_embedded_requirements_authority",
    "runtime_requirements_not_persisted_before_effect",
    "rotated_runtime_release_policy_evidence_for_stale_pre_effect_gate_set",
}
REQUIRED_TESTS = {
    "test_runtime_requirements_are_validated_before_effectful_admission",
    "test_runtime_requirements_bind_admission_release_policy_evidence",
    "test_runtime_requirements_target_post_effect_version",
    "test_same_operation_cannot_repin_runtime_requirements",
    "test_runtime_requirements_cannot_be_empty_duplicate_unknown_or_incomplete",
    "test_runtime_requirements_cannot_be_replayed_across_scope_or_target_version",
    "test_health_gate_cannot_be_replayed_across_target_state_version",
    "test_runtime_health_gate_set_must_match_requirements_exactly",
    "test_runtime_verification_cannot_rotate_release_policy_lineage_after_gate_set_authorized",
    "test_effectful_deployment_cannot_complete_with_different_runtime_release_policy_lineage",
}


def fail(message: str) -> None:
    raise SystemExit(f"WAVE3 RUNTIME REQUIREMENTS VALIDATION FAILED: {message}")


def parse(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def class_node(tree: ast.Module, name: str) -> ast.ClassDef:
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == name:
            return node
    fail(f"missing class {name}")


def dataclass_fields(node: ast.ClassDef) -> set[str]:
    result: set[str] = set()
    for item in node.body:
        if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
            result.add(item.target.id)
    return result


def function_node(tree: ast.Module, name: str) -> ast.FunctionDef:
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    fail(f"missing function {name}")


def method_node(node: ast.ClassDef, name: str) -> ast.FunctionDef:
    for item in node.body:
        if isinstance(item, ast.FunctionDef) and item.name == name:
            return item
    fail(f"missing method {node.name}.{name}")


def source_segment(path: Path, node: ast.AST) -> str:
    text = path.read_text(encoding="utf-8")
    segment = ast.get_source_segment(text, node)
    if segment is None:
        fail(f"cannot read source segment from {path}")
    return segment


def validate() -> None:
    authority_tree = parse(AUTHORITY)
    verification_tree = parse(VERIFICATION)
    tests_tree = parse(TESTS)
    policy_tests_tree = parse(POLICY_TESTS)

    requirements_cls = class_node(verification_tree, "RuntimeVerificationRequirements")
    requirements_fields = dataclass_fields(requirements_cls)
    required_requirement_fields = {
        "authority_profile_and_version",
        "evidence_reference",
        "scope_binding",
        "release_target_state_version",
        "release_policy_profile_and_version",
        "release_policy_evidence_reference",
        "required_reliability_profile_ids",
        "required_health_profile_ids",
        "current",
    }
    if requirements_fields != required_requirement_fields:
        fail(f"RuntimeVerificationRequirements field set drift: {sorted(requirements_fields)}")

    runtime_evidence_cls = class_node(verification_tree, "RuntimeVerificationEvidence")
    runtime_evidence_fields = dataclass_fields(runtime_evidence_cls)
    forbidden_runtime_evidence_fields = {
        "requirements",
        "required_reliability_profile_ids",
        "required_health_profile_ids",
    }
    leaked = runtime_evidence_fields & forbidden_runtime_evidence_fields
    if leaked:
        fail(f"post-effect runtime evidence regained gate-set authority: {sorted(leaked)}")

    admission_cls = class_node(authority_tree, "DeploymentAdmissionEvidence")
    admission_fields = dataclass_fields(admission_cls)
    if "runtime_verification_requirements" not in admission_fields:
        fail("deployment admission no longer requires pre-effect runtime requirements")

    record_cls = class_node(authority_tree, "DeploymentRecord")
    record_fields = dataclass_fields(record_cls)
    for field in ("runtime_verification_requirements", "runtime_requirements_evidence_reference"):
        if field not in record_fields:
            fail(f"durable deployment record no longer persists {field}")

    require_admission = function_node(authority_tree, "require_deployment_admission")
    admission_source = source_segment(AUTHORITY, require_admission)
    required_admission_fragments = (
        "evidence.runtime_verification_requirements.validate_for(",
        "expected_release_target_state_version=intent.expected_release_target_state_version + 1",
        "expected_release_policy_evidence_reference=gate_map[\"release_policy\"].evidence_reference",
    )
    for fragment in required_admission_fragments:
        if fragment not in admission_source:
            fail(f"pre-effect admission requirement binding missing: {fragment}")

    authority_cls = class_node(authority_tree, "DeploymentAuthority")
    create_or_observe = method_node(authority_cls, "create_or_observe")
    create_source = source_segment(AUTHORITY, create_or_observe)
    for fragment in (
        "existing.runtime_verification_requirements != admission.runtime_verification_requirements",
        "same deployment operation cannot replace persisted runtime verification requirements",
        "runtime_verification_requirements=admission.runtime_verification_requirements",
        "runtime_requirements_evidence_reference=admission.runtime_verification_requirements.evidence_reference",
    ):
        if fragment not in create_source:
            fail(f"deployment create-or-observe requirement persistence/repin invariant missing: {fragment}")

    observe_effect = method_node(authority_cls, "observe_effect")
    observe_source = source_segment(AUTHORITY, observe_effect)
    if "confirmed deployment target version differs from pre-authorized runtime verification requirements" not in observe_source:
        fail("effect confirmation no longer binds the resulting target-state version to pre-authorized requirements")

    complete_runtime = method_node(authority_cls, "complete_runtime_verification")
    complete_source = source_segment(AUTHORITY, complete_runtime)
    if "record.runtime_verification_requirements" not in complete_source:
        fail("runtime verification no longer consumes the persisted pre-effect requirements")
    if "evidence.requirements" in complete_source:
        fail("runtime verification is consuming post-effect evidence-owned requirements")

    verify_runtime_fn = function_node(verification_tree, "verify_runtime")
    parameter_names = [arg.arg for arg in verify_runtime_fn.args.args]
    if parameter_names[:3] != ["intent", "evidence", "requirements"]:
        fail(f"verify_runtime must receive requirements separately from evidence: {parameter_names}")
    verify_source = source_segment(VERIFICATION, verify_runtime_fn)
    for fragment in (
        "runtime health evidence must match the exact release-policy-required gate set",
        "health gate evidence is bound to a different release-target state version",
        "runtime verification is using a different release-policy profile",
        "runtime verification release-policy evidence differs from the pre-effect requirements policy lineage",
        "expected_release_policy_evidence_reference=evidence.release_policy_evidence_reference",
    ):
        if fragment not in verify_source:
            fail(f"runtime verification fail-closed invariant missing: {fragment}")

    test_names = {
        node.name
        for tree in (tests_tree, policy_tests_tree)
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name.startswith("test_")
    }
    missing_tests = REQUIRED_TESTS - test_names
    if missing_tests:
        fail("missing adversarial tests: " + ",".join(sorted(missing_tests)))

    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    laws = set(manifest.get("canonical_release_laws", []))
    forbidden = set(manifest.get("forbidden_substitutions", []))
    if not REQUIRED_LAWS.issubset(laws):
        fail("implementation manifest is missing pre-effect runtime-requirement laws")
    if not REQUIRED_FORBIDDEN.issubset(forbidden):
        fail("implementation manifest is missing runtime-requirement anti-laundering substitutions")

    print(
        "WAVE3 RUNTIME REQUIREMENTS VALIDATION: PASS — runtime gate requirements are pre-effect, "
        "release-policy-lineage-bound, durable and non-repinnable."
    )


if __name__ == "__main__":
    validate()
