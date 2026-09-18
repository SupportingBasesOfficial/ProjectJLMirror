const root = document.querySelector("#g3-inventory");
const state = document.querySelector("#state");
const list = document.querySelector("#resources");
const detail = document.querySelector("#detail");
const detailJson = document.querySelector("#detail-json");

function cookie(name) {
  const prefix = name + "=";
  const found = document.cookie.split(";").map((x) => x.trim()).find((x) => x.startsWith(prefix));
  return found ? decodeURIComponent(found.slice(prefix.length)) : null;
}

const tenant = new URLSearchParams(window.location.search).get("tenant") || "tenant-a";
const caseName = cookie("jlmirror_g3_case") || "success";

async function readJson(url) {
  const response = await fetch(url, {
    method: "GET",
    credentials: "same-origin",
    headers: {"Accept": "application/json"},
    cache: "no-store",
  });
  const body = await response.json();
  return {response, body};
}

function resourceLabel(item) {
  const stateText = item.presence_state === "present" ? "present" : "removed";
  return `${item.display_name} — host — ${stateText}`;
}

async function openDetail(id) {
  const observed = await readJson(
    `/api/v1/tenants/${encodeURIComponent(tenant)}/monitoring-resources/${encodeURIComponent(id)}`
  );
  if (observed.response.status !== 200) throw new Error("detail-" + observed.response.status);
  detail.hidden = false;
  detailJson.textContent = JSON.stringify(observed.body, null, 2);
  return observed.body;
}

async function main() {
  const observed = await readJson(
    `/api/v1/tenants/${encodeURIComponent(tenant)}/monitoring-resources`
  );

  if (caseName === "revoked" || caseName === "cross-tenant") {
    if (observed.response.status === 403) {
      root.dataset.e2eResult = "g3-" + caseName + "-pass";
      state.textContent = "forbidden";
      return;
    }
    root.dataset.e2eResult = "fail";
    return;
  }

  if (observed.response.status !== 200) {
    state.textContent = observed.body.state || "unavailable";
    root.dataset.e2eResult = "fail";
    return;
  }

  list.replaceChildren();
  if (!observed.body.items.length) {
    state.textContent = "No resources are currently visible for this tenant.";
    root.dataset.e2eResult = "fail";
    return;
  }

  state.textContent = `${observed.body.items.length} current resource(s)`;
  for (const item of observed.body.items) {
    const li = document.createElement("li");
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = resourceLabel(item);
    button.addEventListener("click", () => {
      openDetail(item.monitoring_resource_id).catch((error) => {
        state.textContent = error.message;
      });
    });
    li.append(button);
    list.append(li);
  }

  if (caseName === "detail") {
    const value = await openDetail("resource-101");
    if (
      value.monitoring_resource_id === "resource-101" &&
      value.resource_kind === "host" &&
      value.external_references?.provider_object_kind === "zabbix_host" &&
      value.external_references?.provider_external_ref === "101"
    ) {
      root.dataset.e2eResult = "g3-detail-pass";
      return;
    }
    root.dataset.e2eResult = "fail";
    return;
  }

  const leaked = observed.body.items.some((item) => Object.hasOwn(item, "external_references"));
  root.dataset.e2eResult = leaked ? "fail" : "g3-success-pass";
}

main().catch(() => {
  state.textContent = "unavailable";
  root.dataset.e2eResult = "fail";
});
