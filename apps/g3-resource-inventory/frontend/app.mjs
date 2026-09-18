const state = document.querySelector("#state");
const list = document.querySelector("#resources");
const detail = document.querySelector("#detail");
const detailJson = document.querySelector("#detail-json");

const tenant = new URLSearchParams(window.location.search).get("tenant") || "tenant-a";

async function readJson(url) {
  const response = await fetch(url, {
    method: "GET",
    credentials: "same-origin",
    headers: {"Accept": "application/json"},
    cache: "no-store",
  });
  if (response.status === 401) throw new Error("unauthenticated");
  if (response.status === 403) throw new Error("forbidden");
  if (!response.ok) throw new Error("unavailable");
  return response.json();
}

function resourceLabel(item) {
  const stateText = item.presence_state === "present" ? "present" : "removed";
  return `${item.display_name} — host — ${stateText}`;
}

async function openDetail(id) {
  const value = await readJson(
    `/api/v1/tenants/${encodeURIComponent(tenant)}/monitoring-resources/${encodeURIComponent(id)}`
  );
  detail.hidden = false;
  detailJson.textContent = JSON.stringify(value, null, 2);
}

async function load() {
  try {
    const value = await readJson(
      `/api/v1/tenants/${encodeURIComponent(tenant)}/monitoring-resources`
    );
    list.replaceChildren();
    if (!value.items.length) {
      state.textContent = "No resources are currently visible for this tenant.";
      return;
    }
    state.textContent = `${value.items.length} current resource(s)`;
    for (const item of value.items) {
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
  } catch (error) {
    state.textContent = error.message;
  }
}

load();
