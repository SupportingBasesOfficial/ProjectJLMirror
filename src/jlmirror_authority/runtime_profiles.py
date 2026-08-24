from __future__ import annotations

from dataclasses import dataclass
import re

from .model import AdmissionDenied, EnvironmentClass

_PROFILE_ID_RE = re.compile(r"^[a-z][a-z0-9-]*(?:\.[a-z0-9-]+)+@[1-9][0-9]*$")


def _profile_id(value: object, field: str) -> str:
    if not isinstance(value, str) or not _PROFILE_ID_RE.fullmatch(value):
        raise ValueError(f"{field} must be a canonical versioned profile id")
    return value


@dataclass(frozen=True)
class RuntimeBinding:
    runtime_profile_id: str
    principal_class: str
    lifecycle_class: str
    isolation_class: str
    ingress_profile: str
    egress_profiles: frozenset[str]
    secret_reference_classes: frozenset[str]
    resource_profile: str
    allowed_environment_classes: frozenset[EnvironmentClass]

    def __post_init__(self) -> None:
        for field in (
            "runtime_profile_id",
            "principal_class",
            "lifecycle_class",
            "isolation_class",
            "ingress_profile",
            "resource_profile",
        ):
            _profile_id(getattr(self, field), field)

        for field in ("egress_profiles", "secret_reference_classes"):
            value = getattr(self, field)
            if isinstance(value, (str, bytes)):
                raise ValueError(f"{field} must be an exact profile set")
            try:
                normalized = frozenset(value)
            except TypeError as exc:
                raise ValueError(f"{field} must be an exact profile set") from exc
            if not normalized or any(
                not isinstance(profile, str) or not _PROFILE_ID_RE.fullmatch(profile)
                for profile in normalized
            ):
                raise ValueError(f"{field} contains a non-canonical profile")
            object.__setattr__(self, field, normalized)

        environments = self.allowed_environment_classes
        if isinstance(environments, (str, bytes)):
            raise ValueError("allowed_environment_classes must be an exact environment set")
        try:
            normalized_environments = frozenset(environments)
        except TypeError as exc:
            raise ValueError("allowed_environment_classes must be an exact environment set") from exc
        if not normalized_environments or any(
            not isinstance(environment, EnvironmentClass)
            for environment in normalized_environments
        ):
            raise ValueError("allowed_environment_classes contains a non-canonical environment")
        object.__setattr__(self, "allowed_environment_classes", normalized_environments)

    def admit_environment(self, environment: EnvironmentClass) -> None:
        if not isinstance(environment, EnvironmentClass):
            raise AdmissionDenied("runtime environment authority is not canonical")
        if environment not in self.allowed_environment_classes:
            raise AdmissionDenied(
                f"{self.runtime_profile_id} is not allowed in {environment.value}"
            )


_SERVING_ENVIRONMENTS = frozenset(
    {EnvironmentClass.DEVELOPMENT, EnvironmentClass.VALIDATION, EnvironmentClass.PRODUCTION}
)

WEB_BFF = RuntimeBinding(
    runtime_profile_id="runtime.web-bff@1",
    principal_class="principal.web-bff@1",
    lifecycle_class="lifecycle.serving-replica@1",
    isolation_class="isolation.confidential-web@1",
    ingress_profile="ingress.public-browser@1",
    egress_profiles=frozenset({"egress.platform-bounded@1"}),
    secret_reference_classes=frozenset(
        {"secretref.web-session@1", "secretref.service-communication@1"}
    ),
    resource_profile="resource.web@1",
    allowed_environment_classes=_SERVING_ENVIRONMENTS,
)

API_AUTH_BOUNDARY = RuntimeBinding(
    runtime_profile_id="runtime.api@1",
    principal_class="principal.application-serving@1",
    lifecycle_class="lifecycle.serving-replica@1",
    isolation_class="isolation.application-serving@1",
    ingress_profile="ingress.authenticated-api@1",
    egress_profiles=frozenset({"egress.platform-bounded@1"}),
    secret_reference_classes=frozenset(
        {"secretref.state-port@1", "secretref.service-communication@1"}
    ),
    resource_profile="resource.api@1",
    allowed_environment_classes=_SERVING_ENVIRONMENTS,
)

CONTROL_PLANE = RuntimeBinding(
    runtime_profile_id="runtime.control-plane@1",
    principal_class="principal.control-plane@1",
    lifecycle_class="lifecycle.control-plane-serving@1",
    isolation_class="isolation.control-plane@1",
    ingress_profile="ingress.privileged-platform@1",
    egress_profiles=frozenset({"egress.platform-bounded@1"}),
    secret_reference_classes=frozenset(
        {"secretref.state-port@1", "secretref.service-communication@1"}
    ),
    resource_profile="resource.control-plane@1",
    allowed_environment_classes=_SERVING_ENVIRONMENTS,
)

WAVE1_RUNTIME_BINDINGS = (WEB_BFF, API_AUTH_BOUNDARY, CONTROL_PLANE)