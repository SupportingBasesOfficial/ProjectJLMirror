# D2 / OPEN-REL-030 Evidence State

**State:** OPEN / PARTIAL EVIDENCE  
**Production authority:** none  
**Wave 4 implementation authorization:** not granted  
**Tier 1 mechanism:** PostgreSQL transactional acceptance pattern selected by existing decision; real-database conformance in progress  
**Tier 2 mechanism:** TimescaleDB candidate under falsification; not selected/canonical

## Gate state

```text
D1 ratified canonical base
  main@5f031ae4bacc0c441eeee16f9c67d272e39d6b0b
        |
        v
D2 bounded evidence harness
        |
        +-- Tier 1 real PostgreSQL proof          IN PROGRESS
        +-- Tier 2 Timescale isolation proof      IN PROGRESS
        +-- crash / ambiguity / recovery matrix   PARTIAL
        +-- relocation / PITR matrix              NOT YET COMPLETE
        +-- capacity under security profile        NOT YET COMPLETE
        |
        v
OPEN-REL-030 closure                            BLOCKED
        |
        v
Wave 4 implementation authorization            BLOCKED
```

## Acceptance rule

This file may move to `EVIDENCE COMPLETE — READY FOR DECISION REVIEW` only when every mandatory vector in `OPEN-REL-030` has reproducible evidence on the exact PR HEAD.

It may never move directly to `accepted`, `canonical` or `implementation authorized`; those are separate governance actions.
