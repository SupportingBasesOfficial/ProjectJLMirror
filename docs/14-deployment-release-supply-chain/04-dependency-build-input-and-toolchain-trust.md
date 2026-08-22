# Phase 14 — Dependency, Build Input and Toolchain Trust

**Status:** proposed baseline

## Purpose

This contract defines safety properties for dependencies, build inputs and toolchains without selecting package manager, builder, scanner, registry or CI vendor.

## Build input set

A build record identifies all material inputs required to explain artifact bytes/behavior, including as applicable:

- exact source state;
- dependency lock/resolution state;
- compiler/interpreter/build tool identities;
- build scripts and generated-code inputs;
- base images/runtime layers;
- build-time configuration that affects artifact semantics;
- policy/manifest versions used to admit inputs.

## Dependency integrity

Dependencies and build inputs SHALL be integrity-addressable or otherwise verifiably bound to the build record. Floating/mutable references are not sufficient production trust evidence when they can change bytes without changing the recorded release input.

## Dependency risk

Automated vulnerability/integrity analysis produces evidence and blockers, not automatic version authority. A reported issue requires deliberate compatibility/security evaluation before a dependency change becomes source authority.

## Build isolation

The build environment is untrusted with respect to production runtime authority. It should not possess production tenant data, production runtime credentials or broad production deployment authority.

Build-time network access, caches and mirrors are bounded/observable enough to prevent undeclared dependency substitution from becoming invisible.

## Toolchain integrity

A toolchain change is a supply-chain compatibility input even when application source is unchanged. The release evidence identifies toolchain/profile versions sufficiently to detect an unreviewed trust change.

## Generated content

Generated source/artifacts are traceable to generator and inputs. Generated content cannot bypass review merely because it was machine-created.

## Reproducibility

Reproducible/deterministic builds are desirable evidence where feasible, but Phase 14 does not fabricate implementation proof. When byte-for-byte reproducibility is not available, provenance SHALL still identify all material inputs and the implementation must define equivalent tamper/substitution detection.

## Cache poisoning

Build caches are optimization state, not authority. Cache hits do not waive integrity verification or provenance binding.

## Secrets

Build secrets, if ever required, use scoped references/ephemeral credentials and SHALL NOT be embedded in artifact layers, SBOM/provenance public fields, logs or caches.

## OPEN

Exact dependency scanner, builder, package registry, mirror, base-image policy, hermeticity mechanism, reproducibility mechanism and vulnerability thresholds remain OPEN pending implementation evidence.