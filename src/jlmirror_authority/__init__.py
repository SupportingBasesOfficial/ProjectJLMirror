"""Portable Wave 1 authority primitives.

This package implements only the accepted identity/current-authority skeleton.
Frameworks, identity providers, session stores, workload-identity issuers and
secret/config products remain replaceable implementation decisions.
"""

from .config import ConfigurationSchema, ConfigurationSnapshot, require_classified_configuration
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
    TenantRequirement,
)
from .session import (
    BrowserSessionHandle,
    BrowserSessionRecord,
    issue_browser_session,
    resolve_browser_session,
    retire_browser_session,
    rotate_browser_session,
)

__all__ = [
    "AdmissionDenied",
    "AuditClass",
    "AuthenticationStrengthEvidence",
    "AuthorizationDeclaration",
    "BrowserSessionHandle",
    "BrowserSessionRecord",
    "ConfigurationSchema",
    "ConfigurationSnapshot",
    "EnvironmentClass",
    "Principal",
    "PrincipalKind",
    "ScopeClass",
    "SecretReference",
    "StepUpClass",
    "TenantContext",
    "TenantRequirement",
    "issue_browser_session",
    "require_classified_configuration",
    "resolve_browser_session",
    "retire_browser_session",
    "rotate_browser_session",
]
