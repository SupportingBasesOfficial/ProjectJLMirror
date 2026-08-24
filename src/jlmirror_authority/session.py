from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import secrets
from typing import Protocol

from .model import AdmissionDenied, AuthenticationStrengthEvidence, Principal


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("time must be timezone-aware")
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
        if not self.session_generation:
            raise ValueError("session_generation is required")
        created = _utc(self.created_at)
        expires = _utc(self.expires_at)
        if expires <= created:
            raise ValueError("session expiry must follow creation")

    def is_current(self, now: datetime) -> bool:
        return (
            not self.retired
            and self.principal.active
            and _utc(self.created_at) <= _utc(now) < _utc(self.expires_at)
        )


class SessionAuthorityPort(Protocol):
    def create(self, record: BrowserSessionRecord) -> bool:
        """Atomically create one session record; False means collision/conflict."""

    def resolve(self, handle_digest: str) -> BrowserSessionRecord | None:
        """Resolve server-side authority by opaque-handle digest."""

    def rotate(
        self,
        *,
        predecessor_handle_digest: str,
        expected_predecessor_generation: str,
        successor: BrowserSessionRecord,
    ) -> bool:
        """Atomically retire predecessor and create successor, or fail closed."""

    def retire(self, *, handle_digest: str, expected_generation: str) -> bool:
        """Atomically retire/revoke the expected current session generation."""


def _new_handle() -> BrowserSessionHandle:
    return BrowserSessionHandle(secrets.token_urlsafe(48))


def _new_record(
    *,
    handle: BrowserSessionHandle,
    principal: Principal,
    now: datetime,
    lifetime: timedelta,
    authentication_strength: AuthenticationStrengthEvidence | None,
) -> BrowserSessionRecord:
    now = _utc(now)
    if lifetime <= timedelta(0):
        raise ValueError("session lifetime must be positive")
    return BrowserSessionRecord(
        handle_digest=handle.digest,
        principal=principal,
        session_generation=secrets.token_urlsafe(24),
        created_at=now,
        expires_at=now + lifetime,
        authentication_strength=authentication_strength,
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
        if authority.create(record):
            return handle
    raise AdmissionDenied("cannot establish unique server-side browser session authority")


def resolve_browser_session(
    *, authority: SessionAuthorityPort, handle: BrowserSessionHandle, now: datetime
) -> BrowserSessionRecord:
    record = authority.resolve(handle.digest)
    if record is None or record.handle_digest != handle.digest:
        raise AdmissionDenied("browser session is absent or unknown")
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
) -> BrowserSessionHandle:
    current = resolve_browser_session(authority=authority, handle=predecessor, now=now)
    successor_handle = _new_handle()
    successor = _new_record(
        handle=successor_handle,
        principal=current.principal,
        now=now,
        lifetime=lifetime,
        authentication_strength=(
            authentication_strength
            if authentication_strength is not None
            else current.authentication_strength
        ),
    )
    if not authority.rotate(
        predecessor_handle_digest=predecessor.digest,
        expected_predecessor_generation=current.session_generation,
        successor=successor,
    ):
        raise AdmissionDenied("browser session rotation lost current-authority race")
    return successor_handle


def retire_browser_session(
    *, authority: SessionAuthorityPort, handle: BrowserSessionHandle, now: datetime
) -> None:
    current = resolve_browser_session(authority=authority, handle=handle, now=now)
    if not authority.retire(
        handle_digest=handle.digest,
        expected_generation=current.session_generation,
    ):
        raise AdmissionDenied("browser session retirement lost current-authority race")
