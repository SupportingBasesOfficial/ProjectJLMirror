from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import re
from urllib.parse import urlsplit

from .model import AdmissionDenied, EnvironmentClass, Principal, PrincipalKind

_TRUST_DOMAIN_RE = re.compile(r"^[a-z0-9](?:[a-z0-9.-]{0,251}[a-z0-9])?$")
_SEGMENT_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._@-]{0,127}$")
_RUNTIME_PROFILE_RE = re.compile(r"^runtime\.[a-z0-9-]+(?:\.[a-z0-9-]+)*@[1-9][0-9]*$")


def _explicit(value: object, field: str) -> str:
    if (
        not isinstance(value, str)
        or not value
        or value != value.strip()
        or any(ord(char) < 0x20 or ord(char) == 0x7F for char in value)
    ):
        raise ValueError(f"{field} must be an explicit canonical string")
    return value


def _utc(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("time must be timezone-aware")
    return value.astimezone(timezone.utc)


def _trust_domain(value: object, field: str) -> str:
    text = _explicit(value, field)
    if not _TRUST_DOMAIN_RE.fullmatch(text) or ".." in text or text.lower() != text:
        raise ValueError(f"{field} must be a canonical lower-case SPIFFE trust domain")
    return text


@dataclass(frozen=True)
class WorkloadIdentity:
    trust_domain: str
    environment_class: EnvironmentClass
    runtime_profile_id: str
    workload_id: str

    def __post_init__(self) -> None:
        _trust_domain(self.trust_domain, "trust_domain")
        if not isinstance(self.environment_class, EnvironmentClass):
            raise ValueError("environment_class must be canonical")
        if not _RUNTIME_PROFILE_RE.fullmatch(self.runtime_profile_id):
            raise ValueError("runtime_profile_id must be a canonical runtime profile")
        _explicit(self.workload_id, "workload_id")
        if not _SEGMENT_RE.fullmatch(self.workload_id):
            raise ValueError("workload_id must be a canonical SPIFFE path segment")

    @property
    def spiffe_id(self) -> str:
        return (
            f"spiffe://{self.trust_domain}/{self.environment_class.value}/"
            f"{self.runtime_profile_id}/{self.workload_id}"
        )


@dataclass(frozen=True)
class VerifiedWorkloadPeer:
    """Output of a trusted mTLS/X.509-SVID verification adapter."""

    spiffe_id: str
    certificate_not_before: datetime
    certificate_not_after: datetime
    trust_bundle_generation: str
    workload_credential_generation: str

    def __post_init__(self) -> None:
        _explicit(self.spiffe_id, "spiffe_id")
        not_before = _utc(self.certificate_not_before)
        not_after = _utc(self.certificate_not_after)
        if not_after <= not_before:
            raise ValueError("workload certificate validity interval is malformed")
        _explicit(self.trust_bundle_generation, "trust_bundle_generation")
        _explicit(self.workload_credential_generation, "workload_credential_generation")


def parse_workload_identity(value: str) -> WorkloadIdentity:
    if not isinstance(value, str) or "%" in value or "\\" in value:
        raise AdmissionDenied("workload identity is not canonically encoded")
    try:
        parsed = urlsplit(value)
        username = parsed.username
        password = parsed.password
        port = parsed.port
        hostname = parsed.hostname
    except (TypeError, ValueError) as exc:
        raise AdmissionDenied("malformed SPIFFE authority is denied") from exc
    if parsed.scheme != "spiffe" or not parsed.netloc or parsed.query or parsed.fragment:
        raise AdmissionDenied("invalid SPIFFE workload identity")
    if username is not None or password is not None or port is not None:
        raise AdmissionDenied("SPIFFE authority cannot contain userinfo or port")
    trust_domain = hostname or ""
    if trust_domain != parsed.netloc or not _TRUST_DOMAIN_RE.fullmatch(trust_domain) or ".." in trust_domain:
        raise AdmissionDenied("invalid or non-canonical SPIFFE trust domain")

    segments = parsed.path.split("/")[1:]
    if len(segments) != 3 or any(not _SEGMENT_RE.fullmatch(segment) for segment in segments):
        raise AdmissionDenied("workload identity must contain exact environment/runtime/workload segments")
    environment_raw, runtime_profile_id, workload_id = segments
    try:
        environment = EnvironmentClass(environment_raw)
    except ValueError as exc:
        raise AdmissionDenied("workload identity environment class is not canonical") from exc
    if not _RUNTIME_PROFILE_RE.fullmatch(runtime_profile_id):
        raise AdmissionDenied("workload identity runtime profile is not canonical")
    try:
        return WorkloadIdentity(
            trust_domain=trust_domain,
            environment_class=environment,
            runtime_profile_id=runtime_profile_id,
            workload_id=workload_id,
        )
    except ValueError as exc:
        raise AdmissionDenied("workload identity contains non-canonical bindings") from exc


def admit_workload_peer(
    *,
    peer: VerifiedWorkloadPeer,
    expected_trust_domain: str,
    expected_environment: EnvironmentClass,
    allowed_runtime_profiles: frozenset[str],
    current_trust_bundle_generation: str,
    current_workload_credential_generation: str,
    now: datetime,
) -> Principal:
    now = _utc(now)
    if not isinstance(peer, VerifiedWorkloadPeer):
        raise AdmissionDenied("workload verifier returned malformed trusted evidence")
    try:
        expected_domain = _trust_domain(expected_trust_domain, "expected_trust_domain")
        current_bundle = _explicit(
            current_trust_bundle_generation, "current_trust_bundle_generation"
        )
        current_credential = _explicit(
            current_workload_credential_generation, "current_workload_credential_generation"
        )
    except ValueError as exc:
        raise AdmissionDenied("current workload identity authority is malformed or unavailable") from exc
    if not isinstance(expected_environment, EnvironmentClass):
        raise AdmissionDenied("expected workload environment authority is not canonical")
    if isinstance(allowed_runtime_profiles, (str, bytes)):
        raise AdmissionDenied("allowed runtime profiles must be an exact profile set")
    try:
        allowed_profiles = frozenset(allowed_runtime_profiles)
    except TypeError as exc:
        raise AdmissionDenied("allowed runtime profiles are malformed") from exc
    if not allowed_profiles or any(
        not isinstance(profile, str) or not _RUNTIME_PROFILE_RE.fullmatch(profile)
        for profile in allowed_profiles
    ):
        raise AdmissionDenied("allowed runtime profiles contain non-canonical entries")

    identity = parse_workload_identity(peer.spiffe_id)
    if identity.spiffe_id != peer.spiffe_id:
        raise AdmissionDenied("workload identity has alternate textual representation")
    if identity.trust_domain != expected_domain:
        raise AdmissionDenied("workload trust domain mismatch")
    if identity.environment_class is not expected_environment:
        raise AdmissionDenied("cross-environment workload authentication denied")
    if identity.runtime_profile_id not in allowed_profiles:
        raise AdmissionDenied("runtime profile is not authorized for this service boundary")
    if peer.trust_bundle_generation != current_bundle:
        raise AdmissionDenied("workload trust-bundle generation is stale")
    if peer.workload_credential_generation != current_credential:
        raise AdmissionDenied("workload credential generation is stale")
    if not (_utc(peer.certificate_not_before) <= now < _utc(peer.certificate_not_after)):
        raise AdmissionDenied("workload certificate is not current")

    # Deliberately returns only a service principal. Tenant/business authority must
    # be re-established separately by the owning application boundary.
    return Principal(
        principal_id=identity.spiffe_id,
        kind=PrincipalKind.INTERNAL_SERVICE_PRINCIPAL,
        credential_generation=peer.workload_credential_generation,
    )