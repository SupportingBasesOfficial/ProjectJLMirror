from __future__ import annotations

from dataclasses import dataclass

from .model import AdmissionDenied, EnvironmentClass


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

    def admit_environment(self, environment: EnvironmentClass) -> None:
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
