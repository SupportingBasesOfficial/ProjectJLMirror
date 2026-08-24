"""Portable Wave 1 authority primitives.

This package implements only the accepted identity/current-authority skeleton.
Frameworks, identity providers, session stores, workload-identity issuers and
secret/config products remain replaceable implementation decisions.
"""

from .model import (
    AdmissionDenied,
    AuditClass,
    AuthenticationStrengthEvidence,
    AuthorizationDeclaration,
    EnvironmentClass,
    Principal,
    PrincipalKind,
    ScopeClass,
    SecretReference,
    StepUpClass,
    TenantContext,
)

__all__ = [
    "AdmissionDenied",
    "AuditClass",
    "AuthenticationStrengthEvidence",
    "AuthorizationDeclaration",
    "EnvironmentClass",
    "Principal",
    "PrincipalKind",
    "ScopeClass",
    "SecretReference",
    "StepUpClass",
    "TenantContext",
]
