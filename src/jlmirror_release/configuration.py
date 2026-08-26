from __future__ import annotations

from dataclasses import dataclass

from .model import ReleaseError, TargetConfiguration


@dataclass(frozen=True)
class ConfigurationValidationEvidence:
    validation_configuration: TargetConfiguration
    target_configuration: TargetConfiguration
    semantic_equivalence_proven: bool
    target_specific_validation_proven: bool
    copied_secret_values_used_as_equivalence: bool = False


def require_validation_for_target(evidence: ConfigurationValidationEvidence) -> None:
    if evidence.copied_secret_values_used_as_equivalence:
        raise ReleaseError("production secret values cannot be copied to prove configuration equivalence")
    same = evidence.validation_configuration == evidence.target_configuration
    if same:
        return
    if not (evidence.semantic_equivalence_proven or evidence.target_specific_validation_proven):
        raise ReleaseError(
            "different target configuration requires semantic equivalence evidence "
            "or target-specific validation"
        )
