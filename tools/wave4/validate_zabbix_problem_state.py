from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOMAIN = ROOT / "src/jlmirror_monitoring/problem_state.py"
READS = ROOT / "src/jlmirror_monitoring/problem_reads.py"
SQL_PATHS = [
    ROOT / "sql/wave4/042_zabbix_problem_state.sql",
    ROOT / "sql/wave4/043_zabbix_problem_state_lifecycle.sql",
    ROOT / "sql/wave4/044_zabbix_problem_state_snapshot_authority.sql",
    ROOT / "sql/wave4/045_zabbix_problem_state_recovery_authority.sql",
]
AUTH = ROOT / "implementation/wave-4-problem-state-authorization/AUTHORIZATION.md"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def main() -> None:
    domain = DOMAIN.read_text(encoding="utf-8")
    reads = READS.read_text(encoding="utf-8")
    sql = "\n".join(path.read_text(encoding="utf-8") for path in SQL_PATHS)
    lower = sql.lower()
    auth = AUTH.read_text(encoding="utf-8")

    require("wave4.monitoring-problem-state@1" in sql, "wrong problem-state authority")
    require("problem.get" in domain or "read_active_problems" in domain, "problem.get boundary missing")
    require("read_recovery_events" in domain, "event.get recovery boundary missing")
    require("MAX_PROBLEMS_PER_POLL" in domain, "problem polling must be bounded")
    require("MAX_TRIGGER_METADATA_PER_REQUEST" in domain, "trigger metadata must be bounded")
    require("monitoring_problem_provider_binding" in lower, "canonical/provider identity binding missing")
    require("monitoring_problem_state_runtime_admission" in lower, "independent runtime admission missing")
    require("problem_poll_epoch" in lower and "problem_poll_generation" in lower, "independent poll authority missing")
    require("force row level security" in lower, "Problem State persistence must force RLS")
    require("provider_acknowledged boolean" in lower, "provider acknowledgement metadata missing")
    require("provider acknowledgement is metadata only" in lower, "provider acknowledgement non-authority marker missing")
    require("resolved problem cannot be reopened" in lower, "resolved identity reopen guard missing")
    require("ABSENCE FROM INCOMPLETE problem.get != RESOLVED" in auth, "fail-closed negative resolution law missing")

    for marker in (
        "enqueue_zabbix_problem_state_sync",
        "claim_zabbix_problem_state",
        "complete_zabbix_problem_state_with_evidence",
        "monitoring_problem_snapshot_evidence",
        "authoritative negative resolution may consume only snapshot_complete=true evidence",
        "revoke execute on function monitoring.complete_zabbix_problem_state",
        "wave4_terminalize_superseded_problem_state_claims",
        "monitoring.problem_state_recovery_epoch_must_advance",
        "revoke update on monitoring.monitoring_source from jlmirror_wave4_problem_state_executor",
    ):
        require(marker in lower, f"Problem State hardening marker missing: {marker}")

    for marker in (
        "MAX_PROBLEM_PAGE_SIZE = 200",
        "MAX_PROBLEM_RESPONSE_BYTES = 1_048_576",
        "generation_state: ProblemGenerationState = ProblemGenerationState.ACTIVE",
        "authorize_problem_read(filters.tenant_id)",
        "resolve_problem_anchor(filters, cursor)",
        "validation.cursor_invalid",
        "cache_control: str = \"no-store\"",
        "opened_at DESC, problem_id ASC",
    ):
        require(marker in reads, f"Problem read contract marker missing: {marker}")

    for forbidden in (
        "insert into monitoring.health",
        "update monitoring.health",
        "insert into alerting.",
        "update alerting.",
        "insert into itsm.",
        "update itsm.",
    ):
        require(forbidden not in lower, f"forbidden downstream authority leaked: {forbidden}")

    print("wave4_zabbix_problem_state=PASS")


if __name__ == "__main__":
    main()
