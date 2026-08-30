from __future__ import annotations

from dataclasses import dataclass
import base64
import hashlib
import hmac
import threading
from typing import Protocol


def _b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64url_decode(value: str) -> bytes:
    padding = "=" * ((4 - len(value) % 4) % 4)
    return base64.urlsafe_b64decode((value + padding).encode("ascii"))


def _canon(value: str, label: str) -> bytes:
    if not isinstance(value, str) or not value or value != value.strip():
        raise ValueError(f"{label} must be a non-empty canonical string")
    raw = value.encode("utf-8")
    if len(raw) > 512 or any(b < 0x20 or b == 0x7F for b in raw):
        raise ValueError(f"{label} outside bounded canonical envelope")
    return raw


def hkdf_expand_sha256(*, master_key: bytes, tenant_id: str, scope: str, erasure_unit: str) -> bytes:
    """Small deterministic reference for D3 domain-separation tests.

    Production code must consume KeyAuthorityPort and must not embed/export a master key.
    """
    if not isinstance(master_key, bytes) or len(master_key) < 32:
        raise ValueError("reference master key must be at least 256 bits")
    info = b"jlmirror-d3-equivalence-v1\x00" + b"\x00".join(
        (_canon(tenant_id, "tenant_id"), _canon(scope, "scope"), _canon(erasure_unit, "erasure_unit"))
    )
    prk = hmac.new(b"jlmirror-d3-hkdf-salt-v1", master_key, hashlib.sha256).digest()
    return hmac.new(prk, info + b"\x01", hashlib.sha256).digest()


class KeyAuthorityPort(Protocol):
    def hmac_sha256(self, *, key_version: int, context: bytes, message: bytes) -> bytes:
        ...

    def can_sign(self, *, key_version: int) -> bool:
        ...

    def can_verify(self, *, key_version: int) -> bool:
        ...


@dataclass(frozen=True)
class ReferenceKeyVersion:
    version: int
    material: bytes
    signing_enabled: bool
    verification_enabled: bool


class ReferenceKeyAuthority:
    """Evidence-only reference backend; never production authority."""

    def __init__(self, versions: list[ReferenceKeyVersion]):
        if not versions:
            raise ValueError("at least one key version is required")
        mapping = {v.version: v for v in versions}
        if len(mapping) != len(versions) or any(v <= 0 for v in mapping):
            raise ValueError("key versions must be unique positive integers")
        if any(len(v.material) < 32 for v in versions):
            raise ValueError("reference key material must be at least 256 bits")
        self._versions = mapping

    def can_sign(self, *, key_version: int) -> bool:
        item = self._versions.get(key_version)
        return item is not None and item.signing_enabled

    def can_verify(self, *, key_version: int) -> bool:
        item = self._versions.get(key_version)
        return item is not None and item.verification_enabled

    def hmac_sha256(self, *, key_version: int, context: bytes, message: bytes) -> bytes:
        item = self._versions.get(key_version)
        if item is None or not item.verification_enabled:
            raise ValueError("key version unavailable for verification")
        derived = hmac.new(item.material, b"context\x00" + context, hashlib.sha256).digest()
        return hmac.new(derived, message, hashlib.sha256).digest()


@dataclass(frozen=True)
class CsrfToken:
    key_version: int
    mac: bytes

    def encode(self) -> str:
        return f"v{self.key_version}.{_b64url(self.mac)}"

    @classmethod
    def parse(cls, encoded: str) -> "CsrfToken":
        if not isinstance(encoded, str) or not encoded.startswith("v") or encoded.count(".") != 1:
            raise ValueError("non-canonical CSRF token")
        version_part, mac_part = encoded.split(".", 1)
        if not version_part[1:].isdigit() or version_part[1:].startswith("0"):
            raise ValueError("non-canonical CSRF key version")
        mac = _b64url_decode(mac_part)
        if len(mac) != 32 or _b64url(mac) != mac_part:
            raise ValueError("non-canonical CSRF MAC")
        return cls(key_version=int(version_part[1:]), mac=mac)


