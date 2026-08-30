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


class CsrfKeyRing:
    """D3-C reference profile: exactly current + previous verification generations."""

    def __init__(self, *, authority: KeyAuthorityPort, current: int, previous: int | None):
        if current <= 0 or (previous is not None and previous <= 0):
            raise ValueError("key versions must be positive")
        if previous == current:
            raise ValueError("current and previous must differ")
        if authority.can_sign(key_version=current) is not True:
            raise ValueError("current CSRF generation must be sign-capable")
        if authority.can_verify(key_version=current) is not True:
            raise ValueError("current CSRF generation must be verify-capable")
        if previous is not None and authority.can_verify(key_version=previous) is not True:
            raise ValueError("previous CSRF generation must be verify-capable")
        self._authority = authority
        self.current = current
        self.previous = previous

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

    def verify(self, *, token: str, session_lineage_id: str) -> bool:
        try:
            parsed = CsrfToken.parse(token)
        except (ValueError, UnicodeError):
            return False
        allowed = {self.current}
        if self.previous is not None:
            allowed.add(self.previous)
        if parsed.key_version not in allowed:
            return False
        try:
            expected = self._authority.hmac_sha256(
                key_version=parsed.key_version,
                context=self._context(),
                message=self._message(session_lineage_id),
            )
        except ValueError:
            return False
        return hmac.compare_digest(parsed.mac, expected)


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
            self.continuity_generation += 1
            self._seen.clear()
            return self.continuity_generation
