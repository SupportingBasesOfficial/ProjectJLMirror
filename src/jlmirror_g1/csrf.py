from __future__ import annotations

from dataclasses import dataclass
import base64
import hashlib
import hmac
import re
from typing import Mapping

_VERSION_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,31}$")
_LINEAGE_RE = re.compile(r"^[A-Za-z0-9_-]{16,128}$")


def _b64url(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


@dataclass(frozen=True, repr=False)
class CsrfKeyRing:
    current_version: str
    previous_version: str
    keys: Mapping[str, bytes]

    def __post_init__(self) -> None:
        for value, field in (
            (self.current_version, "current_version"),
            (self.previous_version, "previous_version"),
        ):
            if not isinstance(value, str) or not _VERSION_RE.fullmatch(value):
                raise ValueError(f"{field} must be a bounded canonical key version")
        if self.current_version == self.previous_version:
            raise ValueError("current and previous CSRF key versions must differ")
        if set(self.keys) != {self.current_version, self.previous_version}:
            raise ValueError("exactly current and previous CSRF keys must be active")
        for key in self.keys.values():
            if not isinstance(key, bytes) or len(key) < 32:
                raise ValueError("CSRF HMAC keys must contain at least 256 bits")

    def __repr__(self) -> str:
        return (
            "CsrfKeyRing("
            f"current_version={self.current_version!r}, "
            f"previous_version={self.previous_version!r}, keys=<redacted>)"
        )

    def issue(self, *, session_lineage_id: str) -> str:
        lineage = self._lineage(session_lineage_id)
        version = self.current_version
        mac = hmac.new(self.keys[version], lineage.encode("ascii"), hashlib.sha256).digest()
        return f"{version}.{_b64url(mac)}"

    def validate(self, *, token: str, session_lineage_id: str) -> bool:
        if not isinstance(token, str) or token.count(".") != 1:
            return False
        version, encoded_mac = token.split(".", 1)
        key = self.keys.get(version)
        if key is None:
            return False
        try:
            lineage = self._lineage(session_lineage_id)
        except ValueError:
            return False
        expected = _b64url(hmac.new(key, lineage.encode("ascii"), hashlib.sha256).digest())
        return hmac.compare_digest(encoded_mac, expected)

    @staticmethod
    def _lineage(value: str) -> str:
        if not isinstance(value, str) or not _LINEAGE_RE.fullmatch(value):
            raise ValueError("session_lineage_id must be an opaque bounded identifier")
        return value
