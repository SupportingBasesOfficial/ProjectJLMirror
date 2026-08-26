#!/usr/bin/env python3
"""Observer-only validation for Wave 2 quarantine/redrive authority hooks."""

from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
PROFILE = "jlmirror-wave2-redrive-authority/v1"


def _missing(text: str, anchors: tuple[str, ...], owner: str) -> list[str]:
    return [f"{owner} missing redrive authority anchor: {anchor}" for anchor in anchors if anchor not in text]


def validate(root: Path = ROOT) -> list[str]:
    quarantine = (root / "src/jlmirror_async/quarantine.py").read_text(encoding="utf-8")
    tests = (root / "tests/wave2/test_quarantine_redrive_authority.py").read_text(encoding="utf-8")
    readme = (root / "implementation/wave-2/README.md").read_text(encoding="utf-8")
    operations = (
        root
        / "docs/15-operations-recovery-incident-readiness/09-async-replay-quarantine-realtime-webhook-operations.md"
    ).read_text(encoding="utf-8")
    delivery = (root / "docs/10-event-contracts/delivery-ack-retry-and-quarantine.md").read_text(
        encoding="utf-8"
    )

    findings: list[str] = []
    findings.extend(
        _missing(
            quarantine,
            (
                "class CurrentRedriveAuthorityPort",
                "class QuarantineSubject",
                "class RedriveAdmission",
                "quarantine_state_revision: str",
                'identifier(getattr(self, field), field)',
                '"quarantine_state_revision"',
                "def require_current_redrive(",
                "redrive admission is bound to another quarantine subject",
                "redrive privileged authority is not current",
                "owning contract does not currently admit redrive",
                "tenant-scoped redrive admission requires current placement evidence",
                "global redrive admission must not manufacture tenant placement",
                "effect_safety_revision",
                "capacity_admission_revision",
                "audit_revision",
                "rel.outbox-publication@1",
                "rel.consumer-inbox-effect@1",
                "rel.replay-consume-state@1",
                "caller-provided request is scope to check, never proof of current quarantine",
            ),
            "redrive implementation",
        )
    )
    findings.extend(
        _missing(
            tests,
            (
                "test_redrive_requires_current_privileged_authority",
                "test_redrive_requires_owning_contract_eligibility",
                "test_redrive_admission_is_exact_quarantine_generation_bound",
                "test_redrive_admission_requires_durable_quarantine_state_revision",
                "test_tenant_redrive_admission_requires_current_placement_evidence",
                "test_global_redrive_must_not_manufacture_tenant_placement",
                'quarantine_state_revision="quarantine-state-12"',
            ),
            "redrive falsification",
        )
    )
    findings.extend(
        _missing(
            readme,
            (
                "REDRIVE REQUEST != QUARANTINE STATE AUTHORITY",
                "QUARANTINE != REDRIVE ELIGIBILITY",
                "QUEUE AGE / OPERATOR DESIRE / VENDOR DLQ STATE != REDRIVE AUTHORITY",
                "quarantine_state_revision",
                "CurrentRedriveAuthorityPort",
                "does not implement the Phase 15 `ops.redrive-operation@1` store/workflow",
            ),
            "redrive propagation",
        )
    )
    findings.extend(
        _missing(
            operations,
            (
                "`ops.redrive-operation@1`",
                "Redrive requires current privileged authority and owning-contract eligibility",
                "Time in quarantine, operator desire, queue age or a vendor DLQ button is not eligibility",
            ),
            "accepted Phase 15 redrive authority",
        )
    )
    findings.extend(
        _missing(
            delivery,
            (
                "Re-drive is an explicit governed action",
                "current authorization for privileged remediation is checked",
                "duplicate/effect state is reconciled",
                "irreversible effects are not blindly repeated",
            ),
            "accepted Phase 10 redrive authority",
        )
    )
    return findings


def main() -> int:
    findings = validate()
    if findings:
        print(f"RESULT: FAIL — {PROFILE}")
        for finding in findings:
            print(f"- {finding}")
        return 1
    print(
        f"RESULT: PASS — {PROFILE} — redrive request scope cannot substitute for durable quarantine/current privileged authority"
    )
    print("NOTE: PASS is conformance evidence only; Phase 15 operations tooling remains separately governed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
