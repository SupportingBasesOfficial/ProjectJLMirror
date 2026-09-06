#!/usr/bin/env python3
from __future__ import annotations

from evaluate_candidates import (
    CANDIDATES,
    PROOFS,
    HistoricalReader,
    HistoricalRecord,
    blocked,
    evaluate,
    sample_v1,
    sample_v2,
)


def main() -> int:
    result = evaluate()
    assert result["selection"] == "not_selected"
    assert result["selection_authority"] == "not_granted"
    assert result["ledger_credit"] == []
    assert result["current_run_auto_credit"] is False
    assert set(result["candidate_results"]) == set(CANDIDATES)
    assert all(v == "eligible_for_evidence_execution" for v in result["candidate_results"].values())
    assert all(set(result["proof_results"][c]) == set(PROOFS) for c in CANDIDATES)
    assert all(all(v.values()) for v in result["proof_results"].values())

    for candidate in CANDIDATES:
        reader = HistoricalReader(candidate)
        v1, v2 = sample_v1(), sample_v2()
        r1, r2 = reader.read(v1), reader.read(v2)
        assert v1.payload == {"order": "42", "status_code": "P"}
        assert r1.semantic_fields == {"order_id": "42", "state": "paid"}
        assert r2.semantic_fields == {"order_id": "43", "state": "created"}
        assert (r1.tenant_id, r1.contract_id, r1.message_id, r1.occurrence_id) == (
            v1.tenant_id, v1.contract_id, v1.message_id, v1.occurrence_id
        )
        equivalent_v2 = HistoricalRecord(
            v1.tenant_id, v1.contract_id, "other-message", "other-occurrence", 2,
            "reader-v2", "eq-v2-compat", {"order_id": "42", "state": "paid"},
        )
        mapped = reader.read(equivalent_v2)
        assert mapped.semantic_fields == r1.semantic_fields
        assert mapped.equivalence_fingerprint == r1.equivalence_fingerprint
        assert mapped.comparison_profile == r1.comparison_profile == "eq-v2-compat"
        assert blocked(
            lambda: reader.read(v1, fabricate_fields={"newer_fact": "invented"}),
            "upcaster_new_fact_fabrication_forbidden",
        )
        assert blocked(
            lambda: reader.read(v1, dynamic_code=True),
            "dynamic_untrusted_execution_forbidden",
        )
        assert blocked(
            lambda: reader.read(v1, requested_reader_version="reader-v2"),
            "historical_reader_version_mismatch",
        )
        assert blocked(
            lambda: reader.read(HistoricalRecord(
                v1.tenant_id, v1.contract_id, v1.message_id, v1.occurrence_id,
                1, "reader-v2", "eq-v1", dict(v1.payload),
            )),
            "historical_reader_version_unrecoverable",
        )
        assert blocked(
            lambda: reader.read(HistoricalRecord(
                v1.tenant_id, v1.contract_id, v1.message_id, v1.occurrence_id,
                1, "reader-v1", "eq-unknown", dict(v1.payload),
            )),
            "historical_equivalence_profile_unavailable",
        )
        assert blocked(
            lambda: reader.read(HistoricalRecord(
                v1.tenant_id, v1.contract_id, v1.message_id, v1.occurrence_id,
                0, "reader-v0", "eq-v1", dict(v1.payload),
            )),
            "unsupported_historical_schema_version",
        )
        assert blocked(
            lambda: reader.read(HistoricalRecord(
                v1.tenant_id, v1.contract_id, v1.message_id, v1.occurrence_id,
                1, "reader-v1", "eq-v1", {"order": "42", "status_code": "UNKNOWN"},
            )),
            "historical_semantic_value_untrusted",
        )

    print(
        "d4c_open_evt_015_falsification=PASS candidates=3 proofs=7 "
        "real_representation_upcast=true historical_semantics_immutable=true "
        "reader_versions_recoverable=true equivalence_mapping_deterministic=true dynamic_code=false"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
