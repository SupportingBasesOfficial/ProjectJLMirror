from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping, TypeAlias

from .model import SecretReference

JsonScalar: TypeAlias = str | int | float | bool | None


@dataclass(frozen=True)
class ConfigurationSnapshot:
    configuration_generation: str
    public_values: Mapping[str, JsonScalar]
    secret_references: Mapping[str, SecretReference]

    def __post_init__(self) -> None:
        if not self.configuration_generation:
            raise ValueError("configuration_generation is required")
        overlap = set(self.public_values) & set(self.secret_references)
        if overlap:
            raise ValueError(
                f"configuration keys cannot be both public values and secret references: {sorted(overlap)}"
            )
        for key in [*self.public_values, *self.secret_references]:
            if not isinstance(key, str) or not key or key.startswith("_"):
                raise ValueError("configuration keys must be explicit non-private names")
        object.__setattr__(self, "public_values", MappingProxyType(dict(self.public_values)))
        object.__setattr__(self, "secret_references", MappingProxyType(dict(self.secret_references)))

    def evidence_view(self) -> dict[str, object]:
        """Safe structural evidence: no secret value exists in this model."""
        return {
            "configuration_generation": self.configuration_generation,
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
