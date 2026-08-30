#!/usr/bin/env python3
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import os
from pathlib import Path
import re
import subprocess

from jlmirror_authority.model import AdmissionDenied, EnvironmentClass, PrincipalKind
from jlmirror_authority.runtime_profiles import API_AUTH_BOUNDARY
from jlmirror_authority.workload import VerifiedWorkloadPeer, admit_workload_peer

TRUST_DOMAIN = "rotation.validation.d3.jlmirror.invalid"
CANONICAL_SPIFFE_ID = (
    "spiffe://rotation.validation.d3.jlmirror.invalid/"
    "environment.validation@1/runtime.api@1/rotation-evidence"
)
WIRE_SPIFFE_ID = "spiffe://rotation.validation.d3.jlmirror.invalid/runtime/rotation-evidence/v1/workload"
_URI_RE = re.compile(r"URI:([^,\s]+)")


def _run(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        check=check,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def _openssl_date(cert: Path, option: str) -> datetime:
    output = _run("openssl", "x509", "-in", str(cert), "-noout", option).stdout.strip()
    _, value = output.split("=", 1)
    parsed = datetime.strptime(value, "%b %d %H:%M:%S %Y %Z")
    return parsed.replace(tzinfo=timezone.utc)


def _digest_id(prefix: str, path: Path) -> str:
    return f"{prefix}:{hashlib.sha256(path.read_bytes()).hexdigest()}"


def _fingerprint(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _require_file(path: Path) -> Path:
    if not path.is_file() or path.stat().st_size == 0:
        raise SystemExit(f"required SPIRE rotation evidence is missing or empty: {path}")
    return path


def _wire_identity(cert: Path) -> str:
    output = _run(
        "openssl",
        "x509",
        "-in",
        str(cert),
        "-noout",
        "-ext",
        "subjectAltName",
    ).stdout
    identities = _URI_RE.findall(output)
    if identities != [WIRE_SPIFFE_ID]:
        raise AssertionError(f"unexpected SPIRE rotation SVID URI set: {identities!r}")
    return identities[0]


def _expect_denied(label: str, fragment: str, call) -> None:
    try:
        call()
    except AdmissionDenied as exc:
        if fragment not in str(exc):
            raise AssertionError(
                f"{label}: wrong denial reason; expected fragment={fragment!r} actual={str(exc)!r}"
            ) from exc
        return
    raise AssertionError(f"{label}: restored/stale authority was unexpectedly admitted")


def _peer(
    *,
    cert: Path,
    bundle_generation: str,
    credential_generation: str,
) -> VerifiedWorkloadPeer:
    return VerifiedWorkloadPeer(
        spiffe_id=CANONICAL_SPIFFE_ID,
        certificate_not_before=_openssl_date(cert, "-startdate"),
        certificate_not_after=_openssl_date(cert, "-enddate"),
        trust_bundle_generation=bundle_generation,
        workload_credential_generation=credential_generation,
    )


def _admit(
    peer: VerifiedWorkloadPeer,
    *,
    current_bundle: str,
    current_credential: str,
    now: datetime,
):
    return admit_workload_peer(
        peer=peer,
        expected_trust_domain=TRUST_DOMAIN,
        expected_environment=EnvironmentClass.VALIDATION,
        allowed_runtime_profiles=frozenset({API_AUTH_BOUNDARY.runtime_profile_id}),
        current_trust_bundle_generation=current_bundle,
        current_workload_credential_generation=current_credential,
        current_max_certificate_lifetime=timedelta(seconds=45),
        now=now,
    )


def main() -> int:
    root_raw = os.environ.get("SPIRE_ROTATION_EVIDENCE_DIR")
    if not root_raw:
        raise SystemExit("SPIRE_ROTATION_EVIDENCE_DIR is required")
    root = Path(root_raw).resolve()
    if not root.is_dir():
        raise SystemExit(f"SPIRE rotation evidence directory does not exist: {root}")

    run_dir = root / "run"
    restored_bundle = _require_file(run_dir / "bootstrap-bundle.pem")
    current_bundle = _require_file(run_dir / "final-bundle.pem")
    restored_svid = _require_file(run_dir / "pre-ca-svid.pem")
    current_svid = _require_file(run_dir / "post-ca-svid.pem")

    _wire_identity(restored_svid)
    _wire_identity(current_svid)

    restored_bundle_generation = _digest_id("bundle", restored_bundle)
    current_bundle_generation = _digest_id("bundle", current_bundle)
    restored_credential_generation = _digest_id("svid", restored_svid)
    current_credential_generation = _digest_id("svid", current_svid)

    if restored_bundle_generation == current_bundle_generation:
        raise AssertionError("SPIRE rotation evidence did not advance trust-bundle generation")
    if restored_credential_generation == current_credential_generation:
        raise AssertionError("SPIRE rotation evidence did not advance workload credential generation")

    # The restored snapshot must be genuinely usable under its own retired trust state.
    # Otherwise non-resurrection would be vacuous rather than a current-authority property.
    restored_verify = _run(
        "openssl",
        "verify",
        "-no_check_time",
        "-CAfile",
        str(restored_bundle),
        str(restored_svid),
        check=False,
    )
    if restored_verify.returncode != 0:
        raise AssertionError(
            "retired SPIRE snapshot cannot validate its own historical SVID; restore control is invalid: "
            + restored_verify.stderr.strip()
        )

    current_verify = _run(
        "openssl",
        "verify",
        "-no_check_time",
        "-CAfile",
        str(current_bundle),
        str(current_svid),
        check=False,
    )
    if current_verify.returncode != 0:
        raise AssertionError(
            "current SPIRE bundle does not validate the post-rotation SVID: "
            + current_verify.stderr.strip()
        )

    retired_against_current = _run(
        "openssl",
        "verify",
        "-no_check_time",
        "-CAfile",
        str(current_bundle),
        str(restored_svid),
        check=False,
    )
    if retired_against_current.returncode == 0:
        raise AssertionError("retired pre-rotation SVID still validates under the final current bundle")

    # Choose a deterministic instant inside the post-rotation SVID validity interval so this
    # probe tests authority generation rather than runner timing.
    current_not_before = _openssl_date(current_svid, "-startdate")
    current_not_after = _openssl_date(current_svid, "-enddate")
    evaluation_now = current_not_before + timedelta(seconds=1)
    if evaluation_now >= current_not_after:
        raise AssertionError("post-rotation SPIRE SVID validity window is too small for evaluation")

    current_peer = _peer(
        cert=current_svid,
        bundle_generation=current_bundle_generation,
        credential_generation=current_credential_generation,
    )
    principal = _admit(
        current_peer,
        current_bundle=current_bundle_generation,
        current_credential=current_credential_generation,
        now=evaluation_now,
    )
    if principal.kind is not PrincipalKind.INTERNAL_SERVICE_PRINCIPAL:
        raise AssertionError("current SPIRE positive control changed principal class")
    if principal.principal_id != CANONICAL_SPIFFE_ID:
        raise AssertionError("current SPIRE positive control changed canonical principal identity")

    restored_peer = _peer(
        cert=restored_svid,
        bundle_generation=restored_bundle_generation,
        credential_generation=restored_credential_generation,
    )
    _expect_denied(
        "restored_snapshot",
        "trust-bundle generation is stale",
        lambda: _admit(
            restored_peer,
            current_bundle=current_bundle_generation,
            current_credential=current_credential_generation,
            now=evaluation_now,
        ),
    )

    # Independent fence control: even if a restored bundle were accidentally relabelled as
    # current, its retired workload credential generation still cannot become current.
    stale_credential_peer = _peer(
        cert=restored_svid,
        bundle_generation=current_bundle_generation,
        credential_generation=restored_credential_generation,
    )
    _expect_denied(
        "restored_credential_generation",
        "workload credential generation is stale",
        lambda: _admit(
            stale_credential_peer,
            current_bundle=current_bundle_generation,
            current_credential=current_credential_generation,
            now=evaluation_now,
        ),
    )

    print(
        "issuer_restore_retired_authority_nonresurrection=PASS "
        f"wire_spiffe_id={WIRE_SPIFFE_ID} canonical_principal={CANONICAL_SPIFFE_ID} "
        f"restored_bundle_fingerprint={_fingerprint(restored_bundle)} "
        f"current_bundle_fingerprint={_fingerprint(current_bundle)} "
        "historical_snapshot_self_verifies=true retired_under_current_bundle=true "
        "restored_bundle_generation_denied=true restored_credential_generation_denied=true"
    )
    print(
        "conformance_claim=exploratory_only evidence_credited=false ledger_change=false "
        "restore_object_not_current_authority=true wave4=not_granted production=none "
        "d4=not_selected_not_granted"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
