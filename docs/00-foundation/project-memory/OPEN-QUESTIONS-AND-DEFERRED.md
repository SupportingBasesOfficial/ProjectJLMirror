# JLMirror Open Questions and Deferred Work

Status: canonical project-memory source

This file records intentional non-decisions and deferred scopes so future contributors do not mistake absence for acceptance.

## Alerting
- exact Alert Policy/Evaluation DSL/model remains unaccepted;
- exact grouping/correlation/dedupe semantics remain unaccepted;
- timing/debounce/confirmation semantics remain unaccepted;
- policy conflict/precedence behavior remains unaccepted;
- policy edit behavior for existing active Alerts remains unaccepted;
- automatic Alert create/resolve remains blocked until prerequisites are accepted.

## Human responsibility / ACK
- canonical persistence/API/event models are not yet authorized;
- exact responsibility roles/types are not yet accepted;
- whether/how ACK reversal exists is not accepted;
- ACK comments/reasons vocabulary and permissions are not accepted;
- resource-level responsibility inheritance/delegation rules are not accepted.

## Notification / authoritative visibility
- channel capability model is not yet authorized;
- exact WhatsApp/e-mail/SMS/push/provider integrations are not selected here;
- which workflows require authoritative read evidence versus best-effort notification must be explicitly authorized;
- exact authenticated JLMirror confirmation surface is not yet designed;
- privacy/retention rules for read/view receipts remain to be authorized;
- customer identity binding and delegation for approvals remain to be authorized.

## Response / approval
- quote/budget object ownership may belong to Commercial/ITSM/another bounded context and must be decided explicitly;
- approval lifecycle, expiration, cancellation, revision/requote semantics remain open;
- waiting-state vocabulary and SLA pause/continue rules remain open.

## Monitoring
- full Metric History product (retention/downsampling/query/export/scale policy) remains incomplete;
- advanced device taxonomy/vendor/model/role/topology remains future work;
- future additional providers remain undefined until separately authorized.

## ITSM / Automation / AIOps
- detailed state machines and cross-domain contracts remain future authorization work;
- no assumption should be made that an Alert automatically creates an Incident;
- no assumption should be made that an Alert automatically executes an automation;
- AIOps findings must not silently gain authority over Monitoring/Alerting lifecycle.

## Frontend / production
- final UX/navigation/NOC screen contracts remain incomplete;
- production deployment/HA/DR/performance/capacity/security operations require separate evidence;
- IMPLEMENTED does not imply PRODUCTION-READY.

## Memory system
- this foundation establishes the corpus and validator contract;
- future accepted work should progressively backfill earlier phases/PRs with richer links and exact authority references;
- automation may later validate canonical main SHA and accepted PR chain against GitHub metadata, but must not silently rewrite repository truth.
