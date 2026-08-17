# Bounded Contexts

**Status:** proposed baseline

Each context below defines what language and state it owns, what it consumes, and what it deliberately does not own.

## Platform Management

**Owns:** tenant lifecycle, global tenant registry, placement intent/metadata ownership contract, global marketplace catalog, global configuration, platform administration metadata.

**Consumes:** Identity principal references, Commercial customer relationship information.

**Does not own:** tenant operational resources, tenant roles, provider-specific monitoring state.

## Identity

**Owns:** principal, credentials, MFA, session/refresh-family state, recovery, external identity links, principal profile.

**Publishes:** principal lifecycle/security events safe for consumers.

**Does not own:** tenant membership or tenant permissions.

## Organization & Access

**Owns:** tenant membership, roles, permissions, custom roles, authorization assignments/scopes, tenant settings, branding and feature enablement.

**Consumes:** stable Identity principal IDs and Platform tenant IDs.

**Does not own:** authentication credentials or domain resource state.

## Monitoring

**Owns:** monitoring source registration semantics, resource/device internal identity, external monitoring references, metric definitions, current health/state, normalized problems/observations, sync state/checkpoints.

**Consumes:** tenant context and provider-adapter input.

**Publishes:** normalized operational events and query contracts.

**Does not own:** incident/ticket lifecycle, alert notification policy, AIOps findings.

## Alerting

**Owns:** alert lifecycle, alert rules/policies, notification intent, delivery state, escalation policy and operational subscription semantics.

**Consumes:** Monitoring/Infrastructure events and tenant notification configuration.

**Does not own:** raw monitoring history or ITSM ticket state.

## ITSM

**Owns:** incidents/tickets, comments, change/RFC, approvals/tasks, services, SLA, maintenance, knowledge and ITSM sync state.

**Consumes:** alert/resource references through stable contracts.

**Does not own:** monitoring resources or notification delivery infrastructure.

## Automation

**Owns:** automation definitions, versions, parameters, schedules, tasks, workflows, executions and step/result state.

**Consumes:** authorized target/resource references and trigger events.

**Does not own:** identity credentials, external target secrets, or source resource state.

## Infrastructure

**Owns:** assets, relationships/topology, discovery state, infrastructure governance posture, capacity models and configuration-drift/patch-related state.

**Consumes:** monitoring/resource evidence and external infrastructure-provider input.

## AIOps

**Owns:** derived findings, analysis configuration, model/algorithm/version metadata, confidence and correlation outputs.

**Consumes:** monitoring, alerting and infrastructure evidence through read/event contracts.

**Does not own:** source evidence.

## FinOps

**Owns:** resource/service cost entries, budgets, cost forecasts/analysis and optimization opportunities.

**Consumes:** infrastructure/resource identity and commercial rate/context when explicitly contracted.

## Commercial

**Owns:** customer commercial account, contracts/plans, pricing/billing-cycle state, invoices/payments and provider reconciliation state.

**Consumes:** platform tenant/customer linkage and external payment-provider results.

## Reporting & Experience

**Owns:** report definitions, schedules/deliveries, generated artifact metadata, executive/public projections and presentation-oriented read models.

**Consumes:** stable domain query/event contracts.

**Does not own:** source transactional entities.

## Integrations & Extensibility

**Owns:** API-credential metadata, webhook configuration/delivery, tenant integration instances, marketplace installation state and connector sync metadata.

**Consumes:** versioned integration events and provider adapters.

**Does not own:** domain business semantics merely because an external system exposes them.

## Data Administration

**Owns:** export/import/direct-query request records, state, authorization policy references, generated data artifact metadata and operational audit linkage.

**Does not own:** the data being exported or queried.

## Compliance & Governance

**Owns:** compliance control catalog/application, evidence metadata, governance workflows and policy application state.

**Consumes:** audit/evidence from domain owners.

**Does not silently mutate:** source business state to satisfy compliance; remediation goes through owning-domain commands.