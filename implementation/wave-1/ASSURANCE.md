# Wave 1 Assurance Boundary

Wave 1 conformance evidence is subordinate to the accepted Product, Security, API, Reliability, Runtime, Operations and Implementation Readiness authorities.

Required exact-HEAD evidence before merge readiness:

- repository deterministic assurance remains green;
- Wave 0 contract tooling remains green;
- Wave 1 unit/adversarial tests remain green;
- Wave 1 authority validator reports no findings;
- PR scope remains only identity/control-plane/minimal-runtime authority skeleton;
- no residual C2 product is silently promoted to architecture authority;
- no Product/domain endpoint family is introduced beyond accepted authority;
- review findings are resolved only after later exact-HEAD evidence;
- Native Assurance passes 1–12 are clean on the exact final HEAD.

`CI GREEN != MERGE AUTHORIZATION` and `WAVE 1 ACCEPTED != WAVE 2 AUTHORIZED`.
