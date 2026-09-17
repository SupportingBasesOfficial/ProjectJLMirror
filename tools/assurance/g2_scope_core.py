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
PERSISTENCE_RECEIVERS = {"database", "db", "repository", "repo", "prisma", "postgres", "postgresql", "pg", "sqlalchemy", "psycopg"}
PERSISTENCE_WRITES = {"insert", "update", "delete", "save", "upsert", "execute", "executemany", "commit", "persist"}
PROVIDER_AUTHORITY_TERMS = {"role", "roles", "permission", "permissions", "admin", "authorize", "authorization", "authority", "acl"}
SECRET_TERMS = {"password", "passwd", "secret", "token", "apikey", "credential", "credentials"}
SECRET_SINK_TERMS = {"insert", "update", "save", "upsert", "persist", "log", "logger", "print", "response", "serialize", "write", "send", "json", "end"}
DDL_OBJECTS = "table|schema|view|materialized\\s+view|index|sequence|type|function|procedure|trigger|extension|policy"


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
    normalized = re.sub(r"(?<=[A-Z])(?=[A-Z][a-z])", "_", normalized)
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


def _browser_automation_identifier(identifier: str) -> bool:
    parts = _split_components(identifier)
    return any(parts[i:i + 2] == ["browser", "automation"] for i in range(max(0, len(parts) - 1)))


def _identifier_hits_marker(identifier: str, marker: str) -> bool:
    full = _key(identifier)
    if not full:
        return False
    if _key(marker) == "automation" and _browser_automation_identifier(identifier):
        return False
    variants = _identifier_variants(marker)
    if full in variants:
        return True
    return bool(variants & set(_split_components(identifier)))


def _strip_comments(text: str) -> str:
    value = re.sub(r"/\*.*?\*/", " ", text, flags=re.DOTALL)
    value = re.sub(r"--[^\n]*", " ", value)
    return value


def _mask_authorized_browser_automation(text: str) -> str:
    value = re.sub(r"\bbrowser[\s_-]+automation(?:[\s_-]+tests?)?\b", "browser_e2e", text, flags=re.IGNORECASE)
    for identifier in _raw_identifiers(value):
        if _browser_automation_identifier(identifier):
            value = re.sub(rf"\b{re.escape(identifier)}\b", "browser_e2e", value)
    return value


def _persistence_aliases(decoded: str) -> set[str]:
    aliases = set(PERSISTENCE_RECEIVERS)
    changed = True
    while changed:
        changed = False
        receiver_pattern = "|".join(re.escape(name) for name in sorted(aliases, key=len, reverse=True))
        for match in re.finditer(rf"\b(?:const|let|var)\s+([A-Za-z_$][A-Za-z0-9_$]*)\s*=\s*(?:{receiver_pattern})\b", decoded):
            alias = match.group(1)
            if alias not in aliases:
                aliases.add(alias)
                changed = True
    return aliases


def _has_persistence_write(decoded: str) -> bool:
    aliases = _persistence_aliases(decoded)
    receiver = "|".join(re.escape(name) for name in sorted(aliases, key=len, reverse=True))
    write = "|".join(re.escape(name) for name in sorted(PERSISTENCE_WRITES, key=len, reverse=True))
    helper_invocation = r"(?:\.\s*(?:call|apply)\s*(?:\?\.\s*)?\(|(?:\?\.\s*)?\()"
    patterns = (
        rf"\b(?:{receiver})\s*\.\s*(?:{write})\s*{helper_invocation}",
        rf"\b(?:{receiver})\s*\[\s*['\"](?:{write})['\"]\s*\]\s*{helper_invocation}",
        rf"\b(?:const|let|var)\s*\{{[^}}]*\b(?:{write})\b[^}}]*\}}\s*=\s*(?:{receiver})\b",
    )
    return any(re.search(pattern, decoded, flags=re.IGNORECASE) for pattern in patterns)


def _has_secret_to_sink(decoded: str) -> bool:
    secret = "|".join(sorted(SECRET_TERMS, key=len, reverse=True))
    sink = "|".join(sorted(SECRET_SINK_TERMS, key=len, reverse=True))
    patterns = (
        rf"\b(?:{sink})\s*\([^)]*\b(?:{secret})\b",
        rf"\.\s*(?:{sink})\s*\([^)]*\b(?:{secret})\b",
        rf"\breturn\s+\{{[^}}]*\b(?:{secret})\b",
    )
    return any(re.search(pattern, decoded, flags=re.IGNORECASE | re.DOTALL) for pattern in patterns)


