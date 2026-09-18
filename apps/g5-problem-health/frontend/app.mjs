const root=document.querySelector("#g5-problem-health");
const state=document.querySelector("#state");
const problems=document.querySelector("#problems");
const health=document.querySelector("#health");

function cookie(name){
  const prefix=name+"=";
  const found=document.cookie.split(";").map(x=>x.trim()).find(x=>x.startsWith(prefix));
  return found?decodeURIComponent(found.slice(prefix.length)):null;
}

const params=new URLSearchParams(window.location.search);
const tenant=params.get("tenant")||"tenant-a";
const resource=params.get("resource")||"resource-101";
const caseName=cookie("jlmirror_g5_case")||"active";

async function readJson(url){
  const response=await fetch(url,{method:"GET",credentials:"same-origin",headers:{"Accept":"application/json"},cache:"no-store"});
  return {response,body:await response.json()};
}

async function main(){
  const problemUrl=`/api/v1/tenants/${encodeURIComponent(tenant)}/problems?monitoring_resource_id=${encodeURIComponent(resource)}`;
  const healthUrl=`/api/v1/tenants/${encodeURIComponent(tenant)}/health-projections`;
  const [ps,hs]=await Promise.all([readJson(problemUrl),readJson(healthUrl)]);

  if(caseName==="revoked"||caseName==="cross-tenant"){
    if(ps.response.status===403&&hs.response.status===403){
      root.dataset.e2eResult="g5-"+caseName+"-pass";
      state.textContent="forbidden";
      return;
    }
    root.dataset.e2eResult="fail";
    return;
  }

  if(ps.response.status!==200||hs.response.status!==200){
    root.dataset.e2eResult="fail";
    state.textContent="unavailable";
    return;
  }

  problems.replaceChildren();
  for(const item of ps.body.items){
    const li=document.createElement("li");
    li.textContent=`${item.summary} — ${item.problem_state} — ${item.severity_class} — ${item.evidence_state}`;
    problems.append(li);
  }

  health.replaceChildren();
  for(const item of hs.body.items){
    const li=document.createElement("li");
    li.textContent=`${item.monitoring_resource_id} — ${item.health_class} — ${item.evidence_state}`;
    health.append(li);
  }

  if(caseName==="resolved"){
    const ok=ps.body.items.some(item=>item.problem_id==="problem-2"&&item.problem_state==="resolved"&&item.resolved_at!==null);
    root.dataset.e2eResult=ok?"g5-resolved-pass":"fail";
    return;
  }

  if(caseName==="health"){
    const ok=hs.body.items.some(item=>
      item.monitoring_resource_id==="resource-101"&&
      item.health_class==="degraded"&&
      item.evidence_state==="current"&&
      item.problem_refs.includes("problem-1")
    );
    root.dataset.e2eResult=ok?"g5-health-pass":"fail";
    return;
  }

  const active=ps.body.items.some(item=>
    item.problem_id==="problem-1"&&item.problem_state==="active"&&item.resolved_at===null
  );
  const forbiddenAck=document.body.textContent.includes("JLMirror ACK");
  root.dataset.e2eResult=active&&!forbiddenAck?"g5-active-pass":"fail";
  state.textContent=`${ps.body.items.length} problem(s)`;
}

main().catch(()=>{
  state.textContent="unavailable";
  root.dataset.e2eResult="fail";
});
