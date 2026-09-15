from __future__ import annotations

import json
import re
import subprocess
import unicodedata
from pathlib import Path
from typing import Any

AUTHORIZATION_MANIFEST = "implementation/g2-monitoring-source-onboarding-authorization/AUTHORIZATION_MANIFEST.json"
EXPECTED_HEAD_PREFIX = "impl/g2-monitoring-source-onboarding"
EXPECTED_LABEL = "jlmirror-slice:g2-monitoring-source-onboarding"
EXPECTED_CLAIM_PATH = "implementation/g2-monitoring-source-onboarding/IMPLEMENTATION_CLAIM.json"
EXPECTED_AUTHORIZATION_ID = "g2.monitoring-source-onboarding@1"
EXPECTED_SLICE_ID = EXPECTED_AUTHORIZATION_ID
EXPECTED_RULE = "every_changed_path_must_match_canonical_base_policy"
EXPECTED_SEMANTIC_RULE = "candidate_executable_artifacts_must_not_introduce_forbidden_g3_or_parallel_monitoring_authority"
EXPECTED_ATTESTATION_COMMAND = "/jlmirror-g2-scope-attest"
EXPECTED_READINESS_COMMAND = "/jlmirror-g2-scope-ready"
EXPECTED_STATUS_CONTEXT = "JLMIRROR / g2-monitoring-source-onboarding-implementation-scope"
EXPECTED_READY_CONTEXT = "JLMIRROR / g2-monitoring-source-onboarding-merge-readiness"
EXPECTED_RUNTIME_WORKFLOW = ".github/workflows/g2-monitoring-source-onboarding-runtime.yml"
EXPECTED_RUNTIME_NAME = "JLMIRROR G2 Monitoring Source Onboarding Runtime"
EXPECTED_RUNTIME_ENTRYPOINT = "python tools/g2/run_monitoring_source_onboarding_runtime.py"
EXPECTED_PREFIXES = (
    "apps/g2-monitoring-source-onboarding/",
    "contracts/g2-monitoring-source-onboarding/",
    "implementation/g2-monitoring-source-onboarding/",
    "tests/g2/",
    "tools/g2/",
)
EXPECTED_EXACT = (EXPECTED_RUNTIME_WORKFLOW,)
EXPECTED_FORBIDDEN_PATH_TOKENS = (
    "inventory", "monitoring-resource", "monitoring_resource", "metric", "problem", "health", "alert", "replacement", "cutover",
)
EXPECTED_FORBIDDEN_CODE_MARKERS = (
    "monitoring_resource", "host_inventory", "resource_inventory", "resource_ingestion", "metric", "metric_definition",
    "metric_value", "metric_history", "metric_current_state", "metric_observation", "problem", "problem_state", "health",
    "health_status", "health_projection", "monitoring_to_alerting", "alert_creation", "alert_policy", "alerting.",
    "ack_handler", "ack_notification_escalation", "acknowledge", "acknowledgement", "notification", "escalation",
    "itsm", "automation", "aiops", "finops", "commercial", "production_deployment", "production_c3", "c3_numerics",
    "secret_manager", "egress_transport", "provider_native_authority", "provider_authorization", "raw_credentials",
    "raw_provider_credentials", "source_replacement", "source_cutover", "replacement_candidate", "replace_source_instance",
    "candidate_generation", "create table monitoring.", "create schema monitoring", "src/jlmirror_monitoring", "sql/wave4",
)
EXPECTED_SEMANTIC_SCAN_PREFIXES = EXPECTED_PREFIXES
RUNTIME_ALLOWED_ACTIONS = ("actions/checkout", "actions/setup-python", "actions/setup-node")
STRUCTURAL_MARKERS = {"create table monitoring.", "create schema monitoring", "src/jlmirror_monitoring", "sql/wave4", "alerting."}
AUTHORIZED_IDENTIFIER_EXCEPTIONS = {"browserautomation"}
PERSISTENCE_RECEIVERS = {"database", "db", "repository", "repo", "prisma", "postgres", "postgresql", "pg", "sqlalchemy", "psycopg"}
PERSISTENCE_WRITES = {"insert", "update", "delete", "save", "upsert", "execute", "executemany", "commit", "persist"}
PROVIDER_AUTHORITY_TERMS = {"role", "roles", "permission", "permissions", "admin", "authorize", "authorization", "authority", "acl"}
SECRET_TERMS = {"password", "passwd", "secret", "token", "apikey", "credential", "credentials"}
SECRET_SINK_TERMS = {"insert", "update", "save", "upsert", "persist", "log", "logger", "print", "response", "serialize", "write"}


