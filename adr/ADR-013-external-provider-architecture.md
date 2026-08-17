# ADR-013 — External Provider Adapter Architecture

**Status:** proposed  
**Date:** 2026-08-17  
**Reversibility:** reversible if domain ports remain stable

## Context

Monitoring, ITSM, payment, identity and notification systems are outside the platform trust boundary. Provider outages/payloads must not define JLMIRROR availability or ubiquitous language. Tenant-configured URLs can create SSRF risk.

Drivers: `FR-MON-001..002`, `FR-ITSM-005`, `FR-ID-003`, `FR-COM-002`, `INV-EXT-*`, `SEC-INT-*`, `QA-AVAIL-001`, `TM-005`, `TM-006`.

## Decision

Every external provider SHALL be implemented behind a platform-owned port/adapter contract. Provider-native payloads are validated, bounded and normalized before entering owning domains.

Connector execution SHALL define:

- connect/request/overall timeouts;
- retryability categories and bounded retry;
- provider/tenant rate limits where applicable;
- circuit-breaker/degraded-state policy;
- SSRF/egress policy and protocol/destination restrictions;
- response/body size limits;
- credential secret references and least privilege;
- correlation/audit/metrics without secret leakage;
- external-ID mapping separate from internal platform identity.

Initial Monitoring Source support MAY include Zabbix, but Zabbix concepts SHALL NOT become the only canonical Monitoring model.

## Consequences

### Positive
- provider replacement/addition does not rewrite domain rules;
- resilience/security controls are concentrated at trust boundary;
- provider failure can be isolated by tenant/provider.

### Negative / cost
- adapter normalization adds mapping code;
- provider-specific capabilities may require explicit extension points rather than leaking native models.

## Validation

Contract tests with malformed/oversized payloads, timeout, auth failure, redirect/SSRF attempts and provider outage. Verify one tenant provider failure does not block unrelated tenants.

## Exit / revisit conditions

A provider may receive a specialized service/runtime if independent scale or SDK/runtime requirements justify extraction under ADR-020.
