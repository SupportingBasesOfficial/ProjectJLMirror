from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[2]


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def main() -> None:
    worker = (ROOT / "src/jlmirror_monitoring/validation_worker.py").read_text(encoding="utf-8")
    sql = (ROOT / "sql/wave4/003_zabbix_initial_validation_worker.sql").read_text(encoding="utf-8")
    conformance = (ROOT / "tools/wave4/run_zabbix_initial_validation_postgres_conformance.sh").read_text(encoding="utf-8")
    manifest = json.loads((ROOT / "implementation/wave-4/IMPLEMENTATION_MANIFEST.json").read_text(encoding="utf-8"))
    state = (ROOT / "implementation/wave-4/STATE.md").read_text(encoding="utf-8")
    provider = (ROOT / "docs/09-api-contracts/zabbix-monitoring-source-provider-contract.md").read_text(encoding="utf-8")
    monitoring_api = (ROOT / "docs/09-api-contracts/monitoring-domain-api-contract.md").read_text(encoding="utf-8")
    accepted_contracts = provider + "\n" + monitoring_api

    require(manifest["implementation_id"] == "wave4.zabbix-initial-validation-worker@1", "implementation id drift")
    require(manifest["canonical_predecessor_commit"] == "d642a7f456e042dd02de2c04533c39c748f88aa9", "predecessor drift")
    require(manifest["product_feature_activation"] == "monitoring_source_validation_hostgroup_only", "slice boundary drift")
    for forbidden in ("resource_ingestion", "metric_ingestion", "problem_ingestion", "host_inventory_ingestion", "concrete_secret_manager", "concrete_egress_transport"):
        require(forbidden in manifest["explicitly_not_implemented"], f"missing deferred boundary: {forbidden}")

    for phrase in (
        "hostgroup.get",
        "configured host-group scope anchors",
        "API tokens",
        "SHALL NOT be used",
        "Before each provider use",
    ):
        require(phrase in accepted_contracts, f"accepted provider/Monitoring contract phrase missing: {phrase}")

    for phrase in (
        "CredentialResolver",
        "OutboundAdmission",
        "ZabbixHostGroupReader",
        "SCOPE_ANCHOR_INACCESSIBLE",
        "OperationalEvidenceState.INCOMPLETE",
        "SyncOperationState.RECONCILIATION_REQUIRED",
    ):
        require(phrase in worker, f"worker boundary missing: {phrase}")

    require("claim_zabbix_initial_validation" in sql, "claim function missing")
    require("complete_zabbix_initial_validation" in sql, "completion function missing")
    require("execution.stale_authority" in sql, "stale authority retirement class missing")
    require("state = 'reconciliation_required'" in sql, "stale claim retirement state missing")
    require("Monitoring source validation evidence is immutable" in sql, "evidence immutability missing")
    require("credential_generation_ref" in sql and "egress_decision_ref" in sql, "safe dependency evidence missing")
    require("api_token" not in sql.lower(), "secret material must not enter persistence schema")
    require("stale=retired_without_source_mutation" in conformance, "stale-retirement conformance marker missing")
    require("execution.stale_authority" in conformance, "stale-retirement error class not exercised")

    for phrase in (
        "missing configured HostGroup",
        "does not mean all monitored resources disappeared",
        "No automatic retry cadence",
        "provider installation self-identity",
    ):
        require(phrase in state, f"state product boundary missing: {phrase}")

    print("wave4_zabbix_initial_validation_worker=PASS hostgroup_only=true credential=port egress=port stale_commit=fenced+retired retry=not_selected ingestion=none")


if __name__ == "__main__":
    main()