def _review_regex_eligible(text: str, index: int, previous_significant: str) -> bool:
    if not previous_significant or previous_significant in "(=:[,!&|?{};+*-~%^<>":
        return True
    prefix = text[max(0, index - 48):index]
    return bool(re.search(r"\b(?:await|case|delete|do|else|in|instanceof|new|return|throw|typeof|void|yield)\s*$", prefix))


def _review_mask_comments(text: str) -> str:
    chars = list(text)
    quote: str | None = None
    regex_literal = False
    regex_char_class = False
    escaped = False
    previous_significant = ""
    index = 0
    while index < len(text):
        char = text[index]
        if regex_literal:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == "[":
                regex_char_class = True
            elif char == "]":
                regex_char_class = False
            elif char == "/" and not regex_char_class:
                regex_literal = False
                previous_significant = "/"
            index += 1
            continue
        if quote is not None:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
                previous_significant = char
            index += 1
            continue
        if char in "'\"`":
            quote = char
            index += 1
            continue
        if char == "/" and index + 1 < len(text) and text[index + 1] == "*":
            end = text.find("*/", index + 2)
            end = len(text) - 2 if end < 0 else end
            for position in range(index, min(len(text), end + 2)):
                if chars[position] != "\n":
                    chars[position] = " "
            index = end + 2
            continue
        if char == "/" and index + 1 < len(text) and text[index + 1] == "/":
            end = text.find("\n", index + 2)
            end = len(text) if end < 0 else end
            for position in range(index, end):
                chars[position] = " "
            index = end
            continue
        if char == "/" and _review_regex_eligible(text, index, previous_significant):
            regex_literal = True
            regex_char_class = False
            escaped = False
            index += 1
            continue
        if not char.isspace():
            previous_significant = char
        index += 1
    return "".join(chars)


def _review_static_string_aliases(decoded: str) -> dict[str, str]:
    aliases: dict[str, str] = {}
    code = _review_mask_comments(decoded)
    pattern = re.compile(
        r"\b(?:const|let|var)\s+([A-Za-z_$][A-Za-z0-9_$]*)\s*=\s*(['\"])([A-Za-z_$][A-Za-z0-9_$]*)\2\s*(?:[,;\n]|$)"
    )
    for match in pattern.finditer(code):
        aliases[match.group(1)] = match.group(3)
    return aliases


def _review_normalize_static_members(decoded: str) -> str:
    aliases = _review_static_string_aliases(decoded)
    value = _review_mask_comments(decoded)
    value = re.sub(
        r"(\?\.\s*)?\[\s*(['\"])([A-Za-z_$][A-Za-z0-9_$]*)\2\s*\]",
        lambda match: ("?." if match.group(1) else ".") + match.group(3),
        value,
    )
    for alias, member in aliases.items():
        value = re.sub(
            rf"(\?\.\s*)?\[\s*{re.escape(alias)}\s*\]",
            lambda match, member=member: ("?." if match.group(1) else ".") + member,
            value,
        )
    return value


def _review_mask_literals(text: str) -> str:
    chars = list(text)
    quote: str | None = None
    escaped = False
    start = -1
    index = 0
    while index < len(text):
        char = text[index]
        if quote is None:
            if char in "'\"`":
                quote = char
                start = index
            index += 1
            continue
        if escaped:
            escaped = False
        elif char == "\\":
            escaped = True
        elif char == quote:
            for position in range(start, index + 1):
                if chars[position] != "\n":
                    chars[position] = " "
            quote = None
            start = -1
        index += 1
    return "".join(chars)


def _review_code_view(decoded: str) -> str:
    return _review_mask_literals(_review_normalize_static_members(decoded))


def _live_secret_reference(text: str) -> bool:
    secret = "|".join(sorted(SECRET_TERMS, key=len, reverse=True))
    receiver = r"(?:payload|body|request|req|input|credentials?|provider)"
    normalized = _review_code_view(text)
    dot = rf"\b{receiver}\s*(?:\?\.|\.)\s*(?:{secret})\b"
    return bool(re.search(dot, normalized, flags=re.IGNORECASE))


