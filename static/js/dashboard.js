/* Dashboard page. Relies on helpers from app.js. */
async function loadDashboard() {
  try {
    const d = await api("/api/dashboard");
    $("#dashState").hidden = true; $("#dash").hidden = false;
    const kpi = (n, l, cls = "") => `<div class="card kpi ${cls}"><div class="n">${n}</div><div class="l">${l}</div></div>`;
    $("#kpis").innerHTML = kpi(d.total, "Monitored candidates") + kpi(d.levels.High, "High risk", "high") + kpi(d.levels.Medium, "Medium risk", "med") +
      kpi(d.levels.Low, "Low risk", "low") + kpi(d.social.total, `Social findings (${d.social.high} high)`) + kpi(d.apps.total, `App findings (${d.apps.high} high)`);
    $("#sampleNote").textContent = d.sample_records ? `${d.sample_records} record(s) are SAMPLE data, not live monitoring.` : "";
    $("#brandBox").innerHTML = d.brand
      ? `<dl class="dl"><dt>Name</dt><dd>${esc(d.brand.name)}</dd><dt>Website</dt><dd>${esc(d.brand.website) || "-"}</dd><dt>Handles</dt><dd>${esc(d.brand.handles.map((h) => "@" + h).join(", ")) || "-"}</dd><dt>App</dt><dd>${esc(d.brand.app_name) || "-"} ${esc(d.brand.app_id)}</dd><dt>Developer</dt><dd>${esc(d.brand.developer) || "-"}</dd></dl><a href="/brand">Edit profile</a>`
      : '<p class="muted">No brand profile yet.</p><a class="btn" href="/brand">Create brand profile</a>';
    const b = d.blockchain;
    $("#chainBox").innerHTML = `${b.configured ? '<span class="badge ok">Configured</span>' : '<span class="badge none">Blockchain Not Configured</span>'}<p class="muted">${b.configured ? `Network: ${esc(b.chain)}` : "Local SHA-256 verification works without blockchain. See README to deploy the contract."}</p>`;
    $("#statusBox").innerHTML = Object.entries(d.statuses).map(([k, v]) => `<div style="display:flex;justify-content:space-between;padding:.3rem 0"><span>${k}</span><b>${v}</b></div>`).join("");
    const e = d.evidence;
    $("#evBox").innerHTML = `<div style="display:flex;justify-content:space-between"><span>Saved</span><b>${e.total}</b></div><div style="display:flex;justify-content:space-between"><span>Verified intact</span><b>${e.intact}</b></div><div style="display:flex;justify-content:space-between"><span>Tampered</span><b style="color:var(--high)">${e.tampered}</b></div><div style="display:flex;justify-content:space-between"><span>Not yet verified</span><b>${e.unverified}</b></div>`;
    $("#activity").innerHTML = d.activity.length ? d.activity.map((a) => `<li>${esc(a.message)} <span class="muted">- ${fmt(a.created_at)}</span></li>`).join("") : '<li class="muted">No activity yet.</li>';
  } catch (err) { $("#dashState").className = "state err"; $("#dashState").textContent = errText(err); }
}
document.addEventListener("DOMContentLoaded", () => {
  $("#seedBtn").addEventListener("click", (ev) => withBusy(ev.target, async () => {
    try { const r = await api("/api/demo/seed", { method: "POST" }); toast(r.seeded ? `Loaded ${r.social} social + ${r.app} app SAMPLE records` : r.message, "ok"); loadDashboard(); }
    catch (e) { toast(errText(e), "err"); }
  }));
  loadDashboard();
});
