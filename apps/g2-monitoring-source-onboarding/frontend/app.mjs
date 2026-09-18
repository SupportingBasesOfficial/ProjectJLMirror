const root = document.getElementById("g2-onboarding");
const status = document.getElementById("g2-status");
const source = document.getElementById("g2-source");

function cookie(name) {
  const prefix = name + "=";
  const found = document.cookie.split(";").map((x) => x.trim()).find((x) => x.startsWith(prefix));
  return found ? decodeURIComponent(found.slice(prefix.length)) : null;
}

function render(view) {
  root.dataset.state = view.state || "unavailable";
  status.textContent = view.state || "unavailable";
  source.textContent = view.monitoring_source_id || "";
  return view;
}

async function createSource(tenantId, caseName) {
  const csrf = cookie("__Host-jlmirror_csrf");
  const response = await fetch(
    "/bff/v1/tenants/" + encodeURIComponent(tenantId) + "/monitoring-sources",
    {
      method: "POST",
      headers: {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Idempotency-Key": "browser-" + caseName,
        "X-JLMirror-CSRF": csrf || ""
      },
      body: JSON.stringify({
        provider_profile: "zabbix",
        display_name: "Primary Zabbix",
        provider_configuration: {base_url: "https://zabbix.example.test/zabbix"},
        credential_binding_ref: "provider-access-binding:fixture",
        configured_provider_scope: {host_group_refs: [caseName === "missing" ? "group-missing" : "group-linux"]}
      })
    }
  );
  return {response: response, body: await response.json()};
}

async function readSource(tenantId, sourceId) {
  const response = await fetch(
    "/bff/v1/tenants/" + encodeURIComponent(tenantId) + "/monitoring-sources/" + encodeURIComponent(sourceId) + "/status",
    {headers: {"Accept": "application/json"}}
  );
  return {response: response, body: await response.json()};
}

async function main() {
  const params = new URLSearchParams(location.search);
  const tenantId = params.get("tenant");
  const caseName = cookie("jlmirror_g2_case") || "success";
  if (!tenantId) {
    render({state: "unavailable"});
    root.dataset.e2eResult = "fail";
    return;
  }

  const created = await createSource(tenantId, caseName);
  if (caseName === "revoked" || caseName === "cross-tenant") {
    if (created.response.status === 403) {
      root.dataset.e2eResult = "g2-" + caseName + "-pass";
      return;
    }
    root.dataset.e2eResult = "fail";
    return;
  }
  if (created.response.status !== 201) {
    render(created.body);
    root.dataset.httpStatus = String(created.response.status);
    root.dataset.e2eResult = "create-" + String(created.response.status);
    return;
  }
  render(created.body);

  for (let i = 0; i < 60; i += 1) {
    const observed = await readSource(tenantId, created.body.monitoring_source_id);
    render(observed.body);
    if (caseName === "success" && observed.response.status === 200 && observed.body.state === "current" && observed.body.provider_connection_confirmed === true) {
      root.dataset.e2eResult = "g2-success-pass";
      return;
    }
    if (caseName === "missing" && observed.response.status === 200 && observed.body.state === "incomplete" && observed.body.provider_connection_confirmed === false) {
      root.dataset.e2eResult = "g2-missing-pass";
      return;
    }
    await new Promise((resolve) => setTimeout(resolve, 100));
  }
  root.dataset.e2eResult = "fail";
}

main().catch(() => {
  root.dataset.state = "unavailable";
  root.dataset.e2eResult = "fail";
});
