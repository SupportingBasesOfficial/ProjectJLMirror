# JLMirror Project Identity

Status: canonical project-memory source
Canonical main at foundation: `fb7d2e6309df432b133105aa081dc1ef37784820`

## What JLMirror is
JLMirror is a provider-neutral, B2B, multi-tenant SaaS platform for monitoring and IT operations. It is designed to receive technical facts from external monitoring/infrastructure providers, translate them into platform-owned canonical models, and use those models to support Monitoring, Alerting, ITSM, Automation, Infrastructure, AIOps, FinOps and Commercial capabilities.

## Why it exists
External providers such as Zabbix are valuable sources of technical evidence, but they must not become the permanent business identity or source of platform truth. JLMirror exists to separate provider-specific observation from platform-owned operational meaning.

## Current provider
Current provider integration target: Zabbix 7.4.

Canonical flow:

`Zabbix -> Adapter -> Canonical Model -> Domains`

## Product principles
- tenant isolation is foundational;
- provider IDs are evidence, never platform identity;
- provider timestamps and event arrival do not define platform ordering/authority;
- PostgreSQL is durable business truth;
- asynchronous delivery is at-least-once and therefore idempotency is mandatory;
- browser/network presence is never sufficient trust;
- domain ownership must be explicit;
- state machines and cross-domain effects require accepted authorization before runtime implementation.

## What it is not
JLMirror is not a Zabbix UI, not a passive dashboard and not a thin proxy over provider APIs.

## Intended final outcome
When complete, JLMirror should provide a coherent operational chain from infrastructure observation through actionable alerts, human responsibility, verified communication/visibility, approvals, escalation, ITSM, automation, AIOps, dashboards, reporting and production-grade operations without coupling core business semantics to one provider.
