# JLMIRROR Contract Tooling — Wave 0

This directory implements `impl.contract-tooling@1` as a repository-local, observer-only conformance substrate.

## Authority boundary

Reviewed documents remain normative. Generated catalogs/schemas are deterministic projections used by implementation and tests; they are not allowed to silently redefine API, event, security, reliability, runtime, release, recovery, Product or OPEN semantics.

## Commands

```text
python3 tools/contracts/validate_contracts.py .
python3 -m unittest discover -s tools/contracts/tests -p 'test_*.py'
python3 tools/contracts/export_contracts.py
```

`export_contracts.py --output <path>` is an explicit developer action. CI does not write generated output back to the repository.

## Initial coverage

- versioned profile/catalog IDs from exact registered manifest owners;
- HTTP endpoint-manifest field projection from Phase 09;
- event semantic-manifest field projection from Phase 10;
- structural schema compatibility report that is explicitly insufficient to decide semantic compatibility;
- deterministic reference harnesses for tenant/current authority, idempotency create-or-observe, external-effect ambiguity, monotonic fencing and `(R,F]` recovery admission.

No Product route, application runtime, provider adapter, database migration or production authority is introduced by this slice.
