from __future__ import annotations

import json
import subprocess
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "implementation/wave-3/IMPLEMENTATION_MANIFEST.json"
REGISTRY = ROOT / "implementation/wave-3/source-registry.json"

EXPECTED_BASE = "b1f5fb83d2aa53e981007dddd0b751e22db40eee"
EXPECTED_SLICES = ["impl.observability@1", "impl.release-supply-chain@1"]
EXPECTED_SOURCES = {
    "docs/12-observability-sre/10-observability-semantic-manifest.md": "80054d9a15fb82ba26a91c34f98b10964ab3c83d",
    "docs/14-deployment-release-supply-chain/11-release-semantic-manifest.md": "5bb4f7e50ab7eaa7d9162cd9e2f633a10c4d17ff",
    "docs/16-implementation-readiness/11-initial-implementation-sequencing.md": "74b70ab33047f92ae841732f2c7ebab243ca3347",
    "docs/16-implementation-readiness/15-implementation-slice-readiness-manifest.md": "fc810728322d928ce9a5f71243101a390384189a",
}
REQUIRED_FILES = (
    "src/jlmirror_observability/__init__.py",
    "src/jlmirror_observability/model.py",
    "src/jlmirror_observability/catalog.py",
    "src/jlmirror_observability/policy.py",
    "src/jlmirror_observability/pipeline.py",
    "src/jlmirror_release/__init__.py",
    "src/jlmirror_release/model.py",
    "src/jlmirror_release/authority.py",
    "src/jlmirror_release/provenance.py",
    "src/jlmirror_release/configuration.py",
    "src/jlmirror_release/compatibility.py",
    "src/jlmirror_release/verification.py",
    "src/jlmirror_release/recovery.py",
    "tests/wave3/test_observability.py",
    "tests/wave3/test_observability_catalog.py",
    "tests/wave3/test_observability_pipeline.py",
    "tests/wave3/test_release.py",
    "tests/wave3/test_release_provenance_compatibility.py",
    "implementation/wave-3/README.md",
    "implementation/wave-3/IMPLEMENTATION_MANIFEST.json",
    "implementation/wave-3/source-registry.json",
)
REQUIRED_OBSERVABILITY_LAWS = {
    "SEMANTIC CLASS != UNBOUNDED TENANT/RESOURCE IDENTIFIER",
    "OUTCOME TOKEN != ACCEPTED OUTCOME TAXONOMY",
    "NO_APPLICABLE_CASE != FREE-TEXT ASSERTION",
    "PRODUCT SELECTOR VALUE != PRODUCT AUTHORITY EVIDENCE",
}
REQUIRED_RELEASE_LAWS = {
    "PROMOTION EVIDENCE != INTERCHANGEABLE DEPLOYMENT EVIDENCE",
    "BOOLEAN CURRENT != EVIDENCE LINEAGE",
    "CURRENT POLICY PROFILE != SOURCE-TRUST TRANSITION LINEAGE",
    "ADMISSION BOOLEAN != SCOPED CURRENT-AUTHORITY PROOF",
    "RECONCILIATION BOOLEAN != RECONCILIATION AUTHORITY",
    "RELEASE OUTCOME WITHOUT RETAINED EVIDENCE != DURABLE RELEASE RECORD",
}
REQUIRED_FORBIDDEN_SUBSTITUTIONS = {
    "free_text_reason_for_observability_no_applicable_case",
    "stale_or_wrong_scope_evidence_for_observability_no_applicable_case",
    "raw_product_selector_string_or_boolean_for_product_authority",
    "deployment_or_catalog_presence_for_product_applicability",
    "boolean_or_current_build_policy_for_source_trust_transition_lineage",
    "boolean_current_for_build_release_policy",
    "boolean_current_for_builder_authority",
    "boolean_integrity_for_declared_inputs",
    "boolean_current_for_provenance_verifier",
    "boolean_artifact_lifecycle_for_promotion_eligibility",
    "mutable_build_provenance_or_sbom_record_alias",
    "boolean_current_for_promotion_principal_or_release_policy",
    "boolean_current_for_deployment_admission_authority",
    "unscoped_or_wrong_version_admission_evidence_for_current_authority",
    "boolean_current_for_reconciliation_authority",
    "unretained_admission_or_reconciliation_authority_evidence",
    "boolean_current_for_runtime_admission_configuration_policy_or_verifier",
    "boolean_current_for_health_admission_policy",
}
REQUIRED_CODE_TOKENS = {
    "src/jlmirror_observability/model.py": (
        "ALLOWED_SIGNAL_CLASSIFICATIONS",
        "ALLOWED_TENANT_SCOPE_CLASSES",
        "CANONICAL_OUTCOME_CLASSES",
        "operation_class must be a bounded namespaced semantic class",
        "metric operation_class must equal the record's stable operation_class",
    ),
    "src/jlmirror_observability/policy.py": (
        "class NoApplicableCaseEvidence",
        "class ProductApplicabilityEvidence",
        "evidence_reference",
        "scope_binding",
        "current",
        "expected_selector_id",
        "direct SLI NO_APPLICABLE_CASE requires evidence-backed disposition",
    ),
    "src/jlmirror_observability/catalog.py": (
        "resolve_product_applicability(self, evidence",
        "if evidence is None",
        "OPEN-OBS-037",
        "evidence.validate_for(expected_scope, expected_selector_id=self.product_selector)",
    ),
    "src/jlmirror_release/provenance.py": (
        "source_trust_policy_profile_and_version",
        "source_trust_policy_evidence_reference",
        "release_policy_evidence_reference",
        "builder_authority_evidence_reference",
        "declared_inputs_integrity_evidence_reference",
        "provenance_verifier_evidence_reference",
        "artifact_lifecycle_evidence_reference",
        "promotion_principal_authority_evidence_reference",
        "promotion_evidence_reference",
        "configuration_validation_evidence_reference",
        "rollout_compatibility_evidence_reference",
        "runtime_profile_set",
        "schema_state",
        "api_compatibility_family",
        "event_compatibility_set",
    ),
    "src/jlmirror_release/authority.py": (
        "class CurrentAuthorityEvidence",
        "_REQUIRED_ADMISSION_GATES",
        "admission_gate_evidence_references",
        "reconciliation_authority_evidence_reference",
        "release_target_state_version",
        "durable_target_evidence_reference",
        "runtime_verification_evidence_reference",
        "promotion and deployment use different configuration validation evidence",
        "promotion and deployment use different rollout compatibility evidence",
    ),
    "src/jlmirror_release/verification.py": (
        "runtime_admission_evidence_reference",
        "configuration_currentness_evidence_reference",
        "release_policy_evidence_reference",
        "verifier_authority_evidence_reference",
        "policy_evidence_reference",
    ),
}


