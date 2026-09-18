const root = document.querySelector("#g4-metrics");
const state = document.querySelector("#state");
const definitions = document.querySelector("#definitions");
const current = document.querySelector("#current");
const history = document.querySelector("#history");
const completeness = document.querySelector("#completeness");
const historyItems = document.querySelector("#history-items");

function cookie(name) {
  const prefix = name + "=";
  const found = document.cookie.split(";").map((x) => x.trim()).find((x) => x.startsWith(prefix));
  return found ? decodeURIComponent(found.slice(prefix.length)) : null;
}

const params = new URLSearchParams(window.location.search);
const tenant = params.get("tenant") || "tenant-a";
const resource = params.get("resource") || "resource-101";
const caseName = cookie("jlmirror_g4_case") || "success";

async function readJson(url) {
  const response = await fetch(url, {
    method: "GET",
    credentials: "same-origin",
    headers: {"Accept": "application/json"},
    cache: "no-store",
  });
  return {response, body: await response.json()};
}

function textValue(value) {
  return value === null ? "no value" : JSON.stringify(value);
}

async function main() {
  const definitionUrl =
    `/api/v1/tenants/${encodeURIComponent(tenant)}/metric-definitions?monitoring_resource_id=${encodeURIComponent(resource)}`;
  const currentUrl =
    `/api/v1/tenants/${encodeURIComponent(tenant)}/metric-current-states?monitoring_resource_id=${encodeURIComponent(resource)}`;

  const [defs, values] = await Promise.all([readJson(definitionUrl), readJson(currentUrl)]);

  if (caseName === "revoked" || caseName === "cross-tenant") {
    if (defs.response.status === 403 && values.response.status === 403) {
      root.dataset.e2eResult = "g4-" + caseName + "-pass";
      state.textContent = "forbidden";
      return;
    }
    root.dataset.e2eResult = "fail";
    return;
  }

  if (defs.response.status !== 200 || values.response.status !== 200) {
    root.dataset.e2eResult = "fail";
    state.textContent = "unavailable";
    return;
  }

  definitions.replaceChildren();
  current.replaceChildren();

  for (const item of defs.body.items) {
    const li = document.createElement("li");
    li.textContent = `${item.name} [${item.value_kind}] ${item.unit ?? ""}`;
    definitions.append(li);
  }

  for (const item of values.body.items) {
    const li = document.createElement("li");
    li.textContent = `${item.metric_definition_id}: ${textValue(item.value)} (${item.evidence_state})`;
    current.append(li);
  }

  if (caseName === "history") {
    const from = "2026-09-18T05:00:00Z";
    const to = "2026-09-18T06:00:00Z";
    const observed = await readJson(
      `/api/v1/tenants/${encodeURIComponent(tenant)}/metric-observations?metric_definition_id=metric-cpu&from=${encodeURIComponent(from)}&to=${encodeURIComponent(to)}`
    );
    if (observed.response.status !== 200) {
      root.dataset.e2eResult = "fail";
      return;
    }
    history.hidden = false;
    completeness.textContent = observed.body.completeness.state;
    historyItems.replaceChildren();
    for (const item of observed.body.items) {
      const li = document.createElement("li");
      li.textContent = `${item.observed_at}: ${textValue(item.value)}`;
      historyItems.append(li);
    }
    const valid =
      observed.body.metric_definition_id === "metric-cpu" &&
      observed.body.completeness.state === "complete" &&
      observed.body.items.length === 2;
    root.dataset.e2eResult = valid ? "g4-history-pass" : "fail";
    return;
  }

  const missingZero = values.body.items.some((item) => item.value === 0 && item.current_observation_id === null);
  const leakedHealth = document.body.textContent.toLowerCase().includes("healthy");
  root.dataset.e2eResult = !missingZero && !leakedHealth ? "g4-success-pass" : "fail";
  state.textContent = `${defs.body.items.length} metric definition(s)`;
}

main().catch(() => {
  state.textContent = "unavailable";
  root.dataset.e2eResult = "fail";
});
