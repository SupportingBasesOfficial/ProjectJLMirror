from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SQL = ROOT / "sql/integration/001_monitoring_alerting_publication.sql"
DOC = ROOT / "implementation/wave-4-monitoring-alerting-publication-runtime/IMPLEMENTATION.md"
MANIFEST = ROOT / "implementation/wave-4-monitoring-alerting-publication-runtime/IMPLEMENTATION_MANIFEST.json"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def main() -> None:
    sql = SQL.read_text(encoding="utf-8")
    lower = sql.lower()
    doc = DOC.read_text(encoding="utf-8")
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))

    require(manifest["implementation_id"] == "wave4.monitoring-alerting-publication-runtime@1", "wrong implementation id")
    require(manifest["authorization_id"] == "wave4.monitoring-alerting-publication@1", "wrong authorization binding")
    require(manifest["canonical_base"] == "fb7d2e6309df432b133105aa081dc1ef37784820", "wrong canonical base")
    require(manifest["migration"] == "sql/integration/001_monitoring_alerting_publication.sql", "wrong migration path")
    require(manifest["contracts"] == [
        "monitoring.problem-state.changed",
        "monitoring.health-projection.changed",
    ], "contract drift")
    require(manifest["reuses_wave2_outbox"] is True, "Wave 2 outbox reuse must be explicit")
    require(manifest["creates_new_outbox_substrate"] is False, "parallel outbox substrate forbidden")
    require(manifest["same_transaction_publication"] is True, "atomic publication binding required")
    require(manifest["rollback_removes_publication_obligation"] is True, "rollback atomicity law missing")
    require(manifest["stable_message_identity"] is True, "stable message identity required")
    require(manifest["message_id_not_correlation_id"] is True, "message id must not be correlation id")
    require(manifest["causation_bound_to_owning_transition"] is True, "causation must bind owning transition")
    require(manifest["non_equivalent_identity_collision_fails_closed"] is True, "identity conflict must fail closed")
    require(manifest["payload_contains_semantic_problem_or_health_state"] is False, "semantic state replication forbidden")
    require(manifest["alerting_business_mutation_authorized"] is False, "Alerting business mutation must remain blocked")
    require(manifest["broker_selection_authorized"] is False, "broker selection remains blocked")
    require(manifest["production_authority"] == "none", "production authority must remain none")

    for marker in (
        "system.async_outbox_message",
        "system.async_outbox_dispatch",
        "monitoring.monitoring_problem_transition",
        "monitoring.health_projection_transition",
        "monitoring.problem-state.changed",
        "monitoring.health-projection.changed",
        "monitoring_problem_transition_outbox",
        "health_projection_transition_outbox",
        "monitoring.wave4_ensure_monitoring_invalidation",
        "monitoring.recover_problem_state_publication",
        "monitoring.recover_health_projection_publication",
        "monitoring.publication_identity_conflict",
        "monitoring.publication_envelope_identity_collision",
        "v_correlation_id",
        "v_causation_id",
        "confidential_tenant",
        "integration_event",
        "canonical-jsonb-envelope-payload",
    ):
        require(marker in sql, f"missing SQL marker: {marker}")

    require("after insert on monitoring.monitoring_problem_transition" in lower, "Problem publication must be AFTER INSERT")
    require("after insert on monitoring.health_projection_transition" in lower, "Health publication must be AFTER INSERT")
    require("on conflict (producer_message_scope,message_id) do nothing" in lower, "idempotent outbox ensure missing")
    require("on conflict (outbox_record_id) do nothing" in lower, "dispatch recovery missing")
    require("owner to jlmirror_wave4_monitoring_publication_executor" in lower, "publication functions need dedicated NOLOGIN owner")
    require("to jlmirror_wave4_recovery_authority" in lower, "recovery entry points must bind existing recovery authority")
    require("v_existing.correlation_id is distinct from v_correlation_id" in lower, "correlation equivalence check missing")
    require("v_existing.causation_id is distinct from v_causation_id" in lower, "causation equivalence check missing")
    require("v_correlation_id,v_causation_id" in lower, "outbox must persist distinct correlation/causation identities")

    forbidden_payload_tokens = (
        "'problem_state'",
        "'severity_class'",
        "'health_class'",
        "'health_evidence_state'",
        "'provider_acknowledged'",
        "'provider_eventid'",
        "'provider_trigger_ref'",
        "'summary'",
        "'metric_value'",
    )
    payload_sections = sql[sql.index("CREATE OR REPLACE FUNCTION monitoring.wave4_publish_problem_transition"):]
    for token in forbidden_payload_tokens:
        require(token not in payload_sections, f"forbidden semantic/provider payload token leaked: {token}")

    require("create table system.async_outbox_message" not in lower, "must not recreate Wave 2 outbox")
    require("create table system.async_outbox_dispatch" not in lower, "must not recreate Wave 2 dispatch substrate")
    require("create schema" not in lower, "integration migration must not invent a new substrate schema")
    require("insert into alerting." not in lower, "Alerting mutation leaked into publication bridge")
    require("create table alert" not in lower, "Alert table creation not authorized")

    for marker in (
        "TRANSITION ROLLBACK => OUTBOX ROLLBACK",
        "TRANSITION COMMIT   => OUTBOX OBLIGATION COMMIT",
        "It does not create Alert state",
        "does **not** duplicate the outbox schema inside Wave 4",
        "They never synthesize a new transition identity",
        "`message_id` is never overloaded as `correlation_id` or `causation_id`",
    ):
        require(marker in doc, f"implementation documentation marker missing: {marker}")

    print("wave4_monitoring_alerting_publication_runtime=PASS")


if __name__ == "__main__":
    main()
