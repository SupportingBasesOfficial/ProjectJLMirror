import assert from "node:assert/strict";
import test from "node:test";

import {presentShell, PUBLIC_STATES} from "../../apps/g1-identity-tenant-shell/frontend/shell-state.mjs";


test("public shell state set is bounded", () => {
  assert.deepEqual(PUBLIC_STATES, [
    "loading",
    "ready",
    "unauthenticated",
    "forbidden",
    "revoked",
    "unavailable"
  ]);
});

test("ready state exposes only admitted tenant context", () => {
  assert.deepEqual(
    presentShell({
      state: "ready",
      tenant_id: "tenant-a",
      principal_id: "principal-a",
      admission_revision: "rev-7"
    }),
    {state: "ready", message: "Access is current.", tenantId: "tenant-a"}
  );
});

test("malformed ready state fails closed without tenant disclosure", () => {
  assert.deepEqual(
    presentShell({state: "ready", tenant_id: "tenant-a"}),
    {
      state: "unavailable",
      message: "Current access cannot be verified right now.",
      tenantId: null
    }
  );
});

test("forbidden and revoked states do not carry tenant context", () => {
  for (const state of ["unauthenticated", "forbidden", "revoked", "unavailable"]) {
    const result = presentShell({state, tenant_id: "tenant-should-not-leak"});
    assert.equal(result.state, state);
    assert.equal(result.tenantId, null);
  }
});

test("unknown state fails closed", () => {
  assert.equal(presentShell({state: "surprise"}).state, "unavailable");
  assert.equal(presentShell({state: "surprise"}).tenantId, null);
});
