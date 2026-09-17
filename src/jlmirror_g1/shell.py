from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Protocol

from jlmirror_authority.browser import (
    BrowserAuthInitiation,
    BrowserAuthTransaction,
    OidcVerificationPort,
    begin_browser_auth,
    complete_browser_auth,
)
from jlmirror_authority.model import AdmissionDenied, Principal
from jlmirror_authority.session import (
    BrowserSessionHandle,
    SessionAuthorityPort,
    issue_browser_session,
    resolve_browser_session,
    retire_browser_session,
)


@dataclass(frozen=True)
class TenantShellAdmission:
    tenant_id: str
    admission_revision: str

    def __post_init__(self) -> None:
        for field in ("tenant_id", "admission_revision"):
            value = getattr(self, field)
            if not isinstance(value, str) or not value or value != value.strip():
                raise ValueError(f"{field} must be a canonical current-authority binding")


@dataclass(frozen=True)
class ProtectedShellView:
    tenant_id: str
    principal_id: str
    admission_revision: str
    state: str = "ready"


@dataclass(frozen=True, repr=False)
class LoginStart:
    transaction_id: str
    state: str
    nonce: str
    pkce_challenge: str

    def __repr__(self) -> str:
        return (
            "LoginStart("
            f"transaction_id={self.transaction_id!r}, state=<redacted>, "
            "nonce=<redacted>, pkce_challenge=<redacted>)"
        )


class BrowserTransactionStorePort(Protocol):
    def create(self, transaction: BrowserAuthTransaction) -> bool: ...

    def consume(self, transaction_id: str) -> BrowserAuthTransaction | None: ...


class CurrentTenantAdmissionPort(Protocol):
    def require_current(
        self,
        *,
        principal: Principal,
        tenant_id: str,
        now: datetime,
    ) -> TenantShellAdmission: ...


class IdentityTenantShell:
    def __init__(
        self,
        *,
        transactions: BrowserTransactionStorePort,
        oidc: OidcVerificationPort,
        sessions: SessionAuthorityPort,
        tenant_admission: CurrentTenantAdmissionPort,
        issuer: str,
        client_id: str,
        redirect_uri: str,
        authorization_transaction_lifetime: timedelta,
        session_lifetime: timedelta,
    ) -> None:
        self._transactions = transactions
        self._oidc = oidc
        self._sessions = sessions
        self._tenant_admission = tenant_admission
        self._issuer = issuer
        self._client_id = client_id
        self._redirect_uri = redirect_uri
        self._authorization_transaction_lifetime = authorization_transaction_lifetime
        self._session_lifetime = session_lifetime

    def begin_login(self, *, browser_binding: str, now: datetime) -> LoginStart:
        initiation: BrowserAuthInitiation = begin_browser_auth(
            session_binding=browser_binding,
            expected_issuer=self._issuer,
            expected_client_id=self._client_id,
            expected_redirect_uri=self._redirect_uri,
            now=now,
            lifetime=self._authorization_transaction_lifetime,
        )
        if self._transactions.create(initiation.transaction) is not True:
            raise AdmissionDenied("browser authorization transaction could not be persisted")
        return LoginStart(
            transaction_id=initiation.transaction.transaction_id,
            state=initiation.state,
            nonce=initiation.nonce,
            pkce_challenge=initiation.pkce_challenge,
        )

    def finish_login(
        self,
        *,
        transaction_id: str,
        browser_binding: str,
        returned_state: str,
        authorization_code: str,
        now: datetime,
    ) -> BrowserSessionHandle:
        principal, strength = complete_browser_auth(
            transaction_authority=self._transactions,
            oidc_port=self._oidc,
            transaction_id=transaction_id,
            initiating_session_binding=browser_binding,
            returned_state=returned_state,
            authorization_code=authorization_code,
            now=now,
        )
        return issue_browser_session(
            authority=self._sessions,
            principal=principal,
            authentication_strength=strength,
            now=now,
            lifetime=self._session_lifetime,
        )

    def open_shell(
        self,
        *,
        session_capability: str,
        tenant_id: str,
        now: datetime,
    ) -> ProtectedShellView:
        try:
            handle = BrowserSessionHandle(session_capability)
        except ValueError as exc:
            raise AdmissionDenied("browser session capability is malformed") from exc
        record = resolve_browser_session(authority=self._sessions, handle=handle, now=now)
        admission = self._tenant_admission.require_current(
            principal=record.principal,
            tenant_id=tenant_id,
            now=now,
        )
        if not isinstance(admission, TenantShellAdmission):
            raise AdmissionDenied("tenant admission authority returned malformed evidence")
        if admission.tenant_id != tenant_id:
            raise AdmissionDenied("tenant admission evidence belongs to another tenant")
        if record.principal.active is not True:
            raise AdmissionDenied("browser principal is no longer active")
        return ProtectedShellView(
            tenant_id=admission.tenant_id,
            principal_id=record.principal.principal_id,
            admission_revision=admission.admission_revision,
        )

    def logout(self, *, session_capability: str, now: datetime) -> None:
        try:
            handle = BrowserSessionHandle(session_capability)
        except ValueError as exc:
            raise AdmissionDenied("browser session capability is malformed") from exc
        retire_browser_session(authority=self._sessions, handle=handle, now=now)
