#!/usr/bin/env python3
from __future__ import annotations

from dataclasses import dataclass, fields, replace
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import secrets
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
VENDOR_CREDENTIAL_GENERATION_PREFIX = "vendor-credential-generation-"
INITIAL_VENDOR_CREDENTIAL_EPOCH = 7
MAX_VENDOR_TTL = timedelta(seconds=30)
_URI_RE = re.compile(r"URI:([^,\s]+)")
_AUTHORITY_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:@/-]{0,255}$")


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


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise AdmissionDenied("vendor credential time must be authoritative UTC evidence")
    return value.astimezone(timezone.utc)


def _expect_denied(label: str, fragment: str, call) -> None:
    try:
        call()
    except AdmissionDenied as exc:
        if fragment not in str(exc):
            raise AssertionError(
                f"{label}: wrong denial reason; expected fragment={fragment!r} actual={str(exc)!r}"
            ) from exc
        return
    raise AssertionError(f"{label}: vendor credential authority unexpectedly admitted the operation")


@dataclass(frozen=True)
class VendorCredentialGrant:
    credential_id: str
    source_workload_principal_id: str
    source_workload_credential_generation: str
    vendor_principal_id: str
    state_port_scope: str
    credential_generation: str
    issued_at: datetime
    expires_at: datetime
    authenticator: str

    def __post_init__(self) -> None:
        if not self.credential_id or any(ch.isspace() for ch in self.credential_id):
            raise ValueError("vendor credential id must be opaque and non-empty")
        if self.vendor_principal_id == self.source_workload_principal_id:
            raise ValueError("vendor identity must not become canonical workload identity")
        if self.credential_generation == self.source_workload_credential_generation:
            raise ValueError("vendor credential generation must be independent from workload generation")
        issued_at = _utc(self.issued_at)
        expires_at = _utc(self.expires_at)
        if expires_at <= issued_at:
            raise ValueError("vendor credential must expire after issuance")
        if expires_at - issued_at > MAX_VENDOR_TTL:
            raise ValueError("vendor credential exceeds bounded short-lived profile")
        if not re.fullmatch(r"[0-9a-f]{64}", self.authenticator):
            raise ValueError("vendor credential authenticator must be an HMAC-SHA256 tag")


class VendorCredentialAuthority:
    """Evidence-only vendor-side short-lived credential issuer/verifier.

    The issuer key never crosses the authority boundary. Callers receive only a bounded,
    authenticated short-lived grant. Revocation is an independent credential-generation
    transition and therefore does not mutate canonical SPIFFE workload identity.
    """

    def __init__(self) -> None:
        self._issuer_key = secrets.token_bytes(32)
        self._credential_epoch = INITIAL_VENDOR_CREDENTIAL_EPOCH
        self.issue_calls = 0
        self.verify_calls = 0

    @property
    def current_generation(self) -> str:
        return f"{VENDOR_CREDENTIAL_GENERATION_PREFIX}{self._credential_epoch}"

    @staticmethod
    def _payload(
        *,
        credential_id: str,
        source_workload_principal_id: str,
        source_workload_credential_generation: str,
        vendor_principal_id: str,
        state_port_scope: str,
        credential_generation: str,
        issued_at: datetime,
        expires_at: datetime,
    ) -> bytes:
        body = {
            "credential_generation": credential_generation,
            "credential_id": credential_id,
            "expires_at": _utc(expires_at).isoformat(timespec="microseconds"),
            "issued_at": _utc(issued_at).isoformat(timespec="microseconds"),
            "source_workload_credential_generation": source_workload_credential_generation,
            "source_workload_principal_id": source_workload_principal_id,
            "state_port_scope": state_port_scope,
            "vendor_principal_id": vendor_principal_id,
        }
        return json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")

    def _tag(self, **kwargs) -> str:
        return hmac.new(self._issuer_key, self._payload(**kwargs), hashlib.sha256).hexdigest()

    def issue(
        self,
        *,
        source_workload_principal_id: str,
        source_workload_credential_generation: str,
        vendor_principal_id: str,
        state_port_scope: str,
        issued_at: datetime,
        ttl: timedelta,
    ) -> VendorCredentialGrant:
        self.issue_calls += 1
        if ttl <= timedelta(0) or ttl > MAX_VENDOR_TTL:
            raise AdmissionDenied("vendor credential TTL is outside bounded policy")
        issued_at = _utc(issued_at)
        expires_at = issued_at + ttl
        credential_id = f"vc_{secrets.token_hex(16)}"
        unsigned = {
            "credential_id": credential_id,
            "source_workload_principal_id": source_workload_principal_id,
            "source_workload_credential_generation": source_workload_credential_generation,
            "vendor_principal_id": vendor_principal_id,
            "state_port_scope": state_port_scope,
            "credential_generation": self.current_generation,
            "issued_at": issued_at,
            "expires_at": expires_at,
        }
        return VendorCredentialGrant(
            **unsigned,
            authenticator=self._tag(**unsigned),
        )

    def authenticate(self, grant: VendorCredentialGrant) -> None:
        self.verify_calls += 1
        expected = self._tag(
            credential_id=grant.credential_id,
            source_workload_principal_id=grant.source_workload_principal_id,
            source_workload_credential_generation=grant.source_workload_credential_generation,
            vendor_principal_id=grant.vendor_principal_id,
            state_port_scope=grant.state_port_scope,
            credential_generation=grant.credential_generation,
            issued_at=grant.issued_at,
            expires_at=grant.expires_at,
        )
        if not hmac.compare_digest(expected, grant.authenticator):
            raise AdmissionDenied("vendor credential authentication failed")

    def advance_generation(self, *, expected_generation: str) -> str:
        if expected_generation != self.current_generation:
            raise AdmissionDenied("vendor credential generation advance lost currentness race")
        self._credential_epoch += 1
        return self.current_generation


