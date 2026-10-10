"""JLMIRROR FastAPI application layer.

This package implements the runnable backend that connects the domain primitives
in ``src/`` to PostgreSQL and exposes them through a versioned HTTP API.

Architecture (ADR-001): modular monolith with independent workers.
API boundary (ADR-007): Browser -> Web/BFF -> Versioned API -> Application modules.
Tenant isolation (ADR-003): RLS-enforced, tenant context from trusted authority.
"""
