#!/usr/bin/env python3
"""Falsify exact provenance binding for the terminal D3-D evidence set."""

from __future__ import annotations

import copy
import json
import tempfile
from pathlib import Path

import validate_d3_identity_security_state as validator

ROOT = Path(__file__).resolve().parents[2]


def _baseline() -> dict:
    return json.loads((ROOT / validator.MANIFEST).read_text(encoding="utf-8"))


def _proof(state: dict, evidence_id: str) -> dict:
    tracks = {track["track_id"]: track for track in state["tracks"]}
    matches = [
        proof
        for proof in tracks["D3-D"]["evidence_proofs"]
        if proof["evidence_id"] == evidence_id
    ]
    if len(matches) != 1:
        raise AssertionError(f"expected one D3-D proof for {evidence_id!r}, got {len(matches)}")
    return matches[0]


def _expect_rejected(label: str, state: dict, expected_fragment: str) -> None:
    with tempfile.TemporaryDirectory(prefix="jlmirror-d3d-proof-") as tmp:
        root = Path(tmp)
        manifest_path = root / validator.MANIFEST
        gate_doc_path = root / validator.GATE_DOC
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        gate_doc_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
        gate_doc_path.write_text(
            (ROOT / validator.GATE_DOC).read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        try:
            validator.validate(root)
        except AssertionError as exc:
            if expected_fragment not in str(exc):
                raise AssertionError(
                    f"{label}: wrong rejection; expected fragment={expected_fragment!r} actual={str(exc)!r}"
                ) from exc
            return
        raise AssertionError(f"{label}: provenance drift was unexpectedly accepted")


def main() -> int:
    validator.validate(ROOT)
    baseline = _baseline()

    d3d = {track["track_id"]: track for track in baseline["tracks"]}["D3-D"]
    expected_completed = validator.REQUIRED_EVIDENCE["D3-D"]
    if d3d["state"] != "per_track_conformed":
        raise AssertionError(f"D3-D is not terminal: {d3d['state']!r}")
    if set(d3d["evidence_completed"]) != expected_completed or d3d["evidence_remaining"]:
        raise AssertionError("D3-D terminal state is not backed by exactly all required evidence")
    if len(d3d["evidence_proofs"]) != len(expected_completed):
        raise AssertionError("D3-D terminal evidence/proof cardinality drifted")

    private_key_sha = copy.deepcopy(baseline)
    _proof(private_key_sha, "private_key_non_exportability_profile")["evidence_sha"] = "0" * 40
    _expect_rejected(
        "private_key_sha_drift",
        private_key_sha,
        "evidence proof drifted from the assurance-approved provenance",
    )

    restore_probe = copy.deepcopy(baseline)
    _proof(restore_probe, "issuer_restore_retired_authority_nonresurrection")["probe"] = (
        "implementation/d3-identity-security/harness/spire_candidate_probe.sh"
    )
    _expect_rejected(
        "restore_probe_drift",
        restore_probe,
        "evidence proof drifted from the assurance-approved provenance",
    )

    vendor_run = copy.deepcopy(baseline)
    _proof(vendor_run, "vendor_credential_adapter_least_privilege")["workflow_run_id"] += 1
    _expect_rejected(
        "vendor_run_drift",
        vendor_run,
        "evidence proof drifted from the assurance-approved provenance",
    )

    vendor_pin = copy.deepcopy(baseline)
    _proof(vendor_pin, "vendor_credential_adapter_least_privilege")["artifact_pins"] = [
        "spire-1.15.3-linux-amd64-musl.tar.gz@sha256:" + "0" * 64
    ]
    _expect_rejected(
        "vendor_candidate_pin_drift",
        vendor_pin,
        "proof does not bind the exact SPIRE candidate artifact",
    )

    print(
        "d3d_completion_provenance_falsification=PASS "
        "private_key_sha=locked restore_probe=locked vendor_run=locked candidate_pin=locked"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