def git(root: Path, *args: str) -> str:
    return subprocess.check_output(["git", "-C", str(root), *args], text=True, stderr=subprocess.DEVNULL).strip()


def git_bytes(root: Path, *args: str) -> bytes:
    return subprocess.check_output(["git", "-C", str(root), *args], stderr=subprocess.DEVNULL)


def policy_from_base(root: Path, base_sha: str) -> dict[str, Any]:
    data = json.loads(git_bytes(root, "show", f"{base_sha}:{AUTHORIZATION_MANIFEST}").decode())
    policy = data.get("implementation_path_policy")
    if not isinstance(policy, dict):
        raise AssertionError("canonical base missing implementation_path_policy")
    if data.get("implementation_authority_after_merge") != "granted_for_exact_g2_monitoring_source_onboarding_only":
        raise AssertionError("canonical base does not grant exact G2 implementation authority")
    return policy


def configured_policy(policy: dict[str, Any]) -> None:
    expected = (
        ("implementation_pr_head_prefix", EXPECTED_HEAD_PREFIX, "head prefix"),
        ("implementation_pr_required_label", EXPECTED_LABEL, "required label"),
        ("implementation_claim_path", EXPECTED_CLAIM_PATH, "claim path"),
        ("implementation_claim_authorization_id", EXPECTED_AUTHORIZATION_ID, "claim authorization id"),
        ("implementation_pr_base_ref_policy", "must_equal_repository_default_branch", "base ref policy"),
        ("trusted_evaluator_event", "issue_comment", "trusted evaluator event"),
        ("trusted_scope_attestation_command", EXPECTED_ATTESTATION_COMMAND, "scope attestation command"),
        ("trusted_scope_readiness_command", EXPECTED_READINESS_COMMAND, "scope readiness command"),
        ("trusted_scope_status_context", EXPECTED_STATUS_CONTEXT, "scope status context"),
        ("trusted_scope_readiness_status_context", EXPECTED_READY_CONTEXT, "readiness status context"),
        ("trusted_scope_status_evidence_role", "evidence_only_not_standalone_merge_authority", "scope evidence role"),
        ("trusted_scope_concurrency_rule", "per_pr_cancel_in_progress", "scope concurrency rule"),
        ("candidate_controlled_relevance_inference", "forbidden", "candidate relevance inference"),
        ("diff_enforcement_rule", EXPECTED_RULE, "diff enforcement rule"),
        ("semantic_guard_rule", EXPECTED_SEMANTIC_RULE, "semantic guard rule"),
    )
    for key, value, label in expected:
        if policy.get(key) != value:
            raise AssertionError(f"{label} drift")
    if policy.get("trusted_status_creator_login") != "github-actions[bot]" or policy.get("trusted_status_creator_id") != 41898282:
        raise AssertionError("trusted status creator drift")
    if policy.get("same_repository_required") is not True:
        raise AssertionError("same repository requirement drift")
    if tuple(policy.get("allowed_prefixes", [])) != EXPECTED_PREFIXES:
        raise AssertionError("allowed prefixes drift")
    if tuple(policy.get("allowed_exact_paths", [])) != EXPECTED_EXACT:
        raise AssertionError("allowed exact paths drift")
    if tuple(policy.get("forbidden_path_tokens", [])) != EXPECTED_FORBIDDEN_PATH_TOKENS:
        raise AssertionError("forbidden path token set drift")
    if tuple(policy.get("forbidden_code_markers", [])) != EXPECTED_FORBIDDEN_CODE_MARKERS:
        raise AssertionError("forbidden code marker set drift")
    if tuple(policy.get("semantic_scan_prefixes", [])) != EXPECTED_SEMANTIC_SCAN_PREFIXES:
        raise AssertionError("semantic scan prefix set drift")


def matches_policy(path: str, policy: dict[str, Any]) -> bool:
    return path in policy["allowed_exact_paths"] or any(path.startswith(p) for p in policy["allowed_prefixes"])


def validate_paths(paths: list[str], policy: dict[str, Any]) -> list[str]:
    return [f"unauthorized G2 implementation path: {p}" for p in paths if not matches_policy(p, policy)]


def _decode_identifier_escapes(text: str) -> str:
    pattern = re.compile(r"\\u\{([0-9A-Fa-f]+)\}|\\u([0-9A-Fa-f]{4})")

    def replace(match: re.Match[str]) -> str:
        raw = match.group(1) or match.group(2)
        value = int(raw, 16)
        if value > 0x10FFFF or 0xD800 <= value <= 0xDFFF:
            return match.group(0)
        return chr(value)

    return pattern.sub(replace, text)


