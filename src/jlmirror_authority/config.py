from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping, TypeAlias

from .model import AdmissionDenied, SecretReference

JsonScalar: TypeAlias = str | int | float | bool | None


@dataclass(frozen=True)
class ConfigurationSchema:
    """Security-owned classification of configuration keys, not vendor config syntax."""

    public_keys: frozenset[str]
    secret_reference_classes: Mapping[str, frozenset[str]]

    def __post_init__(self) -> None:
        public_keys = frozenset(self.public_keys)
        secret_classes = {
            key: frozenset(classes) for key, classes in self.secret_reference_classes.items()
        }
        overlap = public_keys & set(secret_classes)
        if overlap:
            raise ValueError(f"configuration schema class overlap: {sorted(overlap)}")
        for key in [*public_keys, *secret_classes]:
            if not isinstance(key, str) or not key or key.startswith("_"):
                raise ValueError("configuration schema keys must be explicit non-private names")
        for key, classes in secret_classes.items():
            if not classes:
                raise ValueError(f"secret-classified key has no allowed reference class: {key}")
            if any(not item.startswith("secretref.") or "@" not in item for item in classes):
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
        if not self.configuration_generation:
            raise ValueError("configuration_generation is required")
        public_values = dict(self.public_values)
        secret_references = dict(self.secret_references)
        overlap = set(public_values) & set(secret_references)
        if overlap:
            raise ValueError(
                f"configuration keys cannot be both public values and secret references: {sorted(overlap)}"
            )
        for key in [*public_values, *secret_references]:
            if not isinstance(key, str) or not key or key.startswith("_"):
                raise ValueError("configuration keys must be explicit non-private names")

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
    def classification_proven(self) -> bool:
        return self.schema is not None

    def evidence_view(self) -> dict[str, object]:
        """Structural evidence; explicitly states whether key classification is proven."""
        return {
            "configuration_generation": self.configuration_generation,
            "classification_proven": self.classification_proven,
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


def require_classified_configuration(snapshot: ConfigurationSnapshot) -> ConfigurationSnapshot:
    """Protected runtime consumers must never admit unclassified configuration."""

    if not snapshot.classification_proven:
        raise AdmissionDenied("configuration key classification is unproven")
    return snapshot
