# Machine-readable contract projections

`contracts/` is the machine-readable projection boundary introduced by implementation Wave 0.

The authoritative meaning remains in reviewed `docs/`. Tooling under `tools/contracts/` reads the exact registered owner files and deterministically projects profile IDs and manifest field requirements. Generated output is conformance evidence/input only.

The first static contract is `catalog/source-registry.json`, whose shape is documented by `catalog/source-registry.schema.json`. It prevents tooling from scanning arbitrary prose and accidentally treating incidental text as canonical ownership.

No Product-facing API/event family is created here. Endpoint/event contract instances become eligible only when their exact reviewed Product/domain contract exists.
