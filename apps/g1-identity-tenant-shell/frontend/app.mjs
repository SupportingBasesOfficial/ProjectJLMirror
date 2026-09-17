import {presentShell} from "./shell-state.mjs";

const root = document.getElementById("jlmirror-shell");
const status = document.getElementById("shell-status");
const tenant = document.getElementById("tenant-context");
const tenantId = document.getElementById("tenant-id");

function render(view) {
  const presentation = presentShell(view);
  root.dataset.state = presentation.state;
  status.textContent = presentation.message;
  tenant.hidden = presentation.tenantId === null;
  tenantId.textContent = presentation.tenantId ?? "";
  return presentation;
}

function singleCookie(name) {
  const values = document.cookie
    .split(";")
    .map((part) => part.trim())
    .filter((part) => part.startsWith(name + "="))
    .map((part) => decodeURIComponent(part.slice(name.length + 1)));
  return values.length === 1 ? values[0] : null;
}

async function loadShell(requestedTenant) {
  if (typeof requestedTenant !== "string" || requestedTenant.length === 0) {
    return render({state: "unavailable"});
  }
  try {
    const response = await fetch(
      `/bff/v1/tenants/${encodeURIComponent(requestedTenant)}/shell`,
      {credentials: "same-origin", headers: {"Accept": "application/json"}}
    );
    const body = await response.json();
    return render(body);
  } catch {
    return render({state: "unavailable"});
  }
}

async function exerciseScenario() {
  const params = new URLSearchParams(window.location.search);
  const requestedTenant = params.get("tenant");
  const scenario = params.get("scenario") ?? "allowed";
  const initial = await loadShell(requestedTenant);

  if (scenario === "allowed" && initial.state === "ready" && initial.tenantId === requestedTenant) {
    root.dataset.e2eResult = "allowed-pass";
    return;
  }
  if (scenario === "cross-tenant" && initial.state === "forbidden" && initial.tenantId === null) {
    root.dataset.e2eResult = "cross-tenant-pass";
    return;
  }
  if (scenario === "revoked" && initial.state === "revoked" && initial.tenantId === null) {
    root.dataset.e2eResult = "revoked-pass";
    return;
  }
  if (scenario === "csrf-reject" && initial.state === "ready") {
    const response = await fetch("/bff/v1/logout", {
      method: "POST",
      credentials: "same-origin",
      headers: {"Content-Type": "application/json"},
      body: "{}"
    });
    const after = await loadShell(requestedTenant);
    if (response.status === 403 && after.state === "ready") {
      root.dataset.e2eResult = "csrf-reject-pass";
      return;
    }
  }
  if (scenario === "logout" && initial.state === "ready") {
    const csrf = singleCookie("__Host-jlmirror_csrf");
    const response = await fetch("/bff/v1/logout", {
      method: "POST",
      credentials: "same-origin",
      headers: {
        "Content-Type": "application/json",
        "X-JLMirror-CSRF": csrf ?? ""
      },
      body: "{}"
    });
    const after = await loadShell(requestedTenant);
    if (response.status === 204 && after.state === "unauthenticated") {
      root.dataset.e2eResult = "logout-pass";
      return;
    }
  }

  root.dataset.e2eResult = "fail";
}

window.JLMirrorProtectedShell = Object.freeze({render, loadShell});
exerciseScenario();
