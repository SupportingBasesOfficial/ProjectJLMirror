# JLMIRROR Contract Tooling — Wave 0

This directory implements `impl.contract-tooling@1` as a repository-local, observer-only conformance substrate.

## Authority boundary

Reviewed documents remain normative. Generated catalogs/schemas are deterministic projections used by implementation and tests; they are not allowed to silently redefine API, event, security, reliability, runtime, release, recovery, Product or OPEN semantics.

The source registry pins every projection owner to the exact accepted Git blob. If an implementation PR changes a pinned normative owner, validation fails until an explicit governance handoff updates the accepted source binding. Git blob IDs are exact repository-content identities, not cryptographic trust/signing authority.

A generated catalog records `source_documents`, not ownership. The source document remains the authority; finding an ID in a projection never creates a new owner.

Composite source requirements are explicit mappings. For example, Phase 10 `allowed_consumer_contracts or discovery policy` is projected as an `anyOf` requirement rather than being discarded as prose.

Structural comparison is deliberately conservative. It may report `structurally_identical`, `structurally_additive_candidate` or `structural_change_requires_review`; none of those labels approves semantic compatibility, which remains owned by the reviewed Phase 09/10 contracts.

## Commands

```text
python3 tools/contracts/validate_contracts.py .
python3 -m unittest discover -s tools/contracts/tests -p 'test_*.py'
python3 tools/contracts/export_contracts.py
```

`export_contracts.py --output <path>` is an explicit developer action. Repository-local output is confined to `build/contract-projections/`; CI does not invoke the exporter or write generated state back to the repository.

## Initial coverage

- versioned profile/catalog IDs from exact pinned manifest sources;
- HTTP endpoint-manifest field projection from Phase 09;
- event semantic-manifest field projection from Phase 10, including registered composite requirements;
- conservative structural schema change reporting that cannot decide semantic compatibility;
- deterministic reference harnesses for tenant/current authority, idempotency create-or-observe, external-effect ambiguity, monotonic fencing and `(R,F]` recovery admission;
- concurrent falsification of one-executor idempotency and one-successor fencing behavior.

The in-memory reference models are test oracles only. They do not claim to implement distributed production authority.

No Product route, application runtime, provider adapter, database migration or production authority is introduced by this slice.
