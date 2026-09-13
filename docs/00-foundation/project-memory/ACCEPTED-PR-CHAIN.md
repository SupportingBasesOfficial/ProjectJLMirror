# JLMirror Accepted PR Chain

Status: canonical project-memory source

This file indexes the accepted Wave 4 governance/implementation chain needed to reconstruct current state. Earlier phases remain authoritative in their own accepted docs/PRs and should be expanded here over time.

| PR | Outcome | Canonical result |
|---|---|---|
| #123 | Wave 4 authorization | accepted |
| #124 | superseded work | closed/superseded |
| #125 | organization/provider/commercial model | accepted |
| #126 | late #125 remediation | accepted |
| #127 | ADR collision remediation | accepted |
| #128 | shared provider lineage | accepted |
| #129 | scope validation | accepted |
| #130 | validation TOCTOU fix | accepted |
| #131 | superseded work | closed/superseded |
| #132 | tenant/canonical boundaries v2 | accepted |
| #133 | host authorization | accepted |
| #134 | host resource-kind correction | accepted; `resource_kind=host` is broad Monitoring class, not final device taxonomy |
| #135 | host inventory runtime | accepted |
| #136 | metric definition authorization | accepted |
| #137 | metric definitions runtime | accepted |
| #138 | metric current state authorization | accepted |
| #139 | metric current state runtime | accepted |
| #140 | metric history authorization | accepted |
| #141 | metric history foundation runtime | squash `4908e5124f2d182146d0366030c1dd64c778a423` |
| #142 | Problem State authorization | main `fb79a4c955e1f50db3da1f1c16f08d9cba056401` after merge |
| #143 | Problem State runtime | squash `1da4350cb860d759549b6302e575a02af6f07b09` |
| #144 | Health Projection authorization | main `1e38a90ddb22fb4b42e64686d02c970ad2e8bead` after merge |
| #145 | Health Projection runtime | squash `193883f0b3ddfd3531ceb54e0849c2f6e04744bc` |
| #146 | Monitoring->Alerting publication authorization | squash/main `e7cb9512846926f01429d3fbc4c6d6b0a2a9db71` |
| #147 | Alert Core Model authorization | squash/main `fb7d2e6309df432b133105aa081dc1ef37784820` |
| #148 | Monitoring->Alerting publication runtime | OPEN at this snapshot; branch `impl/wave4-monitoring-alerting-publication` |

## Branch policy
Accepted working branches are generally preserved; do not delete branches automatically.

## Merge policy
- merge only after explicit user authorization;
- prefer squash merge;
- use exact reviewed head protection when available;
- require exact-head CI/review cleanliness before merge.

## HARDEN expectation
Material findings are not merely patched. Their root lesson should be converted into durable tests/validators/learning-ledger protection when appropriate.

## Reconstruction note
This index intentionally distinguishes accepted merge results from open work. Never infer that an open PR is canonical `main` state.
