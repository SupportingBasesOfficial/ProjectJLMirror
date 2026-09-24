# 67 — Additional Notification Channel Expansion Proposal

**Status:** proposed — candidate expansion of G9 transport capability; grants no additional channel authority while proposed  
**Decision class:** C2 provider/transport selection under the accepted G9 notification-delivery domain  
**Drivers:** `ADR-005`, `ADR-013`, accepted `g9.notification-delivery@1`, G8 authoritative-visibility separation

This record proposes how G9 may later expand beyond its currently admitted transport.

## Existing G9 authority

The accepted G9 v1 contract remains authoritative:

- the only admitted transport channel is `whatsapp_business@1`;
- notification intent, delivery attempt, provider evidence and delivery projection are separate concepts;
- retry stays on the same admitted channel;
- `fallback_action_required` does not authorize another channel;
- external read evidence is not G8 authoritative native visibility;
- email, SMS, push, Teams, Slack and other transports are outside current G9 authority;
- the existing application-facing `NotificationPort` owns notification-intent persistence/read operations. This proposal does not redefine that interface.

Therefore this proposed record must not describe SMTP, webhook, SMS, or any second transport as already authorized or implemented.

## Proposed channel-expansion boundary

If an additional channel is accepted, provider delivery should remain behind a worker-side adapter boundary distinct from the existing intent port.

Candidate conceptual interface:

```python
class NotificationTransportAdapter(Protocol):
    channel_class: str

    def dispatch(self, request: DispatchRequest) -> DispatchEvidence:
        ...
```

This is a conceptual boundary only. The exact runtime interface, sync/async shape and package location must be fixed by the future implementation authorization.

The adapter receives an already-admitted G9 dispatch request. It does not:

- create notification intents;
- select tenant;
- select recipient/routing policy;
- mutate Alert, ACK, responsibility, Incident, or Automation state;
- convert provider IDs into platform IDs;
- claim authoritative read evidence.

Provider responses/callbacks are normalized into the existing G9 evidence semantics rather than creating a second notification truth model.

## Candidate additional channels

The following are candidates, not authorizations.

### Email / SMTP

Candidate class: `smtp_email@1`.

Required evidence before authorization:

- TLS profile and certificate validation are explicit;
- envelope/from/recipient authority is derived from trusted tenant configuration, not untrusted payload fields;
- credentials come from accepted secret authority;
- provider acceptance is not represented as inbox delivery/read;
- retry/idempotency maps into G9 immutable-attempt semantics.

### Generic HTTPS webhook

Candidate class: `https_webhook@1`.

Required evidence before authorization:

- HTTPS only under an accepted TLS profile;
- endpoint is selected from trusted tenant configuration;
- SSRF/private-network controls are explicit;
- request authenticity/signing profile is versioned;
- retries are at-least-once safe and provider response does not gain platform authority;
- callback/response body is bounded and untrusted.

Slack, Teams, PagerDuty or other products may later be implemented through this generic adapter only if their endpoint/authentication model fits the accepted profile. Their brand names do not create independent authority.

### SMS

Candidate class: `sms@1`.

No provider is selected by this record. Twilio may be evaluated as a C2 provider candidate, but provider selection, credential profile, delivery receipt semantics, phone-number privacy, regional constraints and cost/rate controls require a separate acceptance step.

### Additional WhatsApp provider/profile

G9 already admits `whatsapp_business@1`. A different BSP/provider implementation may be replaceable behind the accepted channel contract only if it preserves the exact admitted semantics and passes a separately governed conformance profile. This record does not widen the existing WhatsApp authority.

## Channel capability classification

Any future channel authorization must explicitly classify at least:

- provider request accepted;
- provider accepted;
- delivered, if the provider can prove it;
- external read observed, if supplied;
- failed;
- unknown.

The platform must preserve:

```text
SENT != PROVIDER_ACCEPTED
PROVIDER_ACCEPTED != DELIVERED
DELIVERED != VIEWED
EXTERNAL_READ != G8_AUTHORITATIVE_VIEW
PROVIDER_MESSAGE_ID != PLATFORM_NOTIFICATION_ID
```

A channel lacking a stronger evidence signal stays at the strongest state actually proven.

## Routing and response policy boundary

This record does **not** authorize notification routing policy.

A future response-orchestration capability may request a G9 notification intent only after that orchestration capability is separately accepted. Channel selection must then be represented as admitted G9 intent/configuration authority, not as arbitrary provider data.

Record 66 is also proposed; neither record depends on treating the other as already authorized.

## Privacy and secret requirements

Every additional channel must define:

- destination storage and masking rules;
- secret/key authority;
- minimum audit fields;
- raw provider payload retention limits;
- PII minimization;
- tenant isolation;
- callback authenticity/replay controls when callbacks exist.

Raw email addresses, phone numbers, signing keys and provider tokens must not appear in ordinary logs.

## Closure conditions before any additional channel authorization

For each candidate channel:

1. exact `channel_class` and version are fixed;
2. runtime adapter scope is bounded;
3. cross-tenant routing is falsified;
4. direct application/provider mutation of G9 tables is blocked;
5. retry creates a new immutable attempt under the existing G9 model;
6. duplicate dispatch/callback behavior is idempotent;
7. provider evidence cannot fabricate stronger delivery/read state;
8. external read cannot fabricate G8 authoritative visibility;
9. secret/PII logging is falsified;
10. restart/replay/reconciliation is proven.

A channel that has not satisfied these conditions remains outside G9 authority.

## Consequences

### Positive

- G9 can expand without redefining its intent/attempt/evidence model;
- provider selection remains replaceable C2 infrastructure;
- new channels inherit the existing separation between notification delivery and authoritative human visibility.

### Cost / risk

- each transport has distinct security, privacy and evidence semantics;
- webhook support introduces SSRF and signing concerns;
- SMS/email introduce PII and deliverability/regional concerns;
- multi-channel fallback/routing remains a separate product-policy problem.

## Exit / revisit conditions

Revisit if routing/fallback becomes its own domain, if notification delivery is extracted from the monolith, or if a provider requires semantics that cannot be normalized without changing the accepted G9 evidence model.
