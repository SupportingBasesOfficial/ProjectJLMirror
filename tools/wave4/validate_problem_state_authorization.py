from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AUTH = ROOT / "implementation/wave-4-problem-state-authorization/AUTHORIZATION.md"
MANIFEST = ROOT / "implementation/wave-4-problem-state-authorization/AUTHORIZATION_MANIFEST.json"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def main() -> None:
    auth = AUTH.read_text(encoding="utf-8")
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))

    require(manifest["authorization_id"] == "wave4.monitoring-problem-state@1", "wrong authorization id")
    require(manifest["canonical_base"] == "4908e5124f2d182146d0366030c1dd64c778a423", "wrong canonical base")
    require(manifest["status"] == "proposed_bounded_implementation_authorization", "authorization must remain proposed")
    require(manifest["requires_independent_poll_authority"] is True, "problem polling must own independent authority")
    require(manifest["negative_resolution_requires_authoritative_evidence"] is True, "negative resolution must fail closed")
    require(manifest["provider_acknowledgement_is_metadata_only"] is True, "provider acknowledgement cannot become platform authority")

    for marker in (
        "problem.get",
        "event.get",
        "trigger.get",
        "active | resolved",
        "PROVIDER ACKNOWLEDGED != JLMIRROR ACKNOWLEDGEMENT",
        "ABSENCE FROM INCOMPLETE problem.get != RESOLVED",
        "independent recovery-safe poll epoch/generation/admission stream",
        "Problems responses are `no_store`",
        "No Health projection is authorized",
    ):
        require(marker in auth, f"authorization marker missing: {marker}")

    require(set(manifest["canonical_problem_state"]) == {"active", "resolved"}, "unexpected problem states")
    require(
        set(manifest["canonical_severity_class"])
        == {"unknown", "informational", "warning", "degraded", "critical"},
        "unexpected severity classes",
    )

    for forbidden in (
        "health_projection_authorized",
        "alerting_authorized",
        "itsm_authorized",
        "provider_writeback_authorized",
        "frontend_authorized",
    ):
        require(manifest[forbidden] is False, f"forbidden authority enabled: {forbidden}")
    require(manifest["production_authority"] == "none", "production authority must remain none")

    runtime_paths = [
        ROOT / "src/jlmirror_monitoring/problem_state.py",
        ROOT / "sql/wave4/042_zabbix_problem_state.sql",
    ]
    require(not any(path.exists() for path in runtime_paths), "problem-state runtime leaked into authorization gate")

    print("wave4_problem_state_authorization=PASS")


if __name__ == "__main__":
    main()
