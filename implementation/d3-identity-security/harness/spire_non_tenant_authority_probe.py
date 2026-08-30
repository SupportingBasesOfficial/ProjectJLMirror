#!/usr/bin/env python3
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import os
from pathlib import Path
import re
import subprocess

from jlmirror_authority.control_plane import (
    AuthorizationDecision,
    CrossTenantTargetBinding,
    PlacementEvidence,
    RuntimeExecutionEvidence,
    RuntimeLifecycle,
    authorize_protected_operation,
    construct_tenant_context,
)
from jlmirror_authority.model import (
    AdmissionDenied,
    AuditClass,
    AuthorizationDeclaration,
    EnvironmentClass,
    Principal,
    PrincipalKind,
    ScopeClass,
    StepUpClass,
    TenantContext,
    TenantRequirement,
)
from jlmirror_authority.runtime_profiles import API_AUTH_BOUNDARY, CONTROL_PLANE
from jlmirror_authority.workload import VerifiedWorkloadPeer, admit_workload_peer

WIRE_SPIFFE_ID = (
    "spiffe://validation.d3.jlmirror.invalid/"
    "environment/validation/v1/runtime/api/v1/workload-probe"
)
CANONICAL_SPIFFE_ID = (
    "spiffe://validation.d3.jlmirror.invalid/"
    "environment.validation@1/runtime.api@1/workload-probe"
)
TRUST_DOMAIN = "validation.d3.jlmirror.invalid"
TENANT_ID = "tenant-d3-non-authority"
OTHER_PRINCIPAL_ID = "spiffe://validation.d3.jlmirror.invalid/other-service"
_URI_RE = re.compile(r"URI:([^,\s]+)")


