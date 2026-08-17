# Context Map

**Status:** proposed baseline

The context map defines allowed semantic dependencies. It does not require network calls between contexts inside a modular monolith.

## Foundation relationships

- Platform Management provides stable Tenant identity/lifecycle to Organization & Access and all tenant-scoped contexts.
- Identity provides stable Principal identity to Organization & Access.
- Organization & Access provides authorization decisions/context to protected use cases; domain modules remain responsible for enforcing required permissions at their boundaries.

## Operational relationships

- Monitoring publishes normalized resource/health/problem/metric-related facts consumed by Alerting, Infrastructure, AIOps and Reporting projections.
- Alerting consumes operational facts and may publish Alert lifecycle facts to ITSM, Automation, Reporting and Integrations.
- ITSM references Monitoring/Infrastructure resources through stable IDs/contracts; it does not mutate their internal storage.
- Automation consumes authorized resource references and trigger events; execution results are owned by Automation and may publish domain/integration events.
- Infrastructure consumes resource/monitoring evidence and publishes infrastructure state used by AIOps, FinOps, ITSM and Reporting.
- AIOps consumes evidence and publishes derived findings; it never rewrites source evidence.
- FinOps consumes resource/service identity and cost inputs; Commercial remains owner of customer billing/payment business state.
- Reporting consumes queries/events/projections from owners and publishes presentation/read artifacts only.

## Integration relationships

- Integrations & Extensibility exposes versioned external contracts and invokes domain application ports rather than writing domain tables.
- Provider adapters translate external models at anti-corruption boundaries.
- Webhook delivery consumes integration events after the originating transaction commits.

## Governance relationships

- Security policy/enforcement applies at every trust boundary.
- Observability receives telemetry from every runtime without becoming owner of business state.
- Compliance & Governance consumes audit/evidence and requests remediation through owning-domain interfaces.

## Forbidden relationship patterns

- cross-domain direct database mutation;
- external-provider payload treated as canonical internal entity without normalization;
- reporting/public output querying arbitrary internal data without a defined projection/contract;
- queue/job payload selecting physical tenant connection/schema directly;
- UI feature visibility used as authorization;
- global-admin identity automatically treated as unrestricted data-plane bypass.