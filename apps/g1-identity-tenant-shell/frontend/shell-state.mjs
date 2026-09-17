const PUBLIC_STATES = Object.freeze([
  "loading",
  "ready",
  "unauthenticated",
  "forbidden",
  "revoked",
  "unavailable"
]);

export function presentShell(view) {
  const state = PUBLIC_STATES.includes(view?.state) ? view.state : "unavailable";
  if (state === "ready") {
    if (
      typeof view?.tenant_id !== "string" || !view.tenant_id ||
      typeof view?.principal_id !== "string" || !view.principal_id ||
      typeof view?.admission_revision !== "string" || !view.admission_revision
    ) {
      return Object.freeze({
        state: "unavailable",
        message: "Current access cannot be verified right now.",
        tenantId: null
      });
    }
    return Object.freeze({
      state,
      message: "Access is current.",
      tenantId: view.tenant_id
    });
  }

  const messages = Object.freeze({
    loading: "Checking current access…",
    unauthenticated: "Sign in is required.",
    forbidden: "Current access is not admitted.",
    revoked: "Current access changed. Sign in again.",
    unavailable: "Current access cannot be verified right now."
  });
  return Object.freeze({state, message: messages[state], tenantId: null});
}

export {PUBLIC_STATES};
