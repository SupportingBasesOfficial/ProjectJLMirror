#!/usr/bin/env python3
"""Observer-only validation for Wave 1 identity/authority skeleton."""

from __future__ import annotations

import ast
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from jlmirror_authority.runtime_profiles import WAVE1_RUNTIME_BINDINGS  # noqa: E402
from tools.authority.fence_sql_contract import (  # noqa: E402
    EFFECT_ELIGIBLE_PREDECESSOR_PREDICATE,
    validate_fence_revalidation_sql_text,
    validate_fence_sql_text,
)
from tools.authority.wave1_scope import (  # noqa: E402
    AUTHORITY_BASE_SHA,
    validate_wave1_scope,
)
from tools.contracts.core import build_bundle  # noqa: E402

PROFILE = "jlmirror-wave1-authority/v1"
AUTHORITY_BASE = "main@5b56ad94566b48b72a993ee8f5cf7e983127ab21"
EXPECTED_SLICES = [
    "impl.identity-bff@1",
    "impl.control-plane@1",
    "impl.platform-runtime@1",
]
EXPECTED_RUNTIME_PROFILES = [
    "runtime.web-bff@1",
    "runtime.api@1",
    "runtime.control-plane@1",
]
EXPECTED_PRINCIPAL_PROFILES = [
    "principal.web-bff@1",
    "principal.application-serving@1",
    "principal.control-plane@1",
]
EXPECTED_C2 = [
    "identity_provider",
    "session_store",
    "csrf_mechanism",
    "workload_identity_issuer_attestation_backend",
    "service_mesh",
    "secret_manager_kms",
    "configuration_distribution",
    "orchestrator_scheduler",
    "ingress_load_balancer",
    "physical_environment_mapping",
]
EXPECTED_FORBIDDEN_SUBSTITUTIONS = [
    "session_valid_for_current_authorization",
    "privileged_human_without_current_authentication_strength",
    "authentication_strength_for_other_principal",
    "malformed_adapter_evidence_for_authority",
    "not_yet_current_browser_transaction_for_authentication",
    "noncanonical_browser_session_handle_for_session_authority",
    "noncanonical_authority_input_before_c2_adapter",
    "workload_identity_for_tenant_authority",
    "network_presence_for_trust",
    "environment_label_for_authorization",
    "caller_tenant_id_for_tenant_context",
    "cross_tenant_platform_authority_through_application_runtime",
    "untyped_config_for_classified_config",
    "self_asserted_configuration_schema_for_current_authority",
    "non_active_fence_state_for_effect_authority",
    "unvalidated_persisted_fence_state_for_current_authority",
    "fence_token_for_effect_absence",
    "secret_reference_for_secret_value",
    "out_of_scope_git_delta_for_wave1_authority",
]
EXPECTED_MANIFEST = {
    "wave_id": "wave-1.identity-authority-skeleton@1",
    "authority_base": AUTHORITY_BASE,
    "implementation_slices": EXPECTED_SLICES,
    "scope": "authority_skeleton_only",
    "product_feature_activation": "none",
    "runtime_profiles": EXPECTED_RUNTIME_PROFILES,
    "principal_profiles": EXPECTED_PRINCIPAL_PROFILES,
    "closed_protocol_profiles": ["IR-D-001", "IR-D-002", "IR-D-003"],
    "residual_c2_choices_not_selected": EXPECTED_C2,
    "forbidden_authority_substitutions": EXPECTED_FORBIDDEN_SUBSTITUTIONS,
    "next_wave_authorized": False,
}
EXPECTED_RUNTIME_BINDINGS = {
    "runtime.web-bff@1": {
        "principal_class": "principal.web-bff@1",
        "lifecycle_class": "lifecycle.serving-replica@1",
        "isolation_class": "isolation.confidential-web@1",
        "ingress_profile": "ingress.public-browser@1",
        "egress_profiles": ["egress.platform-bounded@1"],
        "secret_reference_classes": [
            "secretref.service-communication@1",
            "secretref.web-session@1",
        ],
        "resource_profile": "resource.web@1",
        "allowed_environment_classes": [
            "environment.development@1",
            "environment.production@1",
            "environment.validation@1",
        ],
    },
    "runtime.api@1": {
        "principal_class": "principal.application-serving@1",
        "lifecycle_class": "lifecycle.serving-replica@1",
        "isolation_class": "isolation.application-serving@1",
        "ingress_profile": "ingress.authenticated-api@1",
        "egress_profiles": ["egress.platform-bounded@1"],
        "secret_reference_classes": [
            "secretref.service-communication@1",
            "secretref.state-port@1",
        ],
        "resource_profile": "resource.api@1",
        "allowed_environment_classes": [
            "environment.development@1",
            "environment.production@1",
            "environment.validation@1",
        ],
    },
    "runtime.control-plane@1": {
        "principal_class": "principal.control-plane@1",
        "lifecycle_class": "lifecycle.control-plane-serving@1",
        "isolation_class": "isolation.control-plane@1",
        "ingress_profile": "ingress.privileged-platform@1",
        "egress_profiles": ["egress.platform-bounded@1"],
        "secret_reference_classes": [
            "secretref.service-communication@1",
            "secretref.state-port@1",
        ],
        "resource_profile": "resource.control-plane@1",
        "allowed_environment_classes": [
            "environment.development@1",
            "environment.production@1",
            "environment.validation@1",
        ],
    },
}


