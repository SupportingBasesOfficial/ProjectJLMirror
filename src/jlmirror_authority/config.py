from __future__ import annotations

from dataclasses import dataclass
import math
import re
from types import MappingProxyType
from typing import Mapping, Protocol, TypeAlias

from .model import AdmissionDenied, EnvironmentClass, SecretReference

JsonScalar: TypeAlias = str | int | float | bool | None
_SECRETREF_RE = re.compile(r"^secretref\.[a-z0-9-]+(?:\.[a-z0-9-]+)*@[1-9][0-9]*$")
_RUNTIME_PROFILE_RE = re.compile(r"^runtime\.[a-z0-9-]+(?:\.[a-z0-9-]+)*@[1-9][0-9]*$")


def _explicit_name(value: object, field: str) -> str:
    if (
        not isinstance(value, str)
        or not value
        or value != value.strip()
        or any(ord(char) < 0x20 or ord(char) == 0x7F for char in value)
    ):
        raise ValueError(f"{field} must be an explicit canonical string")
    return value


def _json_scalar(value: object, field: str) -> JsonScalar:
    if value is None or type(value) in {str, int, bool}:
        return value  # type: ignore[return-value]
    if type(value) is float and math.isfinite(value):
        return value
    raise ValueError(f"{field} must be a finite JSON scalar")


@dataclass(frozen=True)
class ConfigurationSchema:
    """Structural key classification supplied by the Security/configuration boundary.

    Presence of this object proves only that a snapshot is structurally classified.
    It does not prove the classification is current, trusted for a runtime/environment,
    or owned by the accepted configuration authority.
    """

    public_keys: frozenset[str]
    secret_reference_classes: Mapping[str, frozenset[str]]

    def __post_init__(self) -> None:
        if isinstance(self.public_keys, (str, bytes)):
            raise ValueError("public_keys must be a collection of explicit keys")
        if not isinstance(self.secret_reference_classes, Mapping):
            raise ValueError("secret_reference_classes must be a mapping")
        try:
            public_keys = frozenset(self.public_keys)
        except TypeError as exc:
            raise ValueError("public_keys must be an iterable of strings") from exc

        secret_classes: dict[str, frozenset[str]] = {}
        for key, classes in self.secret_reference_classes.items():
            _explicit_name(key, "configuration schema key")
            if isinstance(classes, (str, bytes)):
                raise ValueError(f"secret-reference classes for {key!r} must be a collection")
            try:
                normalized = frozenset(classes)
            except TypeError as exc:
                raise ValueError(f"secret-reference classes for {key!r} are malformed") from exc
            secret_classes[key] = normalized

        overlap = public_keys & set(secret_classes)
        if overlap:
            raise ValueError(f"configuration schema class overlap: {sorted(overlap)}")
        for key in public_keys:
            _explicit_name(key, "configuration schema key")
            if key.startswith("_"):
                raise ValueError("configuration schema keys must be explicit non-private names")
        for key, classes in secret_classes.items():
            if key.startswith("_"):
                raise ValueError("configuration schema keys must be explicit non-private names")
            if not classes:
                raise ValueError(f"secret-classified key has no allowed reference class: {key}")
            if any(not isinstance(item, str) or not _SECRETREF_RE.fullmatch(item) for item in classes):
                raise ValueError(f"invalid secret-reference class for key: {key}")
        object.__setattr__(self, "public_keys", public_keys)
        object.__setattr__(self, "secret_reference_classes", MappingProxyType(secret_classes))


