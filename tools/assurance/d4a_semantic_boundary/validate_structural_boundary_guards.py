from __future__ import annotations

import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BOUNDARY_SOURCE = ROOT / "tools/assurance/d4a_semantic_boundary/broker_boundary.py"
INVENTORY = ROOT / "implementation/d4-eventing-async/source-evidence/semantic-boundary/boundary-inventory.json"

KAFKA_IMPORT_PREFIXES = ("kafka", "aiokafka", "confluent_kafka")
KAFKA_NATIVE_NAMES = {"offset", "partition", "consumer_group", "rebalance", "transactional_id"}
KAFKA_TRANSACTION_METHODS = {
    "init_transactions",
    "begin_transaction",
    "commit_transaction",
    "abort_transaction",
    "send_offsets_to_transaction",
}
KAFKA_TRANSACTION_IDENTIFIERS = {
    method: method.replace("_", "") for method in KAFKA_TRANSACTION_METHODS
}
KAFKA_TEXT_MARKERS = (
    "confluent_kafka", "confluent-kafka", "confluent.kafka", "aiokafka", "kafkajs",
    "node-rdkafka", "rdkafka", "librdkafka", "@confluentinc/kafka-javascript",
    "org.apache.kafka", "org.springframework.kafka", "segmentio/kafka-go", "shopify/sarama",
    "ibm/sarama", "twmb/franz-go", "rust-rdkafka",
)


def _normalized_transaction_method(identifier: str) -> str | None:
    normalized = identifier.lower().replace("_", "")
    for canonical, expected in KAFKA_TRANSACTION_IDENTIFIERS.items():
        if normalized == expected:
            return canonical
    return None


def _python_tree_findings(tree: ast.AST, raw: str) -> set[str]:
    findings: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith(KAFKA_IMPORT_PREFIXES):
                    findings.add(f"import:{alias.name}")
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module.startswith(KAFKA_IMPORT_PREFIXES):
                findings.add(f"import:{module}")
        elif isinstance(node, ast.Attribute):
            if node.attr in KAFKA_NATIVE_NAMES:
                findings.add(f"attribute:{node.attr}")
            transaction = _normalized_transaction_method(node.attr)
            if transaction is not None:
                findings.add(f"transaction_api:{transaction}")
    segment = ast.get_source_segment(raw, tree) or raw
    lowered = segment.lower()
    findings.update(f"marker:{marker}" for marker in KAFKA_TEXT_MARKERS if marker in lowered)
    return findings


def boundary_non_allowlisted_findings(raw: str, allowlisted_class: str) -> list[str]:
    """Exempt exactly one top-level lexical declaration and scan every other class subtree."""
    tree = ast.parse(raw)
    all_matching = [node for node in ast.walk(tree) if isinstance(node, ast.ClassDef) and node.name == allowlisted_class]
    top_level_matching = [node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == allowlisted_class]
    if len(all_matching) != 1 or len(top_level_matching) != 1 or all_matching[0] is not top_level_matching[0]:
        raise AssertionError(
            f"native adapter allowlist must bind to exactly one top-level lexical declaration: {allowlisted_class}"
        )
    allowed = top_level_matching[0]
    findings: set[str] = set()

    for node in tree.body:
        if node is not allowed:
            findings.update(_python_tree_findings(node, raw))
            continue
        # The native adapter body is exempt, but nested classes are independent lexical declarations
        # and therefore remain prohibited from acquiring native/transaction authority.
        for nested in ast.walk(allowed):
            if isinstance(nested, ast.ClassDef) and nested is not allowed:
                findings.update(_python_tree_findings(nested, raw))
    return sorted(findings)


def _call_target(statement: ast.stmt) -> str | None:
    if not isinstance(statement, ast.Expr) or not isinstance(statement.value, ast.Call):
        return None
    func = statement.value.func
    if not isinstance(func, ast.Attribute) or not isinstance(func.value, ast.Attribute):
        return None
    owner = func.value
    if isinstance(owner.value, ast.Name) and owner.value.id == "self":
        return f"{owner.attr}.{func.attr}"
    return None


def assert_ack_verification_dominates(raw: str) -> None:
    """Require a linear two-statement ack path: durable verification, then broker acknowledgement."""
    tree = ast.parse(raw)
    classes = [node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "InboxAcknowledgePath"]
    if len(classes) != 1:
        raise AssertionError("expected exactly one top-level InboxAcknowledgePath declaration")
    methods = [
        node for node in classes[0].body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == "acknowledge_after_durable_responsibility"
    ]
    if len(methods) != 1:
        raise AssertionError("expected exactly one acknowledgement entrypoint")
    body = methods[0].body
    if len(body) != 2:
        raise AssertionError("acknowledgement entrypoint must be a linear two-statement verify-then-ack path")
    targets = [_call_target(statement) for statement in body]
    if targets != ["_verifier.assert_durable", "_broker.acknowledge"]:
        raise AssertionError(
            "durable verification must unconditionally dominate broker acknowledgement with no branch/try/loop escape"
        )


def run_negative_controls() -> None:
    duplicate = """
class KafkaCandidateAdapter:
    def run(self, client):
        client.commitTransaction()
class KafkaCandidateAdapter:
    pass
"""
    try:
        boundary_non_allowlisted_findings(duplicate, "KafkaCandidateAdapter")
    except AssertionError:
        pass
    else:
        raise AssertionError("duplicate allowlisted declaration escaped lexical uniqueness guard")

    nested = """
class KafkaCandidateAdapter:
    class AlternateStubTransport:
        def run(self, client):
            client.commitTransaction()
"""
    assert "transaction_api:commit_transaction" in boundary_non_allowlisted_findings(
        nested, "KafkaCandidateAdapter"
    )

    conditional_verify = """
class InboxAcknowledgePath:
    def acknowledge_after_durable_responsibility(self, receipt):
        if receipt.receipt_id != 'escape':
            self._verifier.assert_durable(receipt)
        self._broker.acknowledge(receipt)
"""
    try:
        assert_ack_verification_dominates(conditional_verify)
    except AssertionError:
        pass
    else:
        raise AssertionError("conditional verification escaped dominance guard")

    broker_first = """
class InboxAcknowledgePath:
    def acknowledge_after_durable_responsibility(self, receipt):
        self._broker.acknowledge(receipt)
        self._verifier.assert_durable(receipt)
"""
    try:
        assert_ack_verification_dominates(broker_first)
    except AssertionError:
        pass
    else:
        raise AssertionError("broker-first acknowledgement escaped dominance guard")


def main() -> int:
    inventory = json.loads(INVENTORY.read_text(encoding="utf-8"))
    allowlist = inventory.get("native_transport_allowlist")
    if allowlist != ["KafkaCandidateAdapter"]:
        raise AssertionError("native transport allowlist must remain exactly KafkaCandidateAdapter")

    raw = BOUNDARY_SOURCE.read_text(encoding="utf-8")
    findings = boundary_non_allowlisted_findings(raw, allowlist[0])
    if findings:
        raise AssertionError(f"non-allowlisted boundary declaration gained native Kafka authority: {findings}")
    assert_ack_verification_dominates(raw)
    run_negative_controls()
    print(
        "d4a_structural_boundary_guards=PASS "
        "native_allowlist=single_top_level_lexical_declaration nested_classes=scanned "
        "ack_dominance=linear_unconditional_verify_then_ack negative_controls=duplicate+nested+conditional+broker_first"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
