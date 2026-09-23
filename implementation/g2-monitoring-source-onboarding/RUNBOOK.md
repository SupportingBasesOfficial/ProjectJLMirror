# G2 Monitoring Source Onboarding - Runtime Proof

This slice composes the accepted G1 current-authority boundary with the accepted Monitoring Source foundation and accepted initial-validation worker. It does not own canonical source persistence or provider validation truth.

## Canonical local proof

From repository root:

```bash
python tools/g2/run_monitoring_source_onboarding_runtime.py
```

The runtime proof executes, in order:

1. bounded G2 unit and current-authorization tests;
2. the accepted initial-validation worker tests from the shared Wave 4 substrate;
3. the accepted initial-validation PostgreSQL conformance proof;
4. a real browser E2E using Chrome/Chromium, the G1 opaque browser session + CSRF boundary, the G2 BFF/UI, canonical Monitoring Source PostgreSQL persistence, and the accepted initial-validation worker;
5. a bounded container proof that resolves the Python base image to its immutable RepoDigest, builds the G2 BFF image, boots HTTPS with a read-only root filesystem, drops all Linux capabilities, enables no-new-privileges, verifies the HTTPS root response, and proves fixture-only routes remain disabled.

The browser proof covers success, same-key replay, missing configured HostGroup, revoked current authority, and cross-tenant denial. The container proof is runtime evidence only; it confers no deployment or production authority.

## Runtime workflow

The pull-request runtime workflow is:

```text
.github/workflows/g2-monitoring-source-onboarding-runtime.yml
```

It checks out the exact analyzed PR HEAD with persisted credentials disabled, verifies the commit identity, and executes the same canonical local command.

The standalone container sub-proof is also reproducible from repository root:

```bash
python tools/g2/run_g2_container_proof.py
```

Its Docker build definition is `apps/g2-monitoring-source-onboarding/Dockerfile.runtime-proof`; the harness resolves `python:3.13-slim-bookworm` to one immutable `python@sha256:...` RepoDigest before building.

## Composition boundary

G2 owns only:

- request and response shape validation;
- current Monitoring action admission composed from accepted platform authority;
- protected BFF routing and CSRF enforcement;
- server-side provider-binding lookup;
- orchestration of canonical source creation;
- handoff to the already-accepted validation responsibility;
- truthful onboarding presentation.

The accepted Monitoring Source foundation remains authoritative for source identity, generation, configuration/scope revision, idempotency, operation state, and durable evidence. The accepted initial-validation worker remains authoritative for provider validation and stale-authority fencing.

## Source onboarding sequence

```text
opaque G1 browser session
-> current tenant + monitoring.source.manage admission
-> CSRF validation
-> strict request decode
-> server-side provider binding lookup
-> accepted Monitoring Source creation plan
-> accepted canonical local source transaction
-> durable validation responsibility
-> pending browser-visible state
```

Same-key replay observes the already-committed logical source identity; a fresh local plan can never replace the committed identity returned to the user.

## Validation and read sequence

```text
accepted initial-validation worker
-> durable evidence completion
-> current monitoring.source.read admission
-> current monitoring.sync.read admission
-> BFF status read
-> truthful browser state
```

A provider connection is confirmed only when durable source evidence is `current` and the durable operation state is `succeeded`. Missing configured HostGroup remains `incomplete`; revoked/cross-tenant authority fails closed.

## Binding boundary

The browser/API carries only `credential_binding_ref`. Provider access material is resolved only inside the accepted worker boundary and is never rendered into browser state or ordinary Monitoring persistence.

## Merge boundary

Green checks are evidence only. Trusted scope/readiness and a separate explicit owner authorization are still required before merge.
