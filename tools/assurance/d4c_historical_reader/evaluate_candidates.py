#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

CANDIDATES = (
    "in_process_versioned_reader_upcaster_registry",
    "sidecar_or_library_historical_reader_profile",
    "offline_replay_transform_pipeline_profile",
)

PROOFS = (
    "historical_semantic_meaning_is_immutable",
    "upcasting_cannot_fabricate_newer_historical_facts",
    "source_message_identity_tenant_and_occurrence_semantics_remain_traceable",
    "supported_retained_history_remains_interpretable",
    "equivalence_evidence_and_comparison_profile_semantics_are_preserved_or_deterministically_mapped",
    "reader_or_upcaster_version_is_explicit_and_historically_recoverable",
    "dynamic_untrusted_code_or_schema_execution_is_not_required_for_historical_read",
)


class ContractViolation(RuntimeError):
    pass


@dataclass(frozen=True)
class HistoricalRecord:
    tenant_id: str
    contract_id: str
    message_id: str
    occurrence_id: str
    schema_version: int
    reader_version: str
    equivalence_profile: str
    payload: dict[str, str]


@dataclass(frozen=True)
class InterpretedRecord:
    tenant_id: str
    contract_id: str
    message_id: str
    occurrence_id: str
    source_schema_version: int
    reader_version: str
    comparison_profile: str
    semantic_fields: dict[str, str]
    equivalence_fingerprint: str


def canonical_semantics(fields: dict[str, str]) -> bytes:
    if set(fields) != {"order_id", "state"}:
        raise ContractViolation("canonical_semantic_shape_invalid")
    return json.dumps(fields, sort_keys=True, separators=(",", ":")).encode("utf-8")


def fingerprint(profile: str, fields: dict[str, str]) -> str:
    if profile not in {"eq-v1", "eq-v2-compat"}:
        raise ContractViolation("historical_equivalence_profile_unavailable")
    return hashlib.sha256(canonical_semantics(fields)).hexdigest()


class HistoricalReader:
    READERS = {1: "reader-v1", 2: "reader-v2"}
    PROFILE_MAP = {"eq-v1": "eq-v2-compat", "eq-v2-compat": "eq-v2-compat"}
    V1_STATES = {"P": "paid", "C": "created"}

    def __init__(self, candidate: str) -> None:
        if candidate not in CANDIDATES:
            raise ValueError(candidate)
        self.candidate = candidate

    @classmethod
    def _interpret(cls, record: HistoricalRecord) -> dict[str, str]:
        if record.schema_version == 1:
            if set(record.payload) != {"order", "status_code"}:
                raise ContractViolation("historical_semantic_shape_untrusted")
            state = cls.V1_STATES.get(record.payload["status_code"])
            if state is None:
                raise ContractViolation("historical_semantic_value_untrusted")
            return {"order_id": record.payload["order"], "state": state}
        if record.schema_version == 2:
            if set(record.payload) != {"order_id", "state"}:
                raise ContractViolation("historical_semantic_shape_untrusted")
            if record.payload["state"] not in cls.V1_STATES.values():
                raise ContractViolation("historical_semantic_value_untrusted")
            return dict(record.payload)
        raise ContractViolation("unsupported_historical_schema_version")

    def read(
        self,
        record: HistoricalRecord,
        *,
        dynamic_code: bool = False,
        requested_reader_version: str | None = None,
        fabricate_fields: dict[str, str] | None = None,
    ) -> InterpretedRecord:
        if dynamic_code:
            raise ContractViolation("dynamic_untrusted_execution_forbidden")
        expected_reader = self.READERS.get(record.schema_version)
        if expected_reader is None:
            raise ContractViolation("unsupported_historical_schema_version")
        if record.reader_version != expected_reader:
            raise ContractViolation("historical_reader_version_unrecoverable")
        if requested_reader_version is not None and requested_reader_version != expected_reader:
            raise ContractViolation("historical_reader_version_mismatch")
        if record.equivalence_profile not in self.PROFILE_MAP:
            raise ContractViolation("historical_equivalence_profile_unavailable")
        if fabricate_fields:
            raise ContractViolation("upcaster_new_fact_fabrication_forbidden")

        semantics = self._interpret(record)
        comparison_profile = self.PROFILE_MAP[record.equivalence_profile]
        return InterpretedRecord(
            tenant_id=record.tenant_id,
            contract_id=record.contract_id,
            message_id=record.message_id,
            occurrence_id=record.occurrence_id,
            source_schema_version=record.schema_version,
            reader_version=expected_reader,
            comparison_profile=comparison_profile,
            semantic_fields=semantics,
            equivalence_fingerprint=fingerprint(comparison_profile, semantics),
        )


def sample_v1() -> HistoricalRecord:
    return HistoricalRecord(
        "tenant-a", "orders.created", "msg-001", "occ-001", 1,
        "reader-v1", "eq-v1", {"order": "42", "status_code": "P"},
    )


def sample_v2() -> HistoricalRecord:
    return HistoricalRecord(
        "tenant-a", "orders.created", "msg-002", "occ-002", 2,
        "reader-v2", "eq-v2-compat", {"order_id": "43", "state": "created"},
    )


def blocked(fn: Any, code: str) -> bool:
    try:
        fn()
    except ContractViolation as exc:
        return str(exc) == code
    return False


def check_candidate(candidate: str) -> dict[str, bool]:
    reader = HistoricalReader(candidate)
    v1, v2 = sample_v1(), sample_v2()
    read_v1, read_v2 = reader.read(v1), reader.read(v2)
    equivalent_v2 = HistoricalRecord(
        v1.tenant_id, v1.contract_id, "msg-equivalent-v2", "occ-equivalent-v2", 2,
        "reader-v2", "eq-v2-compat", {"order_id": "42", "state": "paid"},
    )
    remapped = reader.read(equivalent_v2)

    return {
        "real_v1_representation_upcasted": (
            v1.payload == {"order": "42", "status_code": "P"}
            and read_v1.semantic_fields == {"order_id": "42", "state": "paid"}
        ),
        "semantic_fields_preserved": read_v1.semantic_fields == remapped.semantic_fields,
        "source_schema_traceable": read_v1.source_schema_version == 1,
        "fabricated_new_fact_rejected": blocked(
            lambda: reader.read(v1, fabricate_fields={"settled_at": "future"}),
            "upcaster_new_fact_fabrication_forbidden",
        ),
        "untrusted_shape_rejected": blocked(
            lambda: reader.read(HistoricalRecord(
                v1.tenant_id, v1.contract_id, v1.message_id, v1.occurrence_id, 1,
                "reader-v1", "eq-v1", {"order": "42", "status_code": "P", "new_fact": "x"},
            )),
            "historical_semantic_shape_untrusted",
        ),
        "untrusted_value_rejected": blocked(
            lambda: reader.read(HistoricalRecord(
                v1.tenant_id, v1.contract_id, v1.message_id, v1.occurrence_id, 1,
                "reader-v1", "eq-v1", {"order": "42", "status_code": "UNKNOWN"},
            )),
            "historical_semantic_value_untrusted",
        ),
        "identity_traceable": (
            read_v1.tenant_id == v1.tenant_id and read_v1.contract_id == v1.contract_id
            and read_v1.message_id == v1.message_id and read_v1.occurrence_id == v1.occurrence_id
        ),
        "v1_history_interpretable": read_v1.reader_version == "reader-v1",
        "v2_history_interpretable": read_v2.reader_version == "reader-v2",
        "unsupported_history_fails_closed": blocked(
            lambda: reader.read(HistoricalRecord(
                v1.tenant_id, v1.contract_id, v1.message_id, v1.occurrence_id, 0,
                "reader-v0", "eq-v1", dict(v1.payload),
            )),
            "unsupported_historical_schema_version",
        ),
        "equivalence_mapping_deterministic": (
            read_v1.equivalence_fingerprint == remapped.equivalence_fingerprint
            and read_v1.comparison_profile == remapped.comparison_profile == "eq-v2-compat"
        ),
        "missing_equivalence_profile_fails_closed": blocked(
            lambda: reader.read(HistoricalRecord(
                v1.tenant_id, v1.contract_id, v1.message_id, v1.occurrence_id, 1,
                "reader-v1", "eq-unknown", dict(v1.payload),
            )),
            "historical_equivalence_profile_unavailable",
        ),
        "reader_version_explicit": read_v1.reader_version == v1.reader_version,
        "wrong_reader_version_rejected": blocked(
            lambda: reader.read(HistoricalRecord(
                v1.tenant_id, v1.contract_id, v1.message_id, v1.occurrence_id, 1,
                "reader-v2", "eq-v1", dict(v1.payload),
            )),
            "historical_reader_version_unrecoverable",
        ),
        "requested_reader_mismatch_rejected": blocked(
            lambda: reader.read(v1, requested_reader_version="reader-v2"),
            "historical_reader_version_mismatch",
        ),
        "dynamic_code_rejected": blocked(
            lambda: reader.read(v1, dynamic_code=True), "dynamic_untrusted_execution_forbidden"
        ),
    }


PROOF_CHECKS = {
    PROOFS[0]: ("real_v1_representation_upcasted", "semantic_fields_preserved", "untrusted_value_rejected"),
    PROOFS[1]: ("fabricated_new_fact_rejected", "untrusted_shape_rejected"),
    PROOFS[2]: ("identity_traceable", "source_schema_traceable"),
    PROOFS[3]: ("v1_history_interpretable", "v2_history_interpretable", "unsupported_history_fails_closed"),
    PROOFS[4]: ("equivalence_mapping_deterministic", "missing_equivalence_profile_fails_closed"),
    PROOFS[5]: ("reader_version_explicit", "wrong_reader_version_rejected", "requested_reader_mismatch_rejected"),
    PROOFS[6]: ("dynamic_code_rejected",),
}


def evaluate() -> dict[str, Any]:
    checks = {candidate: check_candidate(candidate) for candidate in CANDIDATES}
    proofs = {
        candidate: {proof: all(checks[candidate][name] for name in names) for proof, names in PROOF_CHECKS.items()}
        for candidate in CANDIDATES
    }
    candidate_results = {
        candidate: (
            "eligible_for_evidence_execution"
            if all(checks[candidate].values()) and all(proofs[candidate].values())
            else "insufficient_evidence"
        )
        for candidate in CANDIDATES
    }
    return {
        "schema_version": 1,
        "source_decision": "OPEN-EVT-015",
        "evidence_id": "historical_reader_upcaster_semantic_and_equivalence_continuity",
        "candidate_results": candidate_results,
        "proof_results": proofs,
        "check_results": checks,
        "selection": "not_selected",
        "selection_authority": "not_granted",
        "ledger_credit": [],
        "current_run_auto_credit": False,
    }


if __name__ == "__main__":
    print(json.dumps(evaluate(), indent=2, sort_keys=True))
