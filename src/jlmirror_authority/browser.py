from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import base64
import hashlib
import hmac
import secrets
from typing import Protocol

from .model import AdmissionDenied, AuthenticationStrengthEvidence, Principal, PrincipalKind


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("time must be timezone-aware")
    return value.astimezone(timezone.utc)


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _b64url_sha256(value: str) -> str:
    digest = hashlib.sha256(value.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


@dataclass(frozen=True)
class BrowserAuthTransaction:
    transaction_id: str
    initiating_session_digest: str
    state_digest: str
    nonce: str
    pkce_verifier: str
    created_at: datetime
    expires_at: datetime


@dataclass(frozen=True)
class BrowserAuthInitiation:
    transaction: BrowserAuthTransaction
    state: str
    pkce_challenge: str


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
        """Evaluate current Security-owned assurance policy."""


def begin_browser_auth(
    *, session_binding: str, now: datetime, lifetime: timedelta = timedelta(minutes=5)
) -> BrowserAuthInitiation:
    now = _utc(now)
    if not session_binding:
        raise ValueError("session_binding is required")
    if lifetime <= timedelta(0):
        raise ValueError("lifetime must be positive")

    state = secrets.token_urlsafe(32)
    nonce = secrets.token_urlsafe(32)
    verifier = secrets.token_urlsafe(48)
    if not 43 <= len(verifier) <= 128:
        raise RuntimeError("generated PKCE verifier outside RFC 7636 length envelope")

    transaction = BrowserAuthTransaction(
        transaction_id=secrets.token_urlsafe(24),
        initiating_session_digest=_digest(session_binding),
        state_digest=_digest(state),
        nonce=nonce,
        pkce_verifier=verifier,
        created_at=now,
        expires_at=now + lifetime,
    )
    return BrowserAuthInitiation(
        transaction=transaction,
        state=state,
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
    expected_issuer: str,
    expected_client_id: str,
    expected_redirect_uri: str,
    now: datetime,
) -> tuple[Principal, AuthenticationStrengthEvidence]:
    now = _utc(now)
    transaction = transaction_authority.consume(transaction_id)
    if transaction is None:
        raise AdmissionDenied("authorization transaction absent, expired or already consumed")
    if now >= _utc(transaction.expires_at):
        raise AdmissionDenied("authorization transaction expired")
    if not hmac.compare_digest(transaction.initiating_session_digest, _digest(initiating_session_binding)):
        raise AdmissionDenied("authorization transaction belongs to another browser session")
    if not hmac.compare_digest(transaction.state_digest, _digest(returned_state)):
        raise AdmissionDenied("OIDC state mismatch")

    verified = oidc_port.exchange_and_verify(
        authorization_code=authorization_code,
        pkce_verifier=transaction.pkce_verifier,
        expected_issuer=expected_issuer,
        expected_client_id=expected_client_id,
        expected_redirect_uri=expected_redirect_uri,
    )
    if verified.issuer != expected_issuer or verified.client_id != expected_client_id:
        raise AdmissionDenied("OIDC issuer/client binding mismatch")
    if not hmac.compare_digest(verified.nonce, transaction.nonce):
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
    )
    return principal, strength


def require_authentication_strength(
    *,
    policy: AuthenticationStrengthPolicyPort,
    policy_id: str,
    evidence: AuthenticationStrengthEvidence | None,
    now: datetime,
) -> None:
    if evidence is None or not evidence.is_current(now):
        raise AdmissionDenied("current authentication-strength evidence cannot be proven")
    if not policy.permits(policy_id=policy_id, evidence=evidence, now=_utc(now)):
        raise AdmissionDenied("current authentication-strength policy is not satisfied")