@dataclass(frozen=True)
class ConfigurationSnapshot:
    configuration_generation: str
    public_values: Mapping[str, JsonScalar]
    secret_references: Mapping[str, SecretReference]
    schema: ConfigurationSchema | None = None

    def __post_init__(self) -> None:
        _explicit_name(self.configuration_generation, "configuration_generation")
        if not isinstance(self.public_values, Mapping):
            raise ValueError("public_values must be a mapping")
        if not isinstance(self.secret_references, Mapping):
            raise ValueError("secret_references must be a mapping")
        if self.schema is not None and not isinstance(self.schema, ConfigurationSchema):
            raise ValueError("schema must be a ConfigurationSchema")

        public_values = dict(self.public_values)
        secret_references = dict(self.secret_references)
        overlap = set(public_values) & set(secret_references)
        if overlap:
            raise ValueError(
                f"configuration keys cannot be both public values and secret references: {sorted(overlap)}"
            )
        for key, value in public_values.items():
            _explicit_name(key, "configuration key")
            if key.startswith("_"):
                raise ValueError("configuration keys must be explicit non-private names")
            _json_scalar(value, f"public configuration value {key!r}")
        for key, reference in secret_references.items():
            _explicit_name(key, "configuration key")
            if key.startswith("_"):
                raise ValueError("configuration keys must be explicit non-private names")
            if not isinstance(reference, SecretReference):
                raise ValueError(f"secret reference {key!r} must be a typed SecretReference")

        if self.schema is not None:
            unknown_public = set(public_values) - self.schema.public_keys
            if unknown_public:
                raise ValueError(
                    f"unclassified/secret-capable public configuration keys: {sorted(unknown_public)}"
                )
            unknown_secret = set(secret_references) - set(self.schema.secret_reference_classes)
            if unknown_secret:
                raise ValueError(f"unclassified secret-reference keys: {sorted(unknown_secret)}")
            for key, reference in secret_references.items():
                allowed = self.schema.secret_reference_classes[key]
                if reference.reference_class not in allowed:
                    raise ValueError(
                        f"secret reference class {reference.reference_class!r} is not allowed for {key!r}"
                    )

        object.__setattr__(self, "public_values", MappingProxyType(public_values))
        object.__setattr__(self, "secret_references", MappingProxyType(secret_references))

    @property
    def classification_schema_present(self) -> bool:
        return self.schema is not None

    def evidence_view(self) -> dict[str, object]:
        """Structural evidence only; never claims current classification authority."""
        return {
            "configuration_generation": self.configuration_generation,
            "classification_schema_present": self.classification_schema_present,
            "public_keys": sorted(self.public_values),
            "secret_reference_classes": {
                key: reference.reference_class
                for key, reference in sorted(self.secret_references.items())
            },
            "secret_reference_generations": {
                key: reference.generation
                for key, reference in sorted(self.secret_references.items())
            },
        }


class ConfigurationAuthorityPort(Protocol):
    def admit_current(
        self,
        *,
        snapshot: ConfigurationSnapshot,
        runtime_profile_id: str,
        environment_class: EnvironmentClass,
        expected_configuration_generation: str,
    ) -> bool:
        """Confirm current Security/config authority for this exact runtime/environment snapshot."""


def require_classified_configuration(
    snapshot: ConfigurationSnapshot,
    *,
    authority: ConfigurationAuthorityPort | None = None,
    runtime_profile_id: str | None = None,
    environment_class: EnvironmentClass | None = None,
    expected_configuration_generation: str | None = None,
) -> ConfigurationSnapshot:
    """Admit configuration only with structural classification plus current owning authority."""

    if not isinstance(snapshot, ConfigurationSnapshot):
        raise AdmissionDenied("runtime configuration evidence is malformed")
    if not snapshot.classification_schema_present:
        raise AdmissionDenied("configuration key classification schema is absent")
    if (
        not isinstance(runtime_profile_id, str)
        or not _RUNTIME_PROFILE_RE.fullmatch(runtime_profile_id)
    ):
        raise AdmissionDenied("runtime profile for configuration admission is unavailable or non-canonical")
    if not isinstance(environment_class, EnvironmentClass):
        raise AdmissionDenied("environment class for configuration admission is unavailable or non-canonical")
    try:
        expected_generation = _explicit_name(
            expected_configuration_generation, "expected_configuration_generation"
        )
    except ValueError as exc:
        raise AdmissionDenied("current configuration generation authority is unavailable") from exc
    if snapshot.configuration_generation != expected_generation:
        raise AdmissionDenied("configuration snapshot generation is stale or unexpected")
    if authority is None:
        raise AdmissionDenied("current configuration classification authority is unavailable")
    try:
        admitted = authority.admit_current(
            snapshot=snapshot,
            runtime_profile_id=runtime_profile_id,
            environment_class=environment_class,
            expected_configuration_generation=expected_generation,
        )
    except Exception as exc:
        raise AdmissionDenied("current configuration classification authority failed closed") from exc
    if admitted is not True:
        raise AdmissionDenied("configuration classification/currentness is not proven by owning authority")
    return snapshot