def _key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", unicodedata.normalize("NFKC", value).casefold())


def _split_components(value: str) -> list[str]:
    normalized = unicodedata.normalize("NFKC", value)
    normalized = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", normalized)
    return [_key(part) for part in re.split(r"[^A-Za-z0-9]+", normalized) if _key(part)]


def _raw_identifiers(text: str) -> list[str]:
    normalized = unicodedata.normalize("NFKC", _decode_identifier_escapes(text))
    return re.findall(r"[A-Za-z_][A-Za-z0-9_]*", normalized)


def _path_keys(path: str) -> set[str]:
    keys: set[str] = set()
    for part in re.split(r"[/\\]", unicodedata.normalize("NFKC", path)):
        full = _key(part)
        if full:
            keys.add(full)
        keys.update(_split_components(part))
    return keys


def _identifier_variants(marker: str) -> set[str]:
    key = _key(marker)
    if not key:
        return set()
    variants = {key, key + "s", key + "es"}
    if key.endswith("y") and len(key) > 1:
        variants.add(key[:-1] + "ies")
    return variants


def _identifier_hits_marker(identifier: str, marker: str) -> bool:
    full = _key(identifier)
    if not full or full in AUTHORIZED_IDENTIFIER_EXCEPTIONS:
        return False
    variants = _identifier_variants(marker)
    if full in variants:
        return True
    return bool(variants & set(_split_components(identifier)))


def _strip_comments(text: str) -> str:
    value = re.sub(r"/\*.*?\*/", " ", text, flags=re.DOTALL)
    value = re.sub(r"--[^\n]*", " ", value)
    return value


def _structural_semantic_errors(path: str, decoded: str) -> list[str]:
    errors: list[str] = []
    suffix = Path(path).suffix.casefold()
    folded = unicodedata.normalize("NFKC", decoded).casefold()
    uncommented = _strip_comments(folded)
    if suffix == ".sql":
        errors.append(f"G2-owned SQL artifact forbidden; accepted Monitoring persistence must be reused: {path}")
    if re.search(r"\b(?:create|alter|drop)\s+(?:table|schema)\b", uncommented):
        errors.append(f"G2-owned DDL forbidden; accepted Monitoring persistence must be reused: {path}")

    identifiers = _raw_identifiers(decoded)
    components: set[str] = set()
    for identifier in identifiers:
        components.update(_split_components(identifier))

    if "provider" in components and (components & PROVIDER_AUTHORITY_TERMS):
        errors.append(f"provider-native authorization/authority semantics forbidden in G2: {path}")

    receiver = "|".join(sorted(PERSISTENCE_RECEIVERS, key=len, reverse=True))
    write = "|".join(sorted(PERSISTENCE_WRITES, key=len, reverse=True))
    persistence_pattern = re.compile(rf"\b(?:{receiver})\s*(?:\.|\[\s*['\"])[^\n;]*?(?:{write})\s*(?:\]|\()", re.IGNORECASE)
    if persistence_pattern.search(decoded):
        errors.append(f"direct persistence write surface forbidden in G2 composition: {path}")

    if components & SECRET_TERMS and components & SECRET_SINK_TERMS:
        errors.append(f"raw secret persistence/exposure data-flow forbidden in G2: {path}")
    return errors


def validate_semantic_artifact(path: str, text: str, policy: dict[str, Any]) -> list[str]:
    if not any(path.startswith(p) for p in policy.get("semantic_scan_prefixes", [])):
        return []
    errors: list[str] = []
    if any(ord(ch) > 127 for ch in text):
        errors.append(f"non-ASCII text forbidden in governed G2 artifact: {path}")
    decoded = _decode_identifier_escapes(text)
    if any(ord(ch) > 127 for ch in decoded):
        errors.append(f"identifier escape decodes to non-ASCII text in governed G2 artifact: {path}")

    path_keys = _path_keys(path)
    for token in policy.get("forbidden_path_tokens", []):
        if _identifier_variants(token) & path_keys:
            errors.append(f"forbidden G2 semantic path token '{token}' in {path}")

    identifiers = _raw_identifiers(decoded)
    folded = unicodedata.normalize("NFKC", decoded).casefold()
    for marker in policy.get("forbidden_code_markers", []):
        if marker in STRUCTURAL_MARKERS:
            hit = unicodedata.normalize("NFKC", marker).casefold() in folded
        else:
            hit = any(_identifier_hits_marker(identifier, marker) for identifier in identifiers)
        if hit:
            errors.append(f"forbidden G2 semantic code marker '{marker}' in {path}")
    errors.extend(_structural_semantic_errors(path, decoded))
    return errors