def _review_secret_aliases(decoded: str) -> set[str]:
    aliases: set[str] = set()
    code = _review_code_view(decoded)
    assignment = re.compile(
        r"(?<![A-Za-z0-9_$])([A-Za-z_$][A-Za-z0-9_$]*)\s*(?:\?\?=|\|\|=|&&=|[+\-*/%&|^]=|=(?!=|>))\s*([^;\n]+)",
        flags=re.IGNORECASE,
    )
    changed = True
    while changed:
        changed = False
        for match in assignment.finditer(code):
            target, expression = match.group(1), match.group(2)
            alias_hit = any(re.search(rf"\b{re.escape(alias)}\b", expression) for alias in aliases)
            if target not in aliases and (_live_secret_reference(expression) or alias_hit):
                aliases.add(target)
                changed = True
    return aliases


def _review_contains_secret(text: str, aliases: set[str]) -> bool:
    if _live_secret_reference(text):
        return True
    code = _review_code_view(text)
    return any(re.search(rf"\b{re.escape(alias)}\b", code) for alias in aliases)


def _review_secret_sink_flow(decoded: str) -> bool:
    code = _review_code_view(decoded)
    aliases = _review_secret_aliases(decoded)
    sink = "|".join(sorted(SECRET_SINK_TERMS, key=len, reverse=True))
    helper = r"(?:(?:\.|\?\.)\s*(?:call|apply)\s*(?:\?\.\s*)?)?"
    invocation = r"(?:\?\.\s*)?\("
    direct = re.compile(
        rf"(?:\b[A-Za-z_$][A-Za-z0-9_$]*\s*(?:\?\.|\.)\s*)?\b(?:{sink})\b\s*{helper}\s*{invocation}(.*?)\)",
        flags=re.IGNORECASE | re.DOTALL,
    )
    return any(_review_contains_secret(match.group(1), aliases) for match in direct.finditer(code))


def _review_sql_authority_call(decoded: str) -> bool:
    execution = (
        r"(?:\b[A-Za-z_$][A-Za-z0-9_$]*\s*(?:\.\s*(?:query|execute|exec|run|sql)|"
        r"\[\s*['\"](?:query|execute|exec|run|sql)['\"]\s*\])|"
        r"\(\s*[A-Za-z_$][A-Za-z0-9_$]*\s*\.\s*(?:query|execute|exec|run|sql)\s*\))\s*\("
    )
    privilege = r"\b(?:grant\b[^;()]{0,300}\b(?:on|to)\b|revoke\b[^;()]{0,300}\b(?:on|from)\b|reassign\s+owned\b)"
    return bool(re.search(rf"{execution}[^;]{{0,600}}{privilege}", decoded, flags=re.IGNORECASE | re.DOTALL))


def _structural_semantic_errors(path: str, decoded: str) -> list[str]:
    errors: list[str] = []
    suffix = Path(path).suffix.casefold()
    folded = unicodedata.normalize("NFKC", decoded).casefold()
    uncommented = _strip_comments(folded)
    if suffix == ".sql":
        errors.append(f"G2-owned SQL artifact forbidden; accepted Monitoring persistence must be reused: {path}")
    ddl_pattern = rf"\b(?:create(?:\s+or\s+replace)?|alter|drop)\s+(?:{DDL_OBJECTS})\b"
    if re.search(ddl_pattern, uncommented, flags=re.IGNORECASE):
        errors.append(f"G2-owned DDL forbidden; accepted Monitoring persistence must be reused: {path}")

    identifiers = _raw_identifiers(decoded)
    components: set[str] = set()
    for identifier in identifiers:
        components.update(_split_components(identifier))

    if "provider" in components and (components & PROVIDER_AUTHORITY_TERMS):
        errors.append(f"provider-native authorization/authority semantics forbidden in G2: {path}")

    if _has_persistence_write(decoded):
        errors.append(f"direct persistence write surface forbidden in G2 composition: {path}")

    if components & SECRET_TERMS and _has_secret_to_sink(decoded):
        errors.append(f"raw secret persistence/exposure data-flow forbidden in G2: {path}")
    if _review_secret_sink_flow(decoded):
        errors.append(f"raw secret sink-equivalence data-flow forbidden in G2: {path}")
    if _review_sql_authority_call(decoded):
        errors.append(f"SQL authority-changing execution surface forbidden in G2: {path}")
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

    marker_text = _mask_authorized_browser_automation(decoded)
    identifiers = _raw_identifiers(marker_text)
    folded = unicodedata.normalize("NFKC", marker_text).casefold()
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