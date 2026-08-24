from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Protocol

from .model import AdmissionDenied, Principal, PrincipalKind

MAX_MACHINE_JTI_BYTES = 512


class ReplayClaim(str, Enum):
    CLAIMED = "claimed"
    ALREADY_USED = "already_used"
    AUTHORITY_UNAVAILABLE = "authority_unavailable"
    CONTINUITY_UNPROVEN = "continuity_unproven"


@dataclass(frozen=True)
class VerifiedMachineAssertion:
    """Claims emitted only after trusted signature/client-key verification."""

    client_principal: str
    jti: str
    audience: str
    issued_at: datetime
    not_before: datetime
    expires_at: datetime
    key_generation: str
    replay_generation: str


class MachineAssertionVerificationPort(Protocol):
    def verify(self, *, compact_assertion: str, expected_client_principal: str) -> VerifiedMachineAssertion:
        """Verify signature/client binding and return normalized trusted claims."""


class MachineReplayAuthority(Protocol):
    def claim_once(
        self,
        *,
        client_principal: str,
        jti: str,
        valid_until: datetime,
        replay_generation: str,
    ) -> ReplayClaim:
        """One logical atomic single-winner claim across all accepting replicas."""


def _utc(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("time must be a timezone-aware datetime")
    return value.astimezone(timezone.utc)


def authenticate_machine_assertion(
    *,
    verifier: MachineAssertionVerificationPort,
    replay_authority: MachineReplayAuthority,
    compact_assertion: str,
    expected_client_principal: str,
    expected_audience: str,
    current_key_generation: str,
    current_replay_generation: str,
    current_max_assertion_lifetime: timedelta,
    now: datetime,
) -> Principal:
    """Authenticate one replay-bounded machine assertion under current Security policy."""

    now = _utc(now)
    if not isinstance(current_max_assertion_lifetime, timedelta) or current_max_assertion_lifetime <= timedelta(0):
        raise AdmissionDenied("current machine assertion lifetime policy is unavailable or invalid")
    verified = verifier.verify(
        compact_assertion=compact_assertion,
        expected_client_principal=expected_client_principal,
    )
    if not isinstance(verified, VerifiedMachineAssertion):
        raise AdmissionDenied("machine assertion verifier returned malformed trusted evidence")
    if verified.client_principal != expected_client_principal:
        raise AdmissionDenied("machine principal binding mismatch")
    if verified.audience != expected_audience:
        raise AdmissionDenied("machine assertion audience mismatch")
    if verified.key_generation != current_key_generation:
        raise AdmissionDenied("machine assertion key generation is not current")
    if verified.replay_generation != current_replay_generation:
        raise AdmissionDenied("machine replay generation is not current")

    issued_at = _utc(verified.issued_at)
    not_before = _utc(verified.not_before)
    expires_at = _utc(verified.expires_at)
    if expires_at <= not_before or expires_at <= issued_at:
        raise AdmissionDenied("machine assertion validity interval is malformed")
    if expires_at - issued_at > current_max_assertion_lifetime:
        raise AdmissionDenied("machine assertion exceeds current short-lived Security policy")
    if not (not_before <= now < expires_at):
        raise AdmissionDenied("machine assertion outside accepted validity interval")
    if issued_at > now:
        raise AdmissionDenied("machine assertion issued in the future")
    if not isinstance(verified.jti, str) or not verified.jti or len(verified.jti.encode("utf-8")) > MAX_MACHINE_JTI_BYTES:
        raise AdmissionDenied("machine assertion jti is missing or exceeds the bounded replay identity envelope")
    if any(ord(char) < 0x20 or ord(char) == 0x7F for char in verified.jti):
        raise AdmissionDenied("machine assertion jti contains control characters")

    claim = replay_authority.claim_once(
        client_principal=verified.client_principal,
        jti=verified.jti,
        valid_until=expires_at,
        replay_generation=verified.replay_generation,
    )
    if claim is not ReplayClaim.CLAIMED:
        raise AdmissionDenied("machine assertion replay admission denied")

    return Principal(
        principal_id=verified.client_principal,
        kind=PrincipalKind.MACHINE_API_PRINCIPAL,
        credential_generation=verified.key_generation,
    )