class WorkloadCurrentnessAuthority:
    """Live platform authority consulted for every vendor exchange/admission.

    This authority is deliberately distinct from both the caller-supplied peer evidence and
    the vendor credential authority. A SPIRE/workload credential generation can therefore
    be revoked or rotated while the old certificate remains inside its X.509 validity window.
    """

    def __init__(self, *, trust_bundle_generation: str, workload_credential_generation: str) -> None:
        if not _AUTHORITY_ID_RE.fullmatch(trust_bundle_generation):
            raise ValueError("current workload trust-bundle generation is malformed")
        if not _AUTHORITY_ID_RE.fullmatch(workload_credential_generation):
            raise ValueError("current workload credential generation is malformed")
        self._trust_bundle_generation = trust_bundle_generation
        self._workload_credential_generation = workload_credential_generation
        self.read_calls = 0
        self.generation_advances = 0

    @property
    def current_workload_credential_generation(self) -> str:
        return self._workload_credential_generation

    def snapshot(self) -> tuple[str, str]:
        self.read_calls += 1
        return self._trust_bundle_generation, self._workload_credential_generation

    def advance_workload_credential_generation(
        self,
        *,
        expected_generation: str,
        successor_generation: str,
    ) -> str:
        if expected_generation != self._workload_credential_generation:
            raise AdmissionDenied("workload credential generation advance lost currentness race")
        if (
            successor_generation == expected_generation
            or not _AUTHORITY_ID_RE.fullmatch(successor_generation)
        ):
            raise AdmissionDenied("successor workload credential generation is invalid")
        self._workload_credential_generation = successor_generation
        self.generation_advances += 1
        return successor_generation


