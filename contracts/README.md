# Machine-readable contract projections

`contracts/` is the machine-readable projection boundary introduced by implementation Wave 0.

The authoritative meaning remains in reviewed `docs/`. Tooling under `tools/contracts/` reads only the exact registered source files and deterministically projects profile IDs and manifest field requirements. Generated output is conformance evidence/input only.

`catalog/source-registry.json` pins each normative input to both the accepted Implementation Readiness base and its exact Git blob object ID. A source-content change therefore fails the implementation projection instead of silently moving the contract boundary with the code. Updating a pin is a governance handoff tied to an accepted normative change, not ordinary implementation discretion.

The `git_blob_sha` values are Git object identities for exact repository-content binding. They are not secret material, signature proof or a substitute for Phase 14 source/artifact trust.

`catalog/source-registry.schema.json` documents the registry shape. Composite normative requirements that are not single machine field names must be explicitly registered and are projected into enforceable schema alternatives; unregistered prose in the selected manifest block fails closed.

No Product-facing API/event family is created here. Endpoint/event contract instances become eligible only when their exact reviewed Product/domain contract exists.
