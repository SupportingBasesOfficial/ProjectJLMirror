# G6 Monitoring → Alerting Transport — Runbook

## Slice

`g6.monitoring-alerting-transport@1`

## Runtime entrypoint

```text
python tools/g6/run_monitoring_alerting_transport_runtime.py
```

The proof executes:

1. worker/current-execution-authority/contract/adapter/SQL-boundary tests;
2. accepted Wave 2 async correctness validator;
3. accepted Monitoring→Alerting publication PostgreSQL conformance;
4. G6 PostgreSQL conformance over real Wave 2 + Wave 4 schemas;
5. hardened non-networked worker container proof.

## Transport flow

```text
validated Monitoring integration envelope
 -> durable create-or-observe Wave 2 inbox receipt
 -> current execution authority
 -> fenced processing claim
 -> current Monitoring source/Problem/Health reread
 -> durable resync result OR reconciliation_required
 -> stop
```

There is no Alert business mutation in G6.

## Duplicate and ambiguity behavior

- equivalent redelivery observes the same durable receipt;
- conflicting same identity/equivalence fails closed;
- completed duplicate does not execute again;
- expired processing lease becomes `reconciliation_required`, never blind retry;
- historical generation completes only as a non-current disposition;
- reordered events reread the current owner projection and cannot regress it.

## Runtime boundaries

The application invokes only three guarded SECURITY DEFINER capabilities:

- `system.g6_admit_monitoring_alerting_message(...)`;
- `system.g6_claim_monitoring_alerting_receipt(...)`;
- `system.g6_complete_monitoring_alerting_resync(...)`.

The invoker has EXECUTE only. Direct table writes remain unavailable.

## Production authority

This proof does not activate a production worker, broker consumer topology, G7 Alert business behavior.