def _authority_base_findings() -> list[str]:
    expected = f"main@{AUTHORITY_BASE_SHA}"
    return [] if AUTHORITY_BASE == expected else [
        f"Wave 1 validator authority-base drift: manifest={AUTHORITY_BASE} scope_guard={expected}"
    ]


def _third_party_import_findings() -> list[str]:
    findings: list[str] = []
    stdlib = set(sys.stdlib_module_names)
    for path in sorted((SRC / "jlmirror_authority").glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [alias.name.split(".")[0] for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                if node.level:
                    continue
                names = [(node.module or "").split(".")[0]]
            else:
                continue
            for name in names:
                if name and name not in stdlib and name != "jlmirror_authority":
                    findings.append(
                        f"third-party/runtime dependency is not accepted in Wave 1 core: {path}:{name}"
                    )
    return findings


def _normalize_runtime_binding(binding: object) -> dict[str, object] | None:
    required_attributes = (
        "runtime_profile_id",
        "principal_class",
        "lifecycle_class",
        "isolation_class",
        "ingress_profile",
        "egress_profiles",
        "secret_reference_classes",
        "resource_profile",
        "allowed_environment_classes",
    )
    if any(not hasattr(binding, name) for name in required_attributes):
        return None
    try:
        environments = sorted(environment.value for environment in binding.allowed_environment_classes)
        return {
            "runtime_profile_id": binding.runtime_profile_id,
            "principal_class": binding.principal_class,
            "lifecycle_class": binding.lifecycle_class,
            "isolation_class": binding.isolation_class,
            "ingress_profile": binding.ingress_profile,
            "egress_profiles": sorted(binding.egress_profiles),
            "secret_reference_classes": sorted(binding.secret_reference_classes),
            "resource_profile": binding.resource_profile,
            "allowed_environment_classes": environments,
        }
    except (AttributeError, TypeError, ValueError):
        return None


def _runtime_semantic_binding_findings(bindings=None) -> list[str]:
    bindings = WAVE1_RUNTIME_BINDINGS if bindings is None else bindings
    if isinstance(bindings, (str, bytes)):
        return ["Wave 1 runtime semantic bindings must be an exact collection"]
    try:
        values = list(bindings)
    except TypeError:
        return ["Wave 1 runtime semantic bindings are malformed"]

    normalized_by_id: dict[str, dict[str, object]] = {}
    findings: list[str] = []
    for binding in values:
        normalized = _normalize_runtime_binding(binding)
        if normalized is None:
            findings.append("Wave 1 runtime semantic binding is malformed")
            continue
        runtime_id = normalized.pop("runtime_profile_id")
        if not isinstance(runtime_id, str):
            findings.append("Wave 1 runtime semantic binding has non-string runtime id")
            continue
        if runtime_id in normalized_by_id:
            findings.append(f"Wave 1 runtime semantic binding is duplicated: {runtime_id}")
            continue
        normalized_by_id[runtime_id] = normalized

    expected_ids = set(EXPECTED_RUNTIME_BINDINGS)
    actual_ids = set(normalized_by_id)
    for runtime_id in sorted(expected_ids - actual_ids):
        findings.append(f"Wave 1 runtime semantic binding missing: {runtime_id}")
    for runtime_id in sorted(actual_ids - expected_ids):
        findings.append(f"Wave 1 runtime semantic binding is outside authorized set: {runtime_id}")
    for runtime_id in sorted(expected_ids & actual_ids):
        if normalized_by_id[runtime_id] != EXPECTED_RUNTIME_BINDINGS[runtime_id]:
            findings.append(f"Wave 1 runtime semantic join drift: {runtime_id}")
    return findings


def _runtime_catalog_findings() -> list[str]:
    bundle = build_bundle(ROOT)
    catalog_ids = {record["id"] for record in bundle["profile_catalog"]["records"]}
    required: set[str] = set()
    for binding in WAVE1_RUNTIME_BINDINGS:
        required.update(
            {
                binding.runtime_profile_id,
                binding.principal_class,
                binding.lifecycle_class,
                binding.isolation_class,
                binding.ingress_profile,
                binding.resource_profile,
                *binding.egress_profiles,
                *binding.secret_reference_classes,
                *(environment.value for environment in binding.allowed_environment_classes),
            }
        )
    missing = sorted(required - catalog_ids)
    return [
        f"Wave 1 runtime binding references unknown canonical profile: {value}"
        for value in missing
    ]


def _fence_sql_findings() -> list[str]:
    primary = ROOT / "sql" / "wave1" / "001_platform_authority_fence.sql"
    revalidation = ROOT / "sql" / "wave1" / "002_revalidate_authority_fence_contract.sql"
    findings: list[str] = []
    try:
        text = primary.read_text(encoding="utf-8")
    except OSError as exc:
        return [f"IR-D-003 primary fence SQL contract unreadable: {exc}"]
    try:
        revalidation_text = revalidation.read_text(encoding="utf-8")
    except OSError as exc:
        findings.append(f"IR-D-003 persisted fence revalidation migration unreadable: {exc}")
        revalidation_text = ""

    default_revoke = (
        "ALTER DEFAULT PRIVILEGES IN SCHEMA platform\n"
        "    REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC;"
    )
    first_function = "CREATE OR REPLACE FUNCTION platform.initialize_authority_fence("
    required_fragments = (
        "current_fence_epoch bigint NOT NULL CHECK (current_fence_epoch > 0)",
        "CHECK (btrim(fence_scope_id) <> '')",
        "CHECK (btrim(current_generation_id) <> '')",
        "CHECK (btrim(authority_state) <> '')",
        "ON CONFLICT (fence_scope_id) DO NOTHING",
        "current_fence_epoch = current_fence_epoch + 1",
        "current_fence_epoch = p_expected_predecessor_epoch",
        "current_generation_id = p_expected_predecessor_generation_id",
        EFFECT_ELIGIBLE_PREDECESSOR_PREDICATE,
        "current_fence_epoch < 9223372036854775807",
        "SECURITY INVOKER",
        default_revoke,
        "REVOKE ALL ON TABLE platform.authority_fences FROM PUBLIC;",
        "REVOKE ALL ON FUNCTION platform.initialize_authority_fence(text, text, text) FROM PUBLIC;",
        "REVOKE ALL ON FUNCTION platform.advance_authority_fence(text, bigint, text, text, text) FROM PUBLIC;",
        "same PostgreSQL transaction",
    )
    findings.extend(
        f"IR-D-003 SQL contract missing required invariant: {fragment}"
        for fragment in required_fragments
        if fragment not in text
    )
    findings.extend(validate_fence_sql_text(text))
    if revalidation_text:
        findings.extend(validate_fence_revalidation_sql_text(revalidation_text))
    if default_revoke in text and first_function in text and text.index(default_revoke) > text.index(first_function):
        findings.append(
            "IR-D-003 SQL default PUBLIC function EXECUTE revocation must precede authority function creation"
        )
    return findings


def _required_boundary_source_findings() -> list[str]:
    required_files = {
        "browser.py",
        "session.py",
        "machine.py",
        "workload.py",
        "control_plane.py",
        "fencing.py",
        "config.py",
        "runtime_profiles.py",
    }
    present = {path.name for path in (SRC / "jlmirror_authority").glob("*.py")}
    return [
        f"Wave 1 required authority boundary source missing: {name}"
        for name in sorted(required_files - present)
    ]


def _no_product_route_findings() -> list[str]:
    findings: list[str] = []
    forbidden = ("@app.route", "@router.", "FastAPI(", "Flask(", "express(", "listen(")
    for path in sorted((SRC / "jlmirror_authority").glob("*.py")):
        text = path.read_text(encoding="utf-8")
        for token in forbidden:
            if token in text:
                findings.append(
                    f"Wave 1 portable authority core must not register Product/HTTP routes: {path}:{token}"
                )
    return findings


def _implementation_manifest_findings() -> list[str]:
    path = ROOT / "implementation" / "wave-1" / "IMPLEMENTATION_MANIFEST.json"
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"Wave 1 implementation manifest unreadable: {exc}"]

    if not isinstance(manifest, dict):
        return ["Wave 1 implementation manifest must be a JSON object"]

    findings: list[str] = []
    actual_keys = set(manifest)
    expected_keys = set(EXPECTED_MANIFEST)
    for key in sorted(expected_keys - actual_keys):
        findings.append(f"Wave 1 implementation manifest missing canonical field: {key}")
    for key in sorted(actual_keys - expected_keys):
        findings.append(f"Wave 1 implementation manifest contains unmodeled field: {key}")
    for key, expected in EXPECTED_MANIFEST.items():
        if key in manifest and manifest[key] != expected:
            findings.append(f"Wave 1 implementation manifest field drift: {key}")
    return findings


def validate() -> list[str]:
    findings: list[str] = []
    findings.extend(_authority_base_findings())
    findings.extend(validate_wave1_scope(ROOT))
    findings.extend(_third_party_import_findings())
    findings.extend(_runtime_semantic_binding_findings())
    findings.extend(_runtime_catalog_findings())
    findings.extend(_fence_sql_findings())
    findings.extend(_required_boundary_source_findings())
    findings.extend(_no_product_route_findings())
    findings.extend(_implementation_manifest_findings())
    return findings


def main() -> int:
    findings = validate()
    print(f"JLMIRROR Wave 1 authority profile: {PROFILE}")
    print(f"Repository root: {ROOT}")
    if findings:
        print("RESULT: FAIL")
        for finding in findings:
            print(f"- {finding}")
        return 1
    print(
        "RESULT: PASS — Wave 1 authority skeleton preserves accepted "
        "scope/profile/session/currentness/fence boundaries"
    )
    print("NOTE: PASS is conformance evidence only; C2 adapters remain non-canonical until accepted.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