def fail(message: str) -> None:
    raise SystemExit(f"WAVE3 VALIDATION FAILED: {message}")


def canonical_source_path(value: object) -> str:
    if not isinstance(value, str) or not value:
        fail(f"invalid source path: {value!r}")
    if "\\" in value or "//" in value:
        fail(f"non-canonical source path: {value!r}")
    pure = PurePosixPath(value)
    if pure.is_absolute() or value != str(pure):
        fail(f"non-canonical source path: {value!r}")
    if any(part in {".", "..", ""} for part in pure.parts):
        fail(f"non-canonical source path: {value!r}")
    if not pure.parts or pure.parts[0] != "docs" or pure.suffix != ".md":
        fail(f"source path must be canonical Markdown under docs/: {value!r}")
    return value


def git_blob_at(commit: str, path: str) -> str:
    proc = subprocess.run(
        ["git", "rev-parse", f"{commit}:{path}"], cwd=ROOT, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
    )
    if proc.returncode != 0:
        fail(f"cannot resolve accepted authority source {commit}:{path}: {proc.stderr.strip()}")
    return proc.stdout.strip()


def validate() -> None:
    for relative in REQUIRED_FILES:
        if not (ROOT / relative).is_file():
            fail(f"required Wave 3 file missing: {relative}")

    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if manifest.get("authority_base") != f"main@{EXPECTED_BASE}":
        fail("implementation manifest authority_base drift")
    if manifest.get("implementation_slices") != EXPECTED_SLICES:
        fail("implementation slice set/order drift")
    if manifest.get("scope") != "platform_observability_and_release_chain_substrate_only":
        fail("Wave 3 scope drift")
    if manifest.get("product_feature_activation") != "none":
        fail("Wave 3 cannot activate Product features")
    if manifest.get("next_wave_authorized") is not False:
        fail("Wave 4 cannot be authorized by Wave 3 implementation metadata")
    if not manifest.get("canonical_observability_laws") or not manifest.get("canonical_release_laws"):
        fail("Wave 3 canonical law sets cannot be empty")
    if not REQUIRED_OBSERVABILITY_LAWS.issubset(set(manifest.get("canonical_observability_laws", []))):
        fail("Wave 3 manifest is missing bounded/scoped observability laws")
    if not REQUIRED_RELEASE_LAWS.issubset(set(manifest.get("canonical_release_laws", []))):
        fail("Wave 3 manifest is missing release evidence-lineage laws")
    if not REQUIRED_FORBIDDEN_SUBSTITUTIONS.issubset(set(manifest.get("forbidden_substitutions", []))):
        fail("Wave 3 manifest is missing applicability/current-authority anti-laundering substitutions")
    if not manifest.get("residual_c2_choices_not_selected"):
        fail("Wave 3 must preserve explicit residual C2 choices")

    for relative, tokens in REQUIRED_CODE_TOKENS.items():
        text = (ROOT / relative).read_text(encoding="utf-8")
        for token in tokens:
            if token not in text:
                fail(f"Wave 3 invariant missing from {relative}: {token}")

    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    if set(registry) != {"accepted_authority_base", "sources"}:
        fail("source registry contains unknown or missing top-level fields")
    if registry.get("accepted_authority_base") != EXPECTED_BASE:
        fail("source registry accepted_authority_base drift")
    sources = registry.get("sources")
    if not isinstance(sources, list):
        fail("source registry sources must be a list")
    actual_registry: dict[str, str] = {}
    for source in sources:
        if not isinstance(source, dict) or set(source) != {"path", "git_blob_sha"}:
            fail("each source registry entry must contain only path and git_blob_sha")
        path = canonical_source_path(source.get("path"))
        sha = source.get("git_blob_sha")
        if path in actual_registry:
            fail(f"duplicate source path: {path}")
        if not isinstance(sha, str) or len(sha) != 40 or any(c not in "0123456789abcdef" for c in sha):
            fail(f"invalid source blob sha for {path}")
        actual_registry[path] = sha
    if actual_registry != EXPECTED_SOURCES:
        fail("Wave 3 source registry set/pins drift from accepted authority bundle")
    for path, expected_sha in EXPECTED_SOURCES.items():
        actual = git_blob_at(EXPECTED_BASE, path)
        if actual != expected_sha:
            fail(f"accepted-base binding mismatch for {path}: expected {expected_sha}, got {actual}")

    workflow = (ROOT / ".github/workflows/deterministic-assurance.yml").read_text(encoding="utf-8")
    required_workflow_fragments = (
        "PYTHONPATH=src python3 -m unittest discover -s tests/wave3 -p 'test_*.py'",
        "PYTHONPATH=src python3 tools/wave3/validate_wave3.py",
        "persist-credentials: false",
        "allow-unsafe-pr-checkout: false",
    )
    for fragment in required_workflow_fragments:
        if fragment not in workflow:
            fail(f"deterministic assurance workflow missing Wave 3/read-only invariant: {fragment}")

    print("WAVE3 VALIDATION: PASS — observability/release substrate remains pinned, bounded, evidence-lineage-safe and non-Product.")


if __name__ == "__main__":
    validate()