def validate_runtime_workflow_text(text: str) -> list[str]:
    try:
        wf = json.loads(text)
    except json.JSONDecodeError:
        return ["runtime workflow must use canonical JSON-form YAML for semantic validation"]
    if not isinstance(wf, dict) or set(wf) != {"name", "on", "permissions", "jobs"}:
        return ["runtime workflow top-level shape drift"]
    errors: list[str] = []
    if wf.get("name") != EXPECTED_RUNTIME_NAME or wf.get("permissions") != {}:
        errors.append("runtime workflow authority drift")
    if wf.get("on") != {"pull_request": {}, "workflow_dispatch": {}}:
        errors.append("runtime workflow trigger set/config drift")
    jobs = wf.get("jobs")
    if not isinstance(jobs, dict) or set(jobs) != {"g2-runtime"}:
        return errors + ["runtime workflow job set drift"]
    job = jobs["g2-runtime"]
    if set(job) != {"runs-on", "steps"} or job.get("runs-on") != "ubuntu-latest":
        return errors + ["runtime workflow job shape drift"]
    steps = job.get("steps")
    if not isinstance(steps, list) or len(steps) != 4:
        return errors + ["runtime workflow must contain exactly four canonical steps"]
    for i, action in enumerate(RUNTIME_ALLOWED_ACTIONS):
        step = steps[i]
        if not isinstance(step, dict) or set(step) != {"uses"}:
            errors.append(f"runtime workflow setup step {i} shape drift")
            continue
        pieces = step["uses"].split("@", 1)
        if len(pieces) != 2:
            errors.append(f"runtime workflow setup step {i} pin drift")
            continue
        name, sha = pieces
        if name != action or len(sha) != 40 or not all(c in "0123456789abcdefABCDEF" for c in sha):
            errors.append(f"runtime workflow setup step {i} pin drift")
    if steps[3] != {"run": EXPECTED_RUNTIME_ENTRYPOINT}:
        errors.append("runtime workflow executable responsibility drift")
    return errors


def _claim(root: Path, head: str, path: str) -> dict[str, Any]:
    value = json.loads(git_bytes(root, "show", f"{head}:{path}").decode())
    if not isinstance(value, dict):
        raise AssertionError("G2 implementation claim must be a JSON object")
    return value


def validate(base_sha: str, head_sha: str, head_ref: str, labels: set[str], head_repo: str, base_repo: str, *, root: Path) -> tuple[bool, list[str]]:
    root = root.resolve()
    try:
        policy = policy_from_base(root, base_sha)
        configured_policy(policy)
        errors: list[str] = []
        if head_repo != base_repo:
            errors.append("G2 implementation PR must originate from the canonical repository")
        if not head_ref.startswith(EXPECTED_HEAD_PREFIX):
            errors.append("G2 implementation PR missing required canonical head prefix")
        if EXPECTED_LABEL not in labels:
            errors.append("G2 implementation PR missing required canonical label")
        try:
            claim = _claim(root, head_sha, EXPECTED_CLAIM_PATH)
            if claim.get("schema_version") != 1 or claim.get("authorization_id") != EXPECTED_AUTHORIZATION_ID or claim.get("slice_id") != EXPECTED_SLICE_ID:
                errors.append("G2 implementation claim drift")
        except Exception:
            errors.append("G2 implementation PR missing or malformed required claim")
        out = git(root, "diff", "--name-only", "--no-renames", f"{base_sha}...{head_sha}")
        paths = [p for p in out.splitlines() if p]
        if not paths:
            errors.append("attested G2 implementation PR has no changed paths")
        errors.extend(validate_paths(paths, policy))
        for path in paths:
            if any(path.startswith(p) for p in EXPECTED_SEMANTIC_SCAN_PREFIXES):
                try:
                    text = git_bytes(root, "show", f"{head_sha}:{path}").decode()
                except Exception:
                    errors.append(f"G2 semantic-scanned artifact must exist as UTF-8 text: {path}")
                else:
                    errors.extend(validate_semantic_artifact(path, text, policy))
        if EXPECTED_RUNTIME_WORKFLOW in paths:
            try:
                text = git_bytes(root, "show", f"{head_sha}:{EXPECTED_RUNTIME_WORKFLOW}").decode()
                errors.extend(validate_runtime_workflow_text(text))
            except Exception:
                errors.append("allowed G2 runtime workflow path must exist as UTF-8 text on candidate head")
        return True, errors
    except Exception as exc:
        return True, [str(exc)]
