from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import base64
import hashlib
import hmac
import re
import secrets
from typing import Protocol

from .model import AdmissionDenied, AuthenticationStrengthEvidence, Principal, PrincipalKind

_TRANSACTION_ID_RE = re.compile(r"^[A-Za-z0-9_-]{32}$")
_SHA256_HEX_RE = re.compile(r"^[0-9a-f]{64}$")
_PKCE_VERIFIER_RE = re.compile(r"^[A-Za-z0-9._~-]{43,128}$")


def _utc(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("time must be a timezone-aware datetime")
    return value.astimezone(timezone.utc)


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _b64url_sha256(value: str) -> str:
    digest = hashlib.sha256(value.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def _trusted_binding(value: str, field: str) -> str:
    if (
        not isinstance(value, str)
        or not value
        or value != value.strip()
        or any(ord(c) < 0x20 or ord(c) == 0x7F for c in value)
    ):
        raise ValueError(f"{field} must be an explicit trusted binding")
    return value


def _transaction_id(value: object) -> str:
    if not isinstance(value, str) or not _TRANSACTION_ID_RE.fullmatch(value):
        raise AdmissionDenied("authorization transaction id is not a canonical BFF transaction identifier")
    return value


@dataclass(frozen=True, repr=False)
class BrowserAuthTransaction:
    transaction_id: str
    initiating_session_digest: str
    state_digest: str
    nonce_digest: str
    pkce_verifier: str
    expected_issuer: str
    expected_client_id: str
    expected_redirect_uri: str
    created_at: datetime
    expires_at: datetime

    def __post_init__(self) -> None:
        if not _TRANSACTION_ID_RE.fullmatch(self.transaction_id):
            raise ValueError("transaction_id must match the BFF-generated opaque identifier profile")
        for field in ("initiating_session_digest", "state_digest", "nonce_digest"):
            if not _SHA256_HEX_RE.fullmatch(getattr(self, field)):
                raise ValueError(f"{field} must be an exact SHA-256 digest")
        if not isinstance(self.pkce_verifier, str) or not _PKCE_VERIFIER_RE.fullmatch(self.pkce_verifier):
            raise ValueError("PKCE verifier outside RFC 7636 unreserved/length envelope")
        _trusted_binding(self.expected_issuer, "expected_issuer")
        _trusted_binding(self.expected_client_id, "expected_client_id")
        _trusted_binding(self.expected_redirect_uri, "expected_redirect_uri")
        created = _utc(self.created_at)
        expires = _utc(self.expires_at)
        if expires <= created:
            raise ValueError("authorization transaction expiry must follow creation")

    def __repr__(self) -> str:
        return (
            "BrowserAuthTransaction("
            f"transaction_id={self.transaction_id!r}, initiating_session_digest=<redacted>, "
            "state_digest=<redacted>, nonce_digest=<redacted>, pkce_verifier=<redacted>, "
            f"expected_issuer={self.expected_issuer!r}, expected_client_id={self.expected_client_id!r}, "
            f"expected_redirect_uri={self.expected_redirect_uri!r}, created_at={self.created_at!r}, "
            f"expires_at={self.expires_at!r})"
        )


@dataclass(frozen=True, repr=False)
class BrowserAuthInitiation:
    transaction: BrowserAuthTransaction
    state: str
    nonce: str
    pkce_challenge: str

    def __repr__(self) -> str:
        return (
            "BrowserAuthInitiation("
            f"transaction_id={self.transaction.transaction_id!r}, "
            "state=<redacted>, nonce=<redacted>, pkce_challenge=<redacted>)"
        )


@dataclass(frozen=True)
class VerifiedOidcIdentity:
    """Output of a trusted OIDC adapter after cryptographic/token validation."""

    principal_id: str
    issuer: str
    client_id: str
    nonce: str
    authenticated_at: datetime
    token_expires_at: datetime
    acr: str | None
    amr: frozenset[str]
    policy_version: str


class BrowserTransactionAuthority(Protocol):
    def consume(self, transaction_id: str) -> BrowserAuthTransaction | None:
        """Atomically return-and-retire one transaction, or None if absent/consumed."""


class OidcVerificationPort(Protocol):
    def exchange_and_verify(
        self,
        *,
        authorization_code: str,
        pkce_verifier: str,
        expected_issuer: str,
        expected_client_id: str,
        expected_redirect_uri: str,
    ) -> VerifiedOidcIdentity:
        """Exchange code server-side and verify signature/issuer/audience/client/time."""


class AuthenticationStrengthPolicyPort(Protocol):
    def permits(
        self,
        *,
        policy_id: str,
        evidence: AuthenticationStrengthEvidence,
        now: datetime,
    ) -> bool:
        """Evaluate current Security-owned assurance policy; only literal True admits."""


def begin_browser_auth(
    *,
    session_binding: str,
    expected_issuer: str,
    expected_client_id: str,
    expected_redirect_uri: str,
    now: datetime,
    lifetime: timedelta,
) -> BrowserAuthInitiation:
    now = _utc(now)
    _trusted_binding(session_binding, "session_binding")
    _trusted_binding(expected_issuer, "expected_issuer")
    _trusted_binding(expected_client_id, "expected_client_id")
    _trusted_binding(expected_redirect_uri, "expected_redirect_uri")
    if not isinstance(lifetime, timedelta) or lifetime <= timedelta(0):
        raise ValueError("lifetime must be an explicit positive timedelta policy input")

    state = secrets.token_urlsafe(32)
    nonce = secrets.token_urlsafe(32)
    verifier = secrets.token_urlsafe(48)
    if not _PKCE_VERIFIER_RE.fullmatch(verifier):
        raise RuntimeError("generated PKCE verifier outside RFC 7636 unreserved/length envelope")

    transaction = BrowserAuthTransaction(
        transaction_id=secrets.token_urlsafe(24),
        initiating_session_digest=_digest(session_binding),
        state_digest=_digest(state),
        nonce_digest=_digest(nonce),
        pkce_verifier=verifier,
        expected_issuer=expected_issuer,
        expected_client_id=expected_client_id,
        expected_redirect_uri=expected_redirect_uri,
        created_at=now,
        expires_at=now + lifetime,
    )
    return BrowserAuthInitiation(
        transaction=transaction,
        state=state,
        nonce=nonce,
        pkce_challenge=_b64url_sha256(verifier),
    )


def complete_browser_auth(
    *,
    transaction_authority: BrowserTransactionAuthority,
    oidc_port: OidcVerificationPort,
    transaction_id: str,
    initiating_session_binding: str,
    returned_state: str,
    authorization_code: str,
    now: datetime,
) -> tuple[Principal, AuthenticationStrengthEvidence]:
    now = _utc(now)
    transaction_id = _transaction_id(transaction_id)
    try:
        initiating_session_binding = _trusted_binding(
            initiating_session_binding, "initiating_session_binding"
        )
        returned_state = _trusted_binding(returned_state, "returned_state")
        authorization_code = _trusted_binding(authorization_code, "authorization_code")
    except ValueError as exc:
        raise AdmissionDenied("browser authorization response binding is malformed") from exc

    transaction = transaction_authority.consume(transaction_id)
    if not isinstance(transaction, BrowserAuthTransaction):
        raise AdmissionDenied("authorization transaction absent, malformed or already consumed")
    if transaction.transaction_id != transaction_id:
        raise AdmissionDenied("authorization transaction authority returned the wrong transaction")
    if not (_utc(transaction.created_at) <= now < _utc(transaction.expires_at)):
        raise AdmissionDenied("authorization transaction is not current")
    if not hmac.compare_digest(transaction.initiating_session_digest, _digest(initiating_session_binding)):
        raise AdmissionDenied("authorization transaction belongs to another browser session")
    if not hmac.compare_digest(transaction.state_digest, _digest(returned_state)):
        raise AdmissionDenied("OIDC state mismatch")

    verified = oidc_port.exchange_and_verify(
        authorization_code=authorization_code,
        pkce_verifier=transaction.pkce_verifier,
        expected_issuer=transaction.expected_issuer,
        expected_client_id=transaction.expected_client_id,
        expected_redirect_uri=transaction.expected_redirect_uri,
    )
    if not isinstance(verified, VerifiedOidcIdentity):
        raise AdmissionDenied("OIDC verifier returned malformed trusted evidence")
    try:
        if verified.issuer != transaction.expected_issuer or verified.client_id != transaction.expected_client_id:
            raise AdmissionDenied("OIDC issuer/client binding mismatch")
        if not hmac.compare_digest(transaction.nonce_digest, _digest(verified.nonce)):
            raise AdmissionDenied("OIDC nonce mismatch")
        if not (_utc(verified.authenticated_at) <= now < _utc(verified.token_expires_at)):
            raise AdmissionDenied("OIDC identity evidence is not current")

        principal = Principal(
            principal_id=verified.principal_id,
            kind=PrincipalKind.HUMAN_BROWSER_SESSION,
            credential_generation=f"session:{transaction.transaction_id}",
        )
        strength = AuthenticationStrengthEvidence(
            issuer=verified.issuer,
            acr=verified.acr,
            amr=verified.amr,
            authenticated_at=verified.authenticated_at,
            evidence_expires_at=verified.token_expires_at,
            policy_version=verified.policy_version,
            principal_id=verified.principal_id,
            principal_credential_generation=principal.credential_generation,
        )
    except (AttributeError, TypeError, ValueError) as exc:
        raise AdmissionDenied("OIDC verifier evidence is not canonical") from exc
    return principal, strength


def require_authentication_strength(
    *,
    policy: AuthenticationStrengthPolicyPort,
    policy_id: str,
    evidence: AuthenticationStrengthEvidence | None,
    now: datetime,
    principal: Principal | None = None,
) -> None:
    if not isinstance(principal, Principal) or principal.active is not True:
        raise AdmissionDenied("current principal for authentication-strength evaluation is unavailable")
    if principal.kind not in {
        PrincipalKind.HUMAN_BROWSER_SESSION,
        PrincipalKind.PLATFORM_ADMIN_PRINCIPAL,
    }:
        raise AdmissionDenied("authentication-strength evidence cannot authorize a non-human principal")
    if evidence is None or not isinstance(evidence, AuthenticationStrengthEvidence):
        raise AdmissionDenied("current authentication-strength evidence cannot be proven")
    try:
        current = evidence.is_current(now)
    except (AttributeError, TypeError, ValueError) as exc:
        raise AdmissionDenied("authentication-strength evidence is malformed") from exc
    if not current:
        raise AdmissionDenied("current authentication-strength evidence cannot be proven")
    if evidence.principal_id != principal.principal_id:
        raise AdmissionDenied("authentication-strength evidence belongs to another principal")
    if evidence.principal_credential_generation != principal.credential_generation:
        raise AdmissionDenied("authentication-strength evidence belongs to another credential/session generation")
    if policy.permits(policy_id=policy_id, evidence=evidence, now=_utc(now)) is not True:
        raise AdmissionDenied("current authentication-strength policy is not satisfied")