@dataclass(frozen=True)
class CsrfRotationWindow:
    """Bounded non-production timing profile used only to falsify D3-C rotation safety."""

    rotation_started_at: int
    previous_valid_until: int
    minimum_safety_lifetime_seconds: int

    def __post_init__(self) -> None:
        for label, value in (
            ("rotation_started_at", self.rotation_started_at),
            ("previous_valid_until", self.previous_valid_until),
            ("minimum_safety_lifetime_seconds", self.minimum_safety_lifetime_seconds),
        ):
            if type(value) is not int:
                raise ValueError(f"{label} must be an integer")
        if self.rotation_started_at < 0:
            raise ValueError("rotation_started_at must be non-negative")
        if self.previous_valid_until < self.rotation_started_at:
            raise ValueError("previous_valid_until precedes rotation start")
        if self.minimum_safety_lifetime_seconds <= 0:
            raise ValueError("minimum safety lifetime must be positive")
        overlap = self.previous_valid_until - self.rotation_started_at
        if overlap < self.minimum_safety_lifetime_seconds:
            raise ValueError("previous-key overlap is shorter than the accepted safety lifetime")

    def previous_is_within_overlap(self, *, now_epoch_seconds: int) -> bool:
        if type(now_epoch_seconds) is not int or now_epoch_seconds < self.rotation_started_at:
            raise ValueError("verification time is outside the canonical rotation epoch")
        return now_epoch_seconds <= self.previous_valid_until


@dataclass(frozen=True)
class CsrfVerificationEvidence:
    accepted: bool
    presented_key_version: int | None
    presented_previous_generation: bool
    accepted_previous_generation: bool
    reason: str


def _canonicalize_csrf_presentation(*, cookie_values: list[str], header_values: list[str]) -> str:
    if not isinstance(cookie_values, list) or not isinstance(header_values, list):
        raise ValueError("CSRF presentation must use canonical value lists")
    if len(cookie_values) != 1 or len(header_values) != 1:
        raise ValueError("ambiguous CSRF presentation")
    cookie = _canon(cookie_values[0], "csrf_cookie").decode("utf-8")
    header = _canon(header_values[0], "csrf_header").decode("utf-8")
    if not hmac.compare_digest(cookie, header):
        raise ValueError("mismatched CSRF presentation")
    return cookie


def canonicalize_ingress_csrf(*, cookie_values: list[str], header_values: list[str]) -> str:
    """Canonical HTTP ingress boundary for the bounded D3-C evidence model."""
    return _canonicalize_csrf_presentation(cookie_values=cookie_values, header_values=header_values)


def canonicalize_bff_csrf(*, cookie_values: list[str], header_values: list[str]) -> str:
    """BFF boundary intentionally delegates to the identical canonicalization rule."""
    return _canonicalize_csrf_presentation(cookie_values=cookie_values, header_values=header_values)