def _run(*args: str) -> str:
    proc = subprocess.run(
        args,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return proc.stdout.strip()


def _openssl_date(cert: Path, option: str) -> datetime:
    output = _run("openssl", "x509", "-in", str(cert), "-noout", option)
    _, value = output.split("=", 1)
    parsed = datetime.strptime(value, "%b %d %H:%M:%S %Y %Z")
    return parsed.replace(tzinfo=timezone.utc)


def _single_file(directory: Path, pattern: str, *, reject_suffix: str | None = None) -> Path:
    candidates = sorted(directory.glob(pattern))
    if reject_suffix is not None:
        candidates = [item for item in candidates if not item.name.endswith(reject_suffix)]
    if len(candidates) != 1:
        raise SystemExit(
            f"expected exactly one {pattern!r} evidence file in {directory}, got {len(candidates)}"
        )
    return candidates[0]


def _digest_id(prefix: str, path: Path) -> str:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return f"{prefix}:{digest}"


def _expect_denied(label: str, expected_fragment: str, call) -> None:
    try:
        call()
    except AdmissionDenied as exc:
        if expected_fragment not in str(exc):
            raise AssertionError(
                f"{label}: wrong denial reason: expected fragment={expected_fragment!r} actual={str(exc)!r}"
            ) from exc
        return
    raise AssertionError(f"{label}: protected operation was unexpectedly admitted")


class CurrentPrincipalAuthority:
    def __init__(self, expected: Principal) -> None:
        self.expected = expected
        self.calls = 0

    def is_current(self, *, principal: Principal, now: datetime) -> bool:
        self.calls += 1
        return principal == self.expected and principal.active is True and now.tzinfo is not None


class TrapPlacementAuthority:
    def __init__(self) -> None:
        self.calls = 0

    def resolve_current(self, tenant_id: str):
        self.calls += 1
        raise AssertionError("placement authority must not be consulted before TenantContext admission")

    def context_is_current(self, context: TenantContext) -> bool:
        self.calls += 1
        raise AssertionError("placement authority must not be consulted for rejected principal binding")


class TrapAuthorizationAuthority:
    def __init__(self) -> None:
        self.calls = 0

    def evaluate(self, **kwargs):
        self.calls += 1
        raise AssertionError("authorization authority must not be reached by pre-authorization denial")


class TrapFinalAdmissionAuthority:
    def __init__(self) -> None:
        self.calls = 0

    def finalize_current_admission(self, **kwargs):
        self.calls += 1
        raise AssertionError("final authority must not be reached by a denied operation")


class PlacementAuthority:
    def __init__(self, evidence: PlacementEvidence) -> None:
        self.evidence = evidence
        self.resolve_calls = 0
        self.current_calls = 0

    def resolve_current(self, tenant_id: str) -> PlacementEvidence | None:
        self.resolve_calls += 1
        return self.evidence if tenant_id == self.evidence.tenant_id else None

    def context_is_current(self, context: TenantContext) -> bool:
        self.current_calls += 1
        return context.tenant_id == self.evidence.tenant_id


class DenyingAuthorizationAuthority:
    def __init__(self) -> None:
        self.calls = 0

    def evaluate(self, *, principal, context, declaration) -> AuthorizationDecision:
        self.calls += 1
        return AuthorizationDecision(granted=False, current=True, policy_revision="policy-deny-1")


class CurrentControlPlaneRuntimeAuthority:
    def __init__(self) -> None:
        self.calls = 0

    def resolve_current_execution(self, *, now: datetime) -> RuntimeExecutionEvidence:
        self.calls += 1
        return RuntimeExecutionEvidence(
            runtime_profile_id=CONTROL_PLANE.runtime_profile_id,
            principal_class=CONTROL_PLANE.principal_class,
            isolation_class=CONTROL_PLANE.isolation_class,
            ingress_profile=CONTROL_PLANE.ingress_profile,
            runtime_generation="control-runtime-1",
            environment_class=EnvironmentClass.VALIDATION,
            runtime_lifecycle=RuntimeLifecycle.ACTIVE,
            current=True,
        )


def main() -> int:
    evidence_dir_raw = os.environ.get("SPIRE_EVIDENCE_DIR")
    if not evidence_dir_raw:
        raise SystemExit("SPIRE_EVIDENCE_DIR is required")
    evidence_dir = Path(evidence_dir_raw).resolve()
    if not evidence_dir.is_dir():
        raise SystemExit(f"SPIRE evidence directory does not exist: {evidence_dir}")

    cert = _single_file(evidence_dir, "svid.*.pem", reject_suffix=".key")
    bundle = _single_file(evidence_dir, "bundle.*.pem")

    san_text = _run("openssl", "x509", "-in", str(cert), "-noout", "-ext", "subjectAltName")
    wire_uris = _URI_RE.findall(san_text)
    if wire_uris != [WIRE_SPIFFE_ID]:
        raise SystemExit(f"unexpected SPIRE wire identity set: {wire_uris!r}")

    # Evidence-only narrow adapter: the accepted canonical logical classes are mapped from
    # exactly one reviewed SPIRE wire representation. No tenant/business identifier is
    # introduced or derived by this mapping.
    canonical_spiffe_id = CANONICAL_SPIFFE_ID
    not_before = _openssl_date(cert, "-startdate")
    not_after = _openssl_date(cert, "-enddate")
    now = datetime.now(timezone.utc)
    if not (not_before <= now < not_after):
        raise SystemExit("real SPIRE workload SVID is not current during authority-composition probe")

    bundle_generation = _digest_id("bundle", bundle)
    credential_generation = _digest_id("svid", cert)
    peer = VerifiedWorkloadPeer(
        spiffe_id=canonical_spiffe_id,
        certificate_not_before=not_before,
        certificate_not_after=not_after,
        trust_bundle_generation=bundle_generation,
        workload_credential_generation=credential_generation,
    )
    principal = admit_workload_peer(
        peer=peer,
        expected_trust_domain=TRUST_DOMAIN,
        expected_environment=EnvironmentClass.VALIDATION,
        allowed_runtime_profiles=frozenset({API_AUTH_BOUNDARY.runtime_profile_id}),
        current_trust_bundle_generation=bundle_generation,
        current_workload_credential_generation=credential_generation,
        current_max_certificate_lifetime=timedelta(seconds=45),
        now=now,
    )
    if principal.kind is not PrincipalKind.INTERNAL_SERVICE_PRINCIPAL:
        raise AssertionError("admitted SPIRE workload did not remain an internal service principal")
    if principal.principal_id != canonical_spiffe_id:
        raise AssertionError("workload adapter changed canonical principal identity")

    tenant_declaration = AuthorizationDeclaration(
        action="monitoring.host.read",
        scope=ScopeClass.TENANT,
        tenant_required=True,
        step_up=StepUpClass.NONE,
        audit_class=AuditClass.NORMAL,
    )
    principal_authority = CurrentPrincipalAuthority(principal)

    # Negative 1: current mTLS/workload principal alone is never tenant authority.
    trap_placement = TrapPlacementAuthority()
    trap_auth = TrapAuthorizationAuthority()
    trap_final = TrapFinalAdmissionAuthority()
    _expect_denied(
        "mtls_without_tenant_context",
        "requires trusted TenantContext",
        lambda: authorize_protected_operation(
            principal=principal,
            principal_authority=principal_authority,
            declaration=tenant_declaration,
            placement_authority=trap_placement,
            authorization_authority=trap_auth,
            context=None,
            now=now,
            final_admission_authority=trap_final,
        ),
    )
    if trap_placement.calls or trap_auth.calls or trap_final.calls:
        raise AssertionError("mTLS-only denial crossed into downstream authority unexpectedly")

    # Negative 2: a tenant context owned by another principal cannot be borrowed by the
    # authenticated workload, even if every tenant/runtime field is syntactically canonical.
    stolen_context = TenantContext(
        tenant_id=TENANT_ID,
        principal_id=OTHER_PRINCIPAL_ID,
        principal_kind=PrincipalKind.INTERNAL_SERVICE_PRINCIPAL,
        principal_credential_generation="other-credential-1",
        cell_id="cell-validation-1",
        placement_version="placement-1",
        runtime_generation="runtime-generation-1",
        runtime_profile_id=API_AUTH_BOUNDARY.runtime_profile_id,
        runtime_isolation_class=API_AUTH_BOUNDARY.isolation_class,
        configuration_generation="configuration-1",
        workload_credential_generation="workload-generation-1",
        network_policy_generation="network-policy-1",
        environment_class=EnvironmentClass.VALIDATION,
        isolation_class="tenant-isolation-1",
        fence_scope_id="fence-scope-1",
        fence_epoch=1,
        constructed_at=now,
    )
    trap_placement_2 = TrapPlacementAuthority()
    trap_auth_2 = TrapAuthorizationAuthority()
    trap_final_2 = TrapFinalAdmissionAuthority()
    _expect_denied(
        "borrowed_tenant_context",
        "TenantContext principal binding does not match current principal",
        lambda: authorize_protected_operation(
            principal=principal,
            principal_authority=principal_authority,
            declaration=tenant_declaration,
            placement_authority=trap_placement_2,
            authorization_authority=trap_auth_2,
            context=stolen_context,
            now=now,
            final_admission_authority=trap_final_2,
        ),
    )
    if trap_placement_2.calls or trap_auth_2.calls or trap_final_2.calls:
        raise AssertionError("borrowed-context denial crossed into downstream authority unexpectedly")

    # Positive narrowing control: construct a trusted current TenantContext through the
    # accepted placement authority. Even then, separate current application authorization
    # remains mandatory and an explicit denial must stop before final admission.
    placement = PlacementEvidence(
        tenant_id=TENANT_ID,
        cell_id="cell-validation-1",
        placement_version="placement-1",
        runtime_generation="runtime-generation-1",
        runtime_profile_id=API_AUTH_BOUNDARY.runtime_profile_id,
        runtime_isolation_class=API_AUTH_BOUNDARY.isolation_class,
        configuration_generation="configuration-1",
        workload_credential_generation=credential_generation,
        network_policy_generation="network-policy-1",
        environment_class=EnvironmentClass.VALIDATION,
        isolation_class="tenant-isolation-1",
        runtime_lifecycle=RuntimeLifecycle.ACTIVE,
        placement_current=True,
        operation_eligible=True,
        cell_admission_current=True,
        fence_scope_id="fence-scope-1",
        fence_epoch=7,
    )
    placement_authority = PlacementAuthority(placement)
    trusted_context = construct_tenant_context(
        principal=principal,
        principal_authority=principal_authority,
        placement_authority=placement_authority,
        tenant_id=TENANT_ID,
        destination_cell_id=placement.cell_id,
        destination_runtime_generation=placement.runtime_generation,
        destination_configuration_generation=placement.configuration_generation,
        destination_workload_credential_generation=placement.workload_credential_generation,
        destination_network_policy_generation=placement.network_policy_generation,
        required_environment=EnvironmentClass.VALIDATION,
        now=now,
    )
    if not trusted_context.matches_principal(principal):
        raise AssertionError("trusted TenantContext positive control lost principal binding")

    denying_authorization = DenyingAuthorizationAuthority()
    final_trap = TrapFinalAdmissionAuthority()
    _expect_denied(
        "separate_current_authorization",
        "owning authorization denied the operation",
        lambda: authorize_protected_operation(
            principal=principal,
            principal_authority=principal_authority,
            declaration=tenant_declaration,
            placement_authority=placement_authority,
            authorization_authority=denying_authorization,
            context=trusted_context,
            now=now,
            final_admission_authority=final_trap,
        ),
    )
    if denying_authorization.calls != 1 or final_trap.calls != 0:
        raise AssertionError("authorization-denial control did not stop at the owning authority")

    # Negative 4: an internal service workload cannot become the privileged cross-tenant
    # platform principal merely by running behind an authenticated Control Plane boundary.
    cross_tenant_declaration = AuthorizationDeclaration(
        action="platform.tenants.inspect",
        scope=ScopeClass.PLATFORM,
        tenant_required=False,
        tenant_requirement=TenantRequirement.EXPLICIT_CROSS_TENANT_PRIVILEGED,
        step_up=StepUpClass.NONE,
        audit_class=AuditClass.SECURITY_CRITICAL,
    )
    runtime_authority = CurrentControlPlaneRuntimeAuthority()
    trap_auth_4 = TrapAuthorizationAuthority()
    trap_final_4 = TrapFinalAdmissionAuthority()
    _expect_denied(
        "service_principal_cross_tenant",
        "requires platform principal",
        lambda: authorize_protected_operation(
            principal=principal,
            principal_authority=principal_authority,
            declaration=cross_tenant_declaration,
            placement_authority=trap_placement,
            authorization_authority=trap_auth_4,
            context=None,
            now=now,
            runtime_binding=CONTROL_PLANE,
            runtime_authority=runtime_authority,
            final_admission_authority=trap_final_4,
            cross_tenant_target=CrossTenantTargetBinding(target_tenant_ids=(TENANT_ID,)),
        ),
    )
    if runtime_authority.calls != 1 or trap_auth_4.calls or trap_final_4.calls:
        raise AssertionError("cross-tenant service-principal denial crossed its intended boundary")

    print(
        "workload_identity_non_tenant_authority=PASS "
        f"wire_spiffe_id={WIRE_SPIFFE_ID} canonical_principal={principal.principal_id} "
        "mtls_only_denied=true borrowed_context_denied=true "
        "separate_current_authorization_required=true cross_tenant_platform_denied=true"
    )
    print(
        "conformance_claim=exploratory_only evidence_credited=false ledger_change=false "
        "wave4=not_granted production=none d4=not_selected_not_granted"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