class BoundedVendorCredentialAdapter:
    """Evidence-only IR-D-002 broker/state-port exchange and live-currentness boundary."""

    def __init__(
        self,
        *,
        workload_currentness_authority: WorkloadCurrentnessAuthority,
        credential_authority: VendorCredentialAuthority,
    ) -> None:
        self._workload_currentness_authority = workload_currentness_authority
        self._credential_authority = credential_authority
        self.exchange_calls = 0
        self.admission_calls = 0

    @property
    def current_vendor_credential_generation(self) -> str:
        return self._credential_authority.current_generation

    @property
    def current_workload_credential_generation(self) -> str:
        return self._workload_currentness_authority.current_workload_credential_generation

    def _admit_current_workload(self, peer: VerifiedWorkloadPeer, *, now: datetime) -> Principal:
        current_bundle_generation, current_workload_generation = (
            self._workload_currentness_authority.snapshot()
        )
        principal = admit_workload_peer(
            peer=peer,
            expected_trust_domain=TRUST_DOMAIN,
            expected_environment=EnvironmentClass.VALIDATION,
            allowed_runtime_profiles=frozenset({API_AUTH_BOUNDARY.runtime_profile_id}),
            current_trust_bundle_generation=current_bundle_generation,
            current_workload_credential_generation=current_workload_generation,
            current_max_certificate_lifetime=timedelta(seconds=45),
            now=_utc(now),
        )
        if principal.kind is not PrincipalKind.INTERNAL_SERVICE_PRINCIPAL or principal.active is not True:
            raise AdmissionDenied("vendor adapter requires authenticated current internal service principal")
        return principal

    def exchange(
        self,
        *,
        peer: VerifiedWorkloadPeer,
        requested_scope: str,
        tenant_binding: str | None,
        now: datetime,
    ) -> VendorCredentialGrant:
        self.exchange_calls += 1
        principal = self._admit_current_workload(peer, now=now)
        if tenant_binding is not None:
            raise AdmissionDenied("vendor credential cannot encode or broaden tenant authority")
        if requested_scope != ALLOWED_SCOPE:
            raise AdmissionDenied("vendor credential scope exceeds exact least-privilege state-port scope")
        return self._credential_authority.issue(
            source_workload_principal_id=principal.principal_id,
            source_workload_credential_generation=principal.credential_generation,
            vendor_principal_id=VENDOR_PRINCIPAL_ID,
            state_port_scope=ALLOWED_SCOPE,
            issued_at=_utc(now),
            ttl=timedelta(seconds=20),
        )

    def admit_grant(
        self,
        *,
        grant: VendorCredentialGrant,
        peer: VerifiedWorkloadPeer,
        now: datetime,
    ) -> None:
        self.admission_calls += 1
        if not isinstance(grant, VendorCredentialGrant):
            raise AdmissionDenied("vendor credential representation is malformed")
        # Authenticity is established before any caller-supplied grant metadata is trusted.
        self._credential_authority.authenticate(grant)
        # The peer is then re-admitted against the live workload authority on every use.
        principal = self._admit_current_workload(peer, now=now)
        if grant.source_workload_principal_id != principal.principal_id:
            raise AdmissionDenied("vendor credential source workload principal is stale or mismatched")
        if grant.source_workload_credential_generation != principal.credential_generation:
            raise AdmissionDenied("vendor credential source workload generation is stale")
        if grant.vendor_principal_id != VENDOR_PRINCIPAL_ID:
            raise AdmissionDenied("vendor credential principal is outside governed adapter identity")
        if grant.state_port_scope != ALLOWED_SCOPE:
            raise AdmissionDenied("vendor credential scope exceeds exact least-privilege state-port scope")
        if grant.credential_generation != self.current_vendor_credential_generation:
            raise AdmissionDenied("vendor credential generation is stale")
        current = _utc(now)
        if current < _utc(grant.issued_at):
            raise AdmissionDenied("vendor credential is not yet valid")
        if current >= _utc(grant.expires_at):
            raise AdmissionDenied("vendor credential is expired")

    def advance_vendor_credential_generation(self, *, expected_generation: str) -> str:
        return self._credential_authority.advance_generation(expected_generation=expected_generation)

    def advance_workload_credential_generation(
        self,
        *,
        expected_generation: str,
        successor_generation: str,
    ) -> str:
        return self._workload_currentness_authority.advance_workload_credential_generation(
            expected_generation=expected_generation,
            successor_generation=successor_generation,
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

    credential_authority = VendorCredentialAuthority()
    workload_currentness_authority = WorkloadCurrentnessAuthority(
        trust_bundle_generation=bundle_generation,
        workload_credential_generation=workload_generation,
    )
    adapter = BoundedVendorCredentialAdapter(
        workload_currentness_authority=workload_currentness_authority,
        credential_authority=credential_authority,
    )
    grant = adapter.exchange(
        peer=peer,
        requested_scope=ALLOWED_SCOPE,
        tenant_binding=None,
        now=evaluation_now,
    )
    adapter.admit_grant(grant=grant, peer=peer, now=evaluation_now + timedelta(seconds=1))
    if grant.state_port_scope != ALLOWED_SCOPE:
        raise AssertionError("vendor adapter broadened requested state-port capability")
    if grant.vendor_principal_id == principal.principal_id:
        raise AssertionError("vendor principal became canonical platform workload identity")
    if grant.credential_generation == principal.credential_generation:
        raise AssertionError("vendor credential generation collapsed into workload generation")
    if grant.expires_at - grant.issued_at > MAX_VENDOR_TTL:
        raise AssertionError("vendor credential exceeded bounded short-lived profile")
    if "_issuer_key" in {field.name for field in fields(VendorCredentialGrant)}:
        raise AssertionError("vendor issuer key leaked into credential representation")
    if hasattr(credential_authority, "issuer_key"):
        raise AssertionError("vendor credential authority exposed a public issuer-key accessor")

    _expect_denied(
        "admin_scope",
        "scope exceeds exact least-privilege",
        lambda: adapter.exchange(
            peer=peer,
            requested_scope=FORBIDDEN_ADMIN_SCOPE,
            tenant_binding=None,
            now=evaluation_now,
        ),
    )
    _expect_denied(
        "owner_scope",
        "scope exceeds exact least-privilege",
        lambda: adapter.exchange(
            peer=peer,
            requested_scope=FORBIDDEN_OWNER_SCOPE,
            tenant_binding=None,
            now=evaluation_now,
        ),
    )
    _expect_denied(
        "tenant_injection",
        "cannot encode or broaden tenant authority",
        lambda: adapter.exchange(
            peer=peer,
            requested_scope=ALLOWED_SCOPE,
            tenant_binding="tenant-forbidden",
            now=evaluation_now,
        ),
    )

    stale_peer = replace(peer, workload_credential_generation="stale-workload-generation")
    _expect_denied(
        "stale_workload_generation",
        "workload credential generation is stale",
        lambda: adapter.exchange(
            peer=stale_peer,
            requested_scope=ALLOWED_SCOPE,
            tenant_binding=None,
            now=evaluation_now,
        ),
    )
    _expect_denied(
        "expired_workload_exchange",
        "workload certificate is not current",
        lambda: adapter.exchange(
            peer=peer,
            requested_scope=ALLOWED_SCOPE,
            tenant_binding=None,
            now=not_after,
        ),
    )

    workload_generation_before_vendor_revocation = adapter.current_workload_credential_generation
    successor_vendor_generation = adapter.advance_vendor_credential_generation(
        expected_generation=grant.credential_generation
    )
    if successor_vendor_generation == grant.credential_generation:
        raise AssertionError("vendor credential authority failed to advance independently")
    if adapter.current_workload_credential_generation != workload_generation_before_vendor_revocation:
        raise AssertionError("vendor credential revocation changed live workload identity generation")

    # Caller-constructible metadata is insufficient: every security-relevant field is MACed.
    forged_current_generation = replace(
        grant,
        credential_id="vc_forged00000000000000000000000000",
        credential_generation=successor_vendor_generation,
        authenticator="0" * 64,
    )
    _expect_denied(
        "forged_vendor_grant",
        "vendor credential authentication failed",
        lambda: adapter.admit_grant(
            grant=forged_current_generation,
            peer=peer,
            now=evaluation_now + timedelta(seconds=2),
        ),
    )
    tampered_scope = replace(grant, state_port_scope=FORBIDDEN_ADMIN_SCOPE)
    _expect_denied(
        "tampered_vendor_grant",
        "vendor credential authentication failed",
        lambda: adapter.admit_grant(
            grant=tampered_scope,
            peer=peer,
            now=evaluation_now + timedelta(seconds=2),
        ),
    )

    stale_grant_check_time = evaluation_now + timedelta(seconds=2)
    if stale_grant_check_time >= grant.expires_at:
        raise AssertionError("vendor revocation negative control accidentally depends on TTL expiry")
    _expect_denied(
        "revoked_vendor_generation",
        "vendor credential generation is stale",
        lambda: adapter.admit_grant(
            grant=grant,
            peer=peer,
            now=stale_grant_check_time,
        ),
    )

    successor_grant = adapter.exchange(
        peer=peer,
        requested_scope=ALLOWED_SCOPE,
        tenant_binding=None,
        now=evaluation_now + timedelta(seconds=3),
    )
    if successor_grant.credential_generation != successor_vendor_generation:
        raise AssertionError("successor vendor credential did not bind current vendor generation")
    if successor_grant.source_workload_credential_generation != principal.credential_generation:
        raise AssertionError("successor vendor credential lost workload-generation binding")
    adapter.admit_grant(
        grant=successor_grant,
        peer=peer,
        now=evaluation_now + timedelta(seconds=4),
    )

    # A live workload-generation rotation/revocation must invalidate the old peer immediately,
    # even while both its X.509 validity window and the vendor grant TTL remain open.
    live_workload_revocation_time = evaluation_now + timedelta(seconds=5)
    if live_workload_revocation_time >= not_after:
        raise AssertionError("live workload-generation negative control accidentally depends on SVID expiry")
    if live_workload_revocation_time >= successor_grant.expires_at:
        raise AssertionError("live workload-generation negative control accidentally depends on vendor TTL")
    successor_workload_generation = "svid:post-revocation-generation"
    adapter.advance_workload_credential_generation(
        expected_generation=workload_generation_before_vendor_revocation,
        successor_generation=successor_workload_generation,
    )
    _expect_denied(
        "live_workload_generation_revoked_exchange",
        "workload credential generation is stale",
        lambda: adapter.exchange(
            peer=peer,
            requested_scope=ALLOWED_SCOPE,
            tenant_binding=None,
            now=live_workload_revocation_time,
        ),
    )
    _expect_denied(
        "live_workload_generation_revoked_grant_admission",
        "workload credential generation is stale",
        lambda: adapter.admit_grant(
            grant=successor_grant,
            peer=peer,
            now=live_workload_revocation_time,
        ),
    )
    if workload_currentness_authority.generation_advances != 1:
        raise AssertionError("live workload currentness authority did not record exactly one generation advance")
    if workload_currentness_authority.read_calls < 2:
        raise AssertionError("vendor adapter did not query live workload currentness on protected operations")

    try:
        parse_workload_identity(successor_grant.vendor_principal_id)
    except AdmissionDenied:
        pass
    else:
        raise AssertionError("vendor principal was accepted as canonical workload identity")

    print(
        "vendor_credential_adapter_least_privilege=PASS "
        f"wire_spiffe_id={WIRE_SPIFFE_ID} canonical_principal={principal.principal_id} "
        f"allowed_scope={ALLOWED_SCOPE} vendor_principal={successor_grant.vendor_principal_id} "
        "admin_scope_denied=true owner_scope_denied=true tenant_injection_denied=true "
        "stale_workload_generation_denied=true expired_workload_exchange_denied=true "
        "credential_authentication=hmac_sha256 forged_vendor_grant_denied=true "
        "tampered_vendor_grant_denied=true authenticated_consumption_path=true "
        "independent_vendor_generation_advanced=true stale_vendor_grant_denied_before_expiry=true "
        "current_workload_generation_unchanged=true successor_vendor_grant_admitted=true "
        "live_workload_currentness_authority=true re_admit_verified_peer_per_operation=true "
        "live_workload_generation_revoked_before_svid_expiry=true "
        "live_workload_generation_revoked_exchange_denied=true "
        "live_workload_generation_revoked_grant_denied=true "
        "independently_revocable=true short_lived=true vendor_identity_noncanonical=true "
        "issuer_key_exported=false secret_material_exported=false"
    )
    print(
        "conformance_claim=exploratory_only evidence_credited=false ledger_change=false "
        "wave4=not_granted production=none d4=not_selected_not_granted"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