class CsrfKeyRing:
    """D3-C reference profile: exactly current + previous verification generations."""

    def __init__(
        self,
        *,
        authority: KeyAuthorityPort,
        current: int,
        previous: int | None,
        rotation_window: CsrfRotationWindow | None = None,
    ):
        if current <= 0 or (previous is not None and previous <= 0):
            raise ValueError("key versions must be positive")
        if previous == current:
            raise ValueError("current and previous must differ")
        if previous is None and rotation_window is not None:
            raise ValueError("rotation window requires a previous generation")
        if authority.can_sign(key_version=current) is not True:
            raise ValueError("current CSRF generation must be sign-capable")
        if authority.can_verify(key_version=current) is not True:
            raise ValueError("current CSRF generation must be verify-capable")
        if previous is not None and authority.can_verify(key_version=previous) is not True:
            raise ValueError("previous CSRF generation must be verify-capable")
        self._authority = authority
        self.current = current
        self.previous = previous
        self.rotation_window = rotation_window

    @staticmethod
    def _context() -> bytes:
        return b"jlmirror-csrf-v1"

    @staticmethod
    def _message(session_lineage_id: str) -> bytes:
        return _canon(session_lineage_id, "session_lineage_id")

    def issue(self, *, session_lineage_id: str) -> str:
        mac = self._authority.hmac_sha256(
            key_version=self.current,
            context=self._context(),
            message=self._message(session_lineage_id),
        )
        return CsrfToken(self.current, mac).encode()

    def verify_with_evidence(
        self,
        *,
        token: str,
        session_lineage_id: str,
        now_epoch_seconds: int | None = None,
    ) -> CsrfVerificationEvidence:
        try:
            parsed = CsrfToken.parse(token)
        except (ValueError, UnicodeError):
            return CsrfVerificationEvidence(False, None, False, False, "malformed_token")

        presented_previous = self.previous is not None and parsed.key_version == self.previous
        allowed = {self.current}
        if self.previous is not None:
            allowed.add(self.previous)
        if parsed.key_version not in allowed:
            return CsrfVerificationEvidence(
                False,
                parsed.key_version,
                False,
                False,
                "generation_not_current_or_previous",
            )

        if presented_previous and self.rotation_window is not None:
            if now_epoch_seconds is None:
                return CsrfVerificationEvidence(
                    False,
                    parsed.key_version,
                    True,
                    False,
                    "previous_overlap_time_uncertain",
                )
            try:
                within_overlap = self.rotation_window.previous_is_within_overlap(
                    now_epoch_seconds=now_epoch_seconds
                )
            except ValueError:
                return CsrfVerificationEvidence(
                    False,
                    parsed.key_version,
                    True,
                    False,
                    "previous_overlap_time_invalid",
                )
            if not within_overlap:
                return CsrfVerificationEvidence(
                    False,
                    parsed.key_version,
                    True,
                    False,
                    "previous_overlap_expired",
                )

        try:
            expected = self._authority.hmac_sha256(
                key_version=parsed.key_version,
                context=self._context(),
                message=self._message(session_lineage_id),
            )
        except ValueError:
            return CsrfVerificationEvidence(
                False,
                parsed.key_version,
                presented_previous,
                False,
                "verification_key_unavailable",
            )

        accepted = hmac.compare_digest(parsed.mac, expected)
        if not accepted:
            return CsrfVerificationEvidence(
                False,
                parsed.key_version,
                presented_previous,
                False,
                "mac_mismatch",
            )
        return CsrfVerificationEvidence(
            True,
            parsed.key_version,
            presented_previous,
            presented_previous,
            "accepted_previous" if presented_previous else "accepted_current",
        )

    def verify(
        self,
        *,
        token: str,
        session_lineage_id: str,
        now_epoch_seconds: int | None = None,
    ) -> bool:
        return self.verify_with_evidence(
            token=token,
            session_lineage_id=session_lineage_id,
            now_epoch_seconds=now_epoch_seconds,
        ).accepted


class AtomicReplayLedger:
    """Reference single-winner replay authority for bounded D3-E concurrency tests."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._seen: set[tuple[str, str]] = set()
        self.available = True
        self.continuity_generation = 1

    def create_or_observe(self, *, client_principal: str, jti: str, expected_generation: int) -> bool:
        client = _canon(client_principal, "client_principal").decode("utf-8")
        token_id = _canon(jti, "jti").decode("utf-8")
        with self._lock:
            if not self.available:
                raise RuntimeError("replay authority unavailable")
            if expected_generation != self.continuity_generation:
                raise RuntimeError("replay continuity generation is not current")
            key = (client, token_id)
            if key in self._seen:
                return False
            self._seen.add(key)
            return True

    def retire_continuity(self) -> int:
        with self._lock:
            # Retiring a continuity generation fences stale callers; it must not erase
            # still-relevant consumed replay identities. Retention expiry is a separate
            # governed concern outside this bounded reference model.
            self.continuity_generation += 1
            return self.continuity_generation
