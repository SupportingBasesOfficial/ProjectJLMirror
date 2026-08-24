from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
import hashlib
import secrets
from typing import Protocol

from .model import (
    AdmissionDenied,
    AuthenticationStrengthEvidence,
    Principal,
    PrincipalKind,
)


def _utc(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("time must be a timezone-aware datetime")
    return value.astimezone(timezone.utc)


def _digest(handle: str) -> str:
    return hashlib.sha256(handle.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class BrowserSessionHandle:
    """Opaque browser capability. Raw value is transport-only and repr-redacted."""

    value: str

    def __post_init__(self) -> None:
        if not isinstance(self.value, str) or len(self.value) < 43:
            raise ValueError("browser session handle must be high-entropy and opaque")

    @property
    def digest(self) -> str:
        return _digest(self.value)

    def __repr__(self) -> str:
        return "BrowserSessionHandle(<redacted>)"


@dataclass(frozen=True)
class BrowserSessionRecord:
    handle_digest: str
    principal: Principal
    session_generation: str
    created_at: datetime
    expires_at: datetime
    retired: bool = False
    authentication_strength: AuthenticationStrengthEvidence | None = None

    def __post_init__(self) -> None:
        if len(self.handle_digest) != 64 or any(c not in "0123456789abcdef" for c in self.handle_digest):
            raise ValueError("session handle digest must be lowercase SHA-256 hex")
        if not isinstance(self.session_generation, str) or not self.session_generation:
            raise ValueError("session_generation is required")
        if type(self.retired) is not bool:
            raise ValueError("retired must be a boolean")
        if self.principal.kind not in {
            PrincipalKind.HUMAN_BROWSER_SESSION,
            PrincipalKind.PLATFORM_ADMIN_PRINCIPAL,
        }:
            raise ValueError("browser sessions require a human browser/admin principal")
        if self.principal.credential_generation != self.session_generation:
            raise ValueError("session principal generation must equal session generation")
        if self.authentication_strength is not None:
            if not isinstance(self.authentication_strength, AuthenticationStrengthEvidence):
                raise ValueError("authentication_strength must be typed trusted evidence")
            if self.authentication_strength.principal_id != self.principal.principal_id:
                raise ValueError("authentication-strength evidence must belong to the session principal")
            if (
                self.authentication_strength.principal_credential_generation
                != self.session_generation
            ):
                raise ValueError(
                    "authentication-strength evidence must belong to the exact session generation"
                )
        created = _utc(self.created_at)
        expires = _utc(self.expires_at)
        if expires <= created:
            raise ValueError("session expiry must follow creation")

    def is_current(self, now: datetime) -> bool:
        return (
            self.retired is False
            and self.principal.active is True
            and _utc(self.created_at) <= _utc(now) < _utc(self.expires_at)
        )


class SessionAuthorityPort(Protocol):
    def create(self, record: BrowserSessionRecord) -> bool:
        """Atomically create one session record; only literal True means success."""

    def resolve(self, handle_digest: str) -> BrowserSessionRecord | None:
        """Resolve server-side authority by opaque-handle digest."""

    def rotate(
        self,
        *,
        predecessor_handle_digest: str,
        expected_predecessor_generation: str,
        successor: BrowserSessionRecord,
    ) -> bool:
        """Atomically retire predecessor and create successor; only literal True wins."""

    def retire(self, *, handle_digest: str, expected_generation: str) -> bool:
        """Atomically retire/revoke expected current generation; only literal True wins."""


def _new_handle() -> BrowserSessionHandle:
    return BrowserSessionHandle(secrets.token_urlsafe(48))


def _new_session_generation() -> str:
    # token_urlsafe may begin with '-' or '_', which are valid capability characters
    # but not valid first characters for canonical authority identifiers. Prefix the
    # random token rather than weakening the identifier grammar.
    return f"session-{secrets.token_urlsafe(24)}"


def _new_record(
    *,
    handle: BrowserSessionHandle,
    principal: Principal,
    now: datetime,
    lifetime: timedelta,
    authentication_strength: AuthenticationStrengthEvidence | None,
) -> BrowserSessionRecord:
    now = _utc(now)
    if not isinstance(lifetime, timedelta) or lifetime <= timedelta(0):
        raise ValueError("session lifetime must be a positive timedelta")
    if principal.kind not in {
        PrincipalKind.HUMAN_BROWSER_SESSION,
        PrincipalKind.PLATFORM_ADMIN_PRINCIPAL,
    }:
        raise AdmissionDenied("non-human principal cannot be converted into a browser session")
    if authentication_strength is not None:
        if not isinstance(authentication_strength, AuthenticationStrengthEvidence):
            raise AdmissionDenied("session authentication-strength evidence is malformed")
        if authentication_strength.principal_id != principal.principal_id:
            raise AdmissionDenied("session authentication-strength evidence belongs to another principal")
        if (
            authentication_strength.principal_credential_generation
            != principal.credential_generation
        ):
            raise AdmissionDenied(
                "session authentication-strength evidence belongs to another credential/session generation"
            )

    session_generation = _new_session_generation()
    session_principal = Principal(
        principal_id=principal.principal_id,
        kind=principal.kind,
        credential_generation=session_generation,
        active=principal.active,
    )
    rebound_strength = (
        replace(
            authentication_strength,
            principal_credential_generation=session_generation,
        )
        if authentication_strength is not None
        else None
    )
    return BrowserSessionRecord(
        handle_digest=handle.digest,
        principal=session_principal,
        session_generation=session_generation,
        created_at=now,
        expires_at=now + lifetime,
        authentication_strength=rebound_strength,
    )


def issue_browser_session(
    *,
    authority: SessionAuthorityPort,
    principal: Principal,
    now: datetime,
    lifetime: timedelta,
    authentication_strength: AuthenticationStrengthEvidence | None = None,
) -> BrowserSessionHandle:
    """Create a server-side session; collisions fail after bounded retries."""

    for _ in range(3):
        handle = _new_handle()
        record = _new_record(
            handle=handle,
            principal=principal,
            now=now,
            lifetime=lifetime,
            authentication_strength=authentication_strength,
        )
        if authority.create(record) is True:
            return handle
    raise AdmissionDenied("cannot establish unique server-side browser session authority")


def resolve_browser_session(
    *, authority: SessionAuthorityPort, handle: BrowserSessionHandle, now: datetime
) -> BrowserSessionRecord:
    record = authority.resolve(handle.digest)
    if not isinstance(record, BrowserSessionRecord) or record.handle_digest != handle.digest:
        raise AdmissionDenied("browser session is absent, unknown or malformed")
    if not record.is_current(now):
        raise AdmissionDenied("browser session is expired, retired or not current")
    return record


def rotate_browser_session(
    *,
    authority: SessionAuthorityPort,
    predecessor: BrowserSessionHandle,
    now: datetime,
    lifetime: timedelta,
    authentication_strength: AuthenticationStrengthEvidence | None = None,
    reauthenticated_principal: Principal | None = None,
) -> BrowserSessionHandle:
    """Atomically replace a session, optionally after same-subject reauthentication/step-up."""

    current = resolve_browser_session(authority=authority, handle=predecessor, now=now)
    source_principal = current.principal
    source_strength = (
        authentication_strength
        if authentication_strength is not None
        else current.authentication_strength
    )

    if reauthenticated_principal is not None:
        if not isinstance(reauthenticated_principal, Principal) or reauthenticated_principal.active is not True:
            raise AdmissionDenied("reauthenticated principal is malformed or retired")
        if (
            reauthenticated_principal.principal_id != current.principal.principal_id
            or reauthenticated_principal.kind is not current.principal.kind
        ):
            raise AdmissionDenied("reauthentication cannot replace the session with another principal")
        source_principal = reauthenticated_principal
        # A new authentication boundary must not inherit old assurance implicitly.
        source_strength = authentication_strength
        if source_strength is not None:
            if source_strength.principal_id != source_principal.principal_id:
                raise AdmissionDenied("fresh authentication-strength evidence belongs to another principal")
            if (
                source_strength.principal_credential_generation
                != source_principal.credential_generation
            ):
                raise AdmissionDenied(
                    "fresh authentication-strength evidence is not bound to the reauthenticated credential generation"
                )

    successor_handle = _new_handle()
    successor = _new_record(
        handle=successor_handle,
        principal=source_principal,
        now=now,
        lifetime=lifetime,
        authentication_strength=source_strength,
    )
    if authority.rotate(
        predecessor_handle_digest=predecessor.digest,
        expected_predecessor_generation=current.session_generation,
        successor=successor,
    ) is not True:
        raise AdmissionDenied("browser session rotation lost current-authority race")
    return successor_handle


def retire_browser_session(
    *, authority: SessionAuthorityPort, handle: BrowserSessionHandle, now: datetime
) -> None:
    current = resolve_browser_session(authority=authority, handle=handle, now=now)
    if authority.retire(
        handle_digest=handle.digest,
        expected_generation=current.session_generation,
    ) is not True:
        raise AdmissionDenied("browser session retirement lost current-authority race")