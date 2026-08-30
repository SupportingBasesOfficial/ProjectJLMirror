#!/usr/bin/env python3
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import os
from pathlib import Path
import re
import subprocess

from jlmirror_authority.model import AdmissionDenied, EnvironmentClass, Principal, PrincipalKind
from jlmirror_authority.runtime_profiles import API_AUTH_BOUNDARY
from jlmirror_authority.workload import VerifiedWorkloadPeer, admit_workload_peer, parse_workload_identity

WIRE_SPIFFE_ID = (
    "spiffe://validation.d3.jlmirror.invalid/"
    "environment/validation/v1/runtime/api/v1/workload-probe"
)
CANONICAL_SPIFFE_ID = (
    "spiffe://validation.d3.jlmirror.invalid/"
    "environment.validation@1/runtime.api@1/workload-probe"
)
TRUST_DOMAIN = "validation.d3.jlmirror.invalid"
ALLOWED_SCOPE = "stateport.monitoring.read@1"
FORBIDDEN_ADMIN_SCOPE = "stateport.monitoring.admin@1"
FORBIDDEN_OWNER_SCOPE = "stateport.database.owner@1"
VENDOR_PRINCIPAL_ID = "vendor.monitoring.readonly@1"
VENDOR_CREDENTIAL_GENERATION = "vendor-credential-generation-7"
MAX_VENDOR_TTL = timedelta(seconds=30)
_URI_RE = re.compile(r"URI:([^,\s]+)")


def _run(*args: str) -> str:
    proc = subprocess.run(
        args,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return proc.stdout.strip()


def _openssl_date(cert: Path, option: str) -> datetime:
    output = _run("openssl", "x509", "-in", str(cert), "-noout", option)
    _, value = output.split("=", 1)
    parsed = datetime.strptime(value, "%b %d %H:%M:%S %Y %Z")
    return parsed.replace(tzinfo=timezone.utc)


def _single_file(directory: Path, pattern: str, *, reject_suffix: str | None = None) -> Path:
    candidates = sorted(directory.glob(pattern))
    if reject_suffix is not None:
        candidates = [item for item in candidates if not item.name.endswith(reject_suffix)]
    if len(candidates) != 1:
        raise SystemExit(
            f"expected exactly one {pattern!r} evidence file in {directory}, got {len(candidates)}"
        )
    return candidates[0]


def _digest_id(prefix: str, path: Path) -> str:
    return f"{prefix}:{hashlib.sha256(path.read_bytes()).hexdigest()}"


def _expect_denied(label: str, fragment: str, call) -> None:
    try:
        call()
    except AdmissionDenied as exc:
        if fragment not in str(exc):
            raise AssertionError(
                f"{label}: wrong denial reason; expected fragment={fragment!r} actual={str(exc)!r}"
            ) from exc
        return
    raise AssertionError(f"{label}: vendor credential exchange unexpectedly succeeded")


@dataclass(frozen=True)
class VendorCredentialGrant:
    source_workload_principal_id: str
    source_workload_credential_generation: str
    vendor_principal_id: str
    state_port_scope: str
    credential_generation: str
    issued_at: datetime
    expires_at: datetime

    def __post_init__(self) -> None:
        if self.vendor_principal_id == self.source_workload_principal_id:
            raise ValueError("vendor identity must not become canonical workload identity")
        if self.credential_generation == self.source_workload_credential_generation:
            raise ValueError("vendor credential generation must be independently revocable")
        if self.expires_at <= self.issued_at:
            raise ValueError("vendor credential must expire after issuance")
        if self.expires_at - self.issued_at > MAX_VENDOR_TTL:
            raise ValueError("vendor credential exceeds bounded short-lived profile")


class BoundedVendorCredentialAdapter:
    """Evidence-only adapter for the IR-D-002 broker/state-port exchange contract.

    No vendor secret value is materialized. The grant records only non-secret authority
    metadata so the probe can falsify broadening, tenant injection and identity collapse.
    """

    def __init__(self, *, current_principal: Principal) -> None:
        self.current_principal = current_principal
        self.calls = 0

    def exchange(
        self,
        *,
        principal: Principal,
        requested_scope: str,
        tenant_binding: str | None,
        now: datetime,
    ) -> VendorCredentialGrant:
        self.calls += 1
        if principal.kind is not PrincipalKind.INTERNAL_SERVICE_PRINCIPAL:
            raise AdmissionDenied("vendor adapter requires authenticated internal service principal")
        if principal.active is not True or principal != self.current_principal:
            raise AdmissionDenied("vendor adapter requires current workload principal generation")

        identity = parse_workload_identity(principal.principal_id)
        if identity.environment_class is not EnvironmentClass.VALIDATION:
            raise AdmissionDenied("vendor adapter workload environment is outside accepted scope")
        if identity.runtime_profile_id != API_AUTH_BOUNDARY.runtime_profile_id:
            raise AdmissionDenied("vendor adapter workload runtime profile is outside accepted scope")
        if tenant_binding is not None:
            raise AdmissionDenied("vendor credential cannot encode or broaden tenant authority")
        if requested_scope != ALLOWED_SCOPE:
            raise AdmissionDenied("vendor credential scope exceeds exact least-privilege state-port scope")
        if now.tzinfo is None or now.utcoffset() is None:
            raise AdmissionDenied("vendor credential issuance time must be authoritative UTC evidence")
        issued_at = now.astimezone(timezone.utc)
        return VendorCredentialGrant(
            source_workload_principal_id=principal.principal_id,
            source_workload_credential_generation=principal.credential_generation,
            vendor_principal_id=VENDOR_PRINCIPAL_ID,
            state_port_scope=ALLOWED_SCOPE,
            credential_generation=VENDOR_CREDENTIAL_GENERATION,
            issued_at=issued_at,
            expires_at=issued_at + timedelta(seconds=20),
        )


def main() -> int:
    evidence_dir_raw = os.environ.get("SPIRE_EVIDENCE_DIR")
    if not evidence_dir_raw:
        raise SystemExit("SPIRE_EVIDENCE_DIR is required")
    evidence_dir = Path(evidence_dir_raw).resolve()
    if not evidence_dir.is_dir():
        raise SystemExit(f"SPIRE evidence directory does not exist: {evidence_dir}")

    cert = _single_file(evidence_dir, "svid.*.pem", reject_suffix=".key")
    bundle = _single_file(evidence_dir, "bundle.*.pem")
    san_text = _run("openssl", "x509", "-in", str(cert), "-noout", "-ext", "subjectAltName")
    wire_uris = _URI_RE.findall(san_text)
    if wire_uris != [WIRE_SPIFFE_ID]:
        raise SystemExit(f"unexpected SPIRE wire identity set: {wire_uris!r}")

    not_before = _openssl_date(cert, "-startdate")
    not_after = _openssl_date(cert, "-enddate")
    evaluation_now = not_before + timedelta(seconds=1)
    if evaluation_now >= not_after:
        raise AssertionError("SPIRE workload SVID validity window is too small for adapter probe")

    bundle_generation = _digest_id("bundle", bundle)
    workload_generation = _digest_id("svid", cert)
    peer = VerifiedWorkloadPeer(
        spiffe_id=CANONICAL_SPIFFE_ID,
        certificate_not_before=not_before,
        certificate_not_after=not_after,
        trust_bundle_generation=bundle_generation,
        workload_credential_generation=workload_generation,
    )
    principal = admit_workload_peer(
        peer=peer,
        expected_trust_domain=TRUST_DOMAIN,
        expected_environment=EnvironmentClass.VALIDATION,
        allowed_runtime_profiles=frozenset({API_AUTH_BOUNDARY.runtime_profile_id}),
        current_trust_bundle_generation=bundle_generation,
        current_workload_credential_generation=workload_generation,
        current_max_certificate_lifetime=timedelta(seconds=45),
        now=evaluation_now,
    )
    if principal.kind is not PrincipalKind.INTERNAL_SERVICE_PRINCIPAL:
        raise AssertionError("SPIRE workload did not remain an internal service principal")
    if principal.principal_id != CANONICAL_SPIFFE_ID:
        raise AssertionError("SPIRE wire adapter changed canonical workload principal")

    adapter = BoundedVendorCredentialAdapter(current_principal=principal)
    grant = adapter.exchange(
        principal=principal,
        requested_scope=ALLOWED_SCOPE,
        tenant_binding=None,
        now=evaluation_now,
    )
    if grant.state_port_scope != ALLOWED_SCOPE:
        raise AssertionError("vendor adapter broadened the requested state-port capability")
    if grant.vendor_principal_id == principal.principal_id:
        raise AssertionError("vendor principal became canonical platform workload identity")
    if grant.credential_generation == principal.credential_generation:
        raise AssertionError("vendor credential is not independently revocable from workload identity")
    if grant.expires_at - grant.issued_at > MAX_VENDOR_TTL:
        raise AssertionError("vendor credential exceeded bounded short-lived profile")

    _expect_denied(
        "admin_scope",
        "scope exceeds exact least-privilege",
        lambda: adapter.exchange(
            principal=principal,
            requested_scope=FORBIDDEN_ADMIN_SCOPE,
            tenant_binding=None,
            now=evaluation_now,
        ),
    )
    _expect_denied(
        "owner_scope",
        "scope exceeds exact least-privilege",
        lambda: adapter.exchange(
            principal=principal,
            requested_scope=FORBIDDEN_OWNER_SCOPE,
            tenant_binding=None,
            now=evaluation_now,
        ),
    )
    _expect_denied(
        "tenant_injection",
        "cannot encode or broaden tenant authority",
        lambda: adapter.exchange(
            principal=principal,
            requested_scope=ALLOWED_SCOPE,
            tenant_binding="tenant-forbidden",
            now=evaluation_now,
        ),
    )

    stale_principal = Principal(
        principal_id=principal.principal_id,
        kind=principal.kind,
        credential_generation="stale-workload-generation",
    )
    _expect_denied(
        "stale_workload_generation",
        "current workload principal generation",
        lambda: adapter.exchange(
            principal=stale_principal,
            requested_scope=ALLOWED_SCOPE,
            tenant_binding=None,
            now=evaluation_now,
        ),
    )

    # The vendor identity is evidence for the downstream vendor boundary only. It is not a
    # SPIFFE URI and therefore cannot be parsed back into canonical workload identity.
    try:
        parse_workload_identity(grant.vendor_principal_id)
    except AdmissionDenied:
        pass
    else:
        raise AssertionError("vendor principal was unexpectedly accepted as canonical workload identity")

    if adapter.calls != 5:
        raise AssertionError(f"unexpected vendor adapter call count: {adapter.calls}")

    print(
        "vendor_credential_adapter_least_privilege=PASS "
        f"wire_spiffe_id={WIRE_SPIFFE_ID} canonical_principal={principal.principal_id} "
        f"allowed_scope={ALLOWED_SCOPE} vendor_principal={grant.vendor_principal_id} "
        "admin_scope_denied=true owner_scope_denied=true tenant_injection_denied=true "
        "stale_workload_generation_denied=true independently_revocable=true short_lived=true "
        "vendor_identity_noncanonical=true secret_material_exported=false"
    )
    print(
        "conformance_claim=exploratory_only evidence_credited=false ledger_change=false "
        "wave4=not_granted production=none d4=not_selected_not_granted"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
