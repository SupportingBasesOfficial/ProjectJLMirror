# D4-C OPEN-EVT-009 quarantine/redrive source evidence

Status: **source evidence only; no ledger promotion and no candidate selection**.

Canonical base: `main@48734ede4bceb6b4f25f7ac5c9f84ced9563e351`.

## Decision and evidence axis

- decision: `OPEN-EVT-009`;
- evidence: `quarantine_redrive_current_authority_and_dedup_preservation`;
- D4-C candidate selection remains open;
- current D4-C ledger remains `1/9` because only OPEN-EVT-008 has been separately promoted.

The accepted candidate classes are:

1. `durable_platform_quarantine_store_with_broker_dlq_adapter`;
2. `broker_native_dlq_with_canonical_platform_quarantine_index`;
3. `hybrid_platform_quarantine_store_plus_broker_dlq`;
4. `equivalent_reviewed_profile` remains `insufficient_evidence` until separately reviewed evidence exists.

## Executable source semantics

The executable harness establishes one platform-owned quarantine process truth across all three concrete candidates. Broker-native DLQ coordinates are transport adapter metadata and cannot become the logical quarantine identity or business/recovery truth.

The source run proves:

- bounded retry exhaustion transitions work into governed quarantine;
- the retry count used by the harness is a test-only bounded fixture and does not select production retry numerics;
- for the same scoped message identity, retry count cannot regress and retry budget cannot be silently rebound;
- once governed quarantine is reached, failure redelivery cannot reopen the record as retryable;
- redrive requires **current** privileged authority, not merely historical authority;
- current redrive authority is scoped by actor, tenant and data classification;
- authority for one tenant cannot authorize redrive in another tenant;
- revocation removes historical authority from current admission;
- redrive attempts, denials and admissions carry durable actor, tenant-scope and reason/outcome audit evidence;
- redrive re-enters normal deduplication, content-equivalence and reconciliation admission instead of bypassing it;
- same scoped identity with changed immutable content fails closed as integrity failure;
- identity without durable equivalence evidence is uncertainty, not duplicate success;
- ambiguous external-effect outcome requires reconciliation rather than blind re-execution;
- confidential payload/equivalence access is tenant- and classification-scoped;
- retention is represented only as a governed, nonnumeric policy class in this C2 evidence;
- broker replacement changes adapter metadata while preserving platform quarantine identity, classification, retention policy and audit history;
- durable current authority and quarantine truth survive the process restart exercised by the evidence harness.

## Deliberate non-selection

This evidence does **not** select:

- one of the three concrete quarantine/DLQ candidate classes;
- a broker-native DLQ product or topology;
- a numeric retry count/backoff/retention/quarantine horizon;
- an OPEN-EVT-011 content-equivalence profile;
- a redrive UI/API/product surface;
- storage technology/schema for production quarantine;
- a production IAM/RBAC technology or tenant-authorization implementation;
- Product, Wave4, production or C3 authority.

The harness uses SHA-256 only as a deterministic test comparator over canonicalized fixture content. It is not an OPEN-EVT-011 production content-equivalence selection.

## Ledger and authority boundary

This source PR must keep:

- source `current_run_auto_credit=false`;
- source `ledger_credit=[]`;
- D4-C current ledger exactly `1/9`;
- `OPEN-EVT-009` still present in D4-C `evidence_remaining`;
- D4-C candidate `null`, `not_selected`, `candidate_selection_open`;
- D4-D `0/5`;
- D4-wide `13/26`;
- D4 gate `scoped`;
- transport authority `selected_not_granted`;
- Product/Wave4 implementation authority `not_granted`;
- production authority `none`;
- C3 numeric/topology authority `not_selected`.

A later ledger promotion, if source evidence becomes exact-HEAD CLEAN, must be a separate reviewed PR. Candidate selection and full D4 acceptance remain later independent transitions.
