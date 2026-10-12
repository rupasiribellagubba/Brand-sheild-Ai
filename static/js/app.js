/* Shared helpers + page logic (brand, monitor, candidate, evidence). */
const $ = (s, r = document) => r.querySelector(s);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const STATUSES = ["New", "Under Review", "Confirmed Suspicious", "False Positive"];

async function api(url, opts = {}) {
  const o = { headers: {}, ...opts };
  if (o.body && !(o.body instanceof FormData)) { o.headers["Content-Type"] = "application/json"; o.body = JSON.stringify(o.body); }
  let r;
  try { r = await fetch(url, o); } catch { throw new Error("Network error: the server is unreachable."); }
  let d = {};
  try { d = await r.json(); } catch { /* non-JSON */ }
  if (!r.ok) { const e = new Error(d.error || `Request failed (${r.status})`); e.details = d.details || []; e.data = d; throw e; }
  return d;
}
function toast(msg, type = "") {
  const t = document.createElement("div"); t.className = "toast " + type; t.textContent = msg;
  $("#toasts").appendChild(t); setTimeout(() => t.remove(), 4500);
}
const errText = (e) => e.message + (e.details && e.details.length ? " - " + e.details.join(" ") : "");
const badge = (l) => `<span class="badge ${l ? l.toLowerCase() : "none"}">${esc(l || "-")}</span>`;
const sampleTag = (c) => (c.is_sample ? ' <span class="badge sample">SAMPLE</span>' : "");
const scoreBar = (c) => `<div style="display:flex;gap:.5rem;align-items:center"><b>${c.score ?? "-"}</b><div class="bar ${(c.level || "").toLowerCase()}" style="flex:1"><i style="width:${c.score || 0}%"></i></div></div>`;
const fmt = (iso) => (iso ? new Date(iso).toLocaleString() : "-");
const statusSelect = (c) => `<select data-status="${c.id}">${STATUSES.map((s) => `<option ${s === c.status ? "selected" : ""}>${s}</option>`).join("")}</select>`;
async function withBusy(btn, fn) { btn.disabled = true; try { return await fn(); } finally { btn.disabled = false; } }

/* ---------- Brand profile ---------- */
function initBrand() {
  const f = $("#brandForm");
  api("/api/brand").then(({ brand }) => { if (brand) for (const k of ["name", "website", "description", "social_handles", "app_name", "app_id", "developer"]) f.elements[k].value = brand[k] || ""; })
    .catch((e) => toast(errText(e), "err"));
  f.addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const btn = f.querySelector("button");
    await withBusy(btn, async () => {
      try {
        const r = await api("/api/brand", { method: "PUT", body: Object.fromEntries(new FormData(f)) });
        $("#formMsg").textContent = `Saved. ${r.reanalyzed} existing record(s) re-analyzed.`; toast("Brand profile saved", "ok");
      } catch (e) { $("#formMsg").textContent = ""; toast(errText(e), "err"); }
    });
  });
}

/* ---------- Monitor pages (social / apps) ---------- */
function initMonitor() {
  const root = $("#monitor"), kind = root.dataset.kind, isSocial = kind === "social", cols = isSocial ? 6 : 8;
  const rows = $("#rows");
  const row = (c) => isSocial
    ? `<tr><td><b>${esc(c.name)}</b>${sampleTag(c)}<br><span class="muted">@${esc((c.username || "").replace(/^@/, ""))}</span></td><td>${esc(c.platform)}</td><td>${scoreBar(c)}</td><td>${badge(c.level)}</td><td>${statusSelect(c)}</td><td><a href="/candidate/${c.id}">Inspect</a></td></tr>`
    : `<tr><td><b>${esc(c.name)}</b>${sampleTag(c)}</td><td>${esc(c.developer) || '<span class="muted">not provided</span>'}</td><td>${esc(c.app_id) || '<span class="muted">-</span>'}</td><td>${esc(c.source)}</td><td>${scoreBar(c)}</td><td>${badge(c.level)}</td><td>${statusSelect(c)}</td><td><a href="/candidate/${c.id}">Inspect</a></td></tr>`;

  async function load() {
    rows.innerHTML = `<tr><td colspan="${cols}" class="state">Loading&hellip;</td></tr>`;
    const qs = new URLSearchParams({ q: $("#q").value, level: $("#fLevel").value, status: $("#fStatus").value, sort: $("#fSort").value });
    try {
      const { items } = await api(`/api/${kind}/candidates?${qs}`);
      rows.innerHTML = items.length ? items.map(row).join("") : `<tr><td colspan="${cols}" class="state">No records found. Add a candidate, import a CSV, or load sample data from the dashboard.</td></tr>`;
    } catch (e) { rows.innerHTML = `<tr><td colspan="${cols}" class="state err">${esc(errText(e))}</td></tr>`; }
  }
  let t; $("#q").addEventListener("input", () => { clearTimeout(t); t = setTimeout(load, 250); });
  for (const id of ["#fLevel", "#fStatus", "#fSort"]) $(id).addEventListener("change", load);

  rows.addEventListener("change", async (ev) => {
    const sel = ev.target.closest("select[data-status]"); if (!sel) return;
    try { await api(`/api/candidates/${sel.dataset.status}/status`, { method: "PATCH", body: { status: sel.value } }); toast("Status updated", "ok"); }
    catch (e) { toast(errText(e), "err"); load(); }
  });

  $("#addForm").addEventListener("submit", async (ev) => {
    ev.preventDefault(); const f = ev.target;
    await withBusy(f.querySelector("button"), async () => {
      $("#addMsg").textContent = "Analyzing...";
      try {
        const c = await api(`/api/${kind}/candidates`, { method: "POST", body: Object.fromEntries(new FormData(f)) });
        $("#addMsg").textContent = `Scored ${c.score}/100 (${c.level}).`; toast("Candidate analyzed and saved", "ok"); f.reset(); load();
      } catch (e) { $("#addMsg").textContent = ""; toast(errText(e), "err"); }
    });
  });

  $("#csvForm").addEventListener("submit", async (ev) => {
    ev.preventDefault(); const f = ev.target, file = f.elements.file.files[0], out = $("#csvResult");
    if (!file) return;
    if (!file.name.toLowerCase().endsWith(".csv")) { out.innerHTML = '<div class="alert err">Please choose a .csv file.</div>'; return; }
    if (file.size > 1024 * 1024) { out.innerHTML = '<div class="alert err">File exceeds the 1 MB limit.</div>'; return; }
    await withBusy(f.querySelector("button"), async () => {
      out.innerHTML = '<div class="state">Uploading&hellip;</div>';
      try {
        const r = await api(`/api/${kind}/import`, { method: "POST", body: new FormData(f) });
        const errs = r.errors.map((x) => `<li>Row ${x.row}: ${esc(x.error)}</li>`).join("");
        out.innerHTML = `<div class="alert ok">Imported ${r.imported} record(s); ${r.skipped} rejected.</div>${errs ? `<ul class="notes">${errs}</ul>` : ""}`;
        toast(`Imported ${r.imported} record(s)`, "ok"); f.reset(); load();
      } catch (e) { out.innerHTML = `<div class="alert err">${esc(errText(e))}</div>`; }
    });
  });
  load();
}

/* ---------- Candidate detail ---------- */
function initCandidate() {
  const id = $("#candidate").dataset.id;
  let cand;
  const render = () => {
    const c = cand;
    $("#backLink").href = c.kind === "social" ? "/social" : "/apps";
    $("#cName").textContent = c.name; $("#cBadges").innerHTML = badge(c.level) + sampleTag(c);
    const fields = c.kind === "social"
      ? [["Type", "Social profile"], ["Username", c.username], ["Platform", c.platform], ["URL", c.url], ["Description", c.description]]
      : [["Type", "Mobile app"], ["Developer", c.developer], ["App ID", c.app_id], ["Source", c.source], ["URL", c.url], ["Description", c.description]];
    $("#cFields").innerHTML = fields.map(([k, v]) => `<dt>${k}</dt><dd>${esc(v) || '<span class="muted">not provided</span>'}</dd>`).join("");
    $("#scoreBox").innerHTML = `<div class="big-score">${c.score}<small class="muted">/100</small></div>${scoreBar(c)}<p class="muted">Score reflects similarity signals, not confirmed fraud.</p>`;
    const sel = $("#statusSel"); sel.innerHTML = STATUSES.map((s) => `<option ${s === c.status ? "selected" : ""}>${s}</option>`).join("");
    $("#indicators").innerHTML = c.indicators.length ? c.indicators.map((i) => `<div class="ind"><div class="top"><span>${esc(i.label)}${i.available ? "" : ' <span class="badge none">not scored</span>'}</span><span>+${i.contribution} / ${i.weight}</span></div><div class="bar"><i style="width:${i.weight ? (i.contribution / i.weight) * 100 : 0}%"></i></div><small>${esc(i.detail)}</small></div>`).join("") : '<p class="muted">No indicators available.</p>';
    $("#notes").innerHTML = c.notes.map((n) => `<li>${esc(n)}</li>`).join("");
    if (c.summary) $("#summary").textContent = c.summary;
    $("#evList").innerHTML = c.evidence.length ? c.evidence.map((e) => `<li><a href="/evidence">${esc(e.evidence_id)}</a> - <span class="hash">${esc(e.sha256.slice(0, 16))}&hellip;</span> (${fmt(e.created_at)})</li>`).join("") : "<li>No evidence saved yet.</li>";
  };
  async function load() {
    try { cand = await api(`/api/candidates/${id}`); $("#state").hidden = true; $("#detail").hidden = false; render(); }
    catch (e) { $("#state").className = "state err"; $("#state").textContent = errText(e); }
  }
  $("#statusSel").addEventListener("change", async (ev) => {
    try { await api(`/api/candidates/${id}/status`, { method: "PATCH", body: { status: ev.target.value } }); toast("Status updated", "ok"); }
    catch (e) { toast(errText(e), "err"); }
  });
  $("#sumBtn").addEventListener("click", (ev) => withBusy(ev.target, async () => {
    $("#sumMsg").textContent = "Generating...";
    try { const r = await api(`/api/candidates/${id}/summary`, { method: "POST" }); $("#summary").textContent = r.summary; $("#sumMsg").textContent = `Source: ${r.source}.${r.warning ? " " + r.warning : ""}`; }
    catch (e) { $("#sumMsg").textContent = ""; toast(errText(e), "err"); }
  }));
  $("#evBtn").addEventListener("click", (ev) => withBusy(ev.target, async () => {
    try { const e = await api("/api/evidence", { method: "POST", body: { candidate_id: Number(id) } }); toast(`Saved ${e.evidence_id}`, "ok"); load(); }
    catch (e) { toast(errText(e), "err"); }
  }));
  load();
}

/* ---------- Evidence vault ---------- */
function initEvidence() {
  const rows = $("#rows");
  async function loadChain() {
    try {
      const s = await api("/api/blockchain/status?check=1");
      $("#chainStatus").innerHTML = `<b>Blockchain:</b> ${badge(s.configured ? (s.connected === false ? "high" : "low") : "none").replace(/>[^<]*</, `>${esc(s.label)}<`)} ` +
        (s.configured ? `<span class="muted">Network: ${esc(s.chain)} | Contract: <span class="hash">${esc(s.contract_address)}</span></span>` : `<span class="muted">Local SHA-256 verification still works. Missing: ${esc(s.missing.join(", ") || "web3 package")}.</span>`) +
        (s.error ? `<div class="alert err">${esc(s.error)}</div>` : "");
    } catch (e) { $("#chainStatus").innerHTML = `<span class="state err">${esc(errText(e))}</span>`; }
  }
  const chainCell = (e) => !e.blockchain ? '<span class="muted">Not submitted</span>'
    : e.blockchain.status === "confirmed" ? `${badge("low").replace(/>[^<]*</, ">confirmed<")}<br><span class="hash" title="${esc(e.blockchain.tx_hash)}">${esc(e.blockchain.tx_hash.slice(0, 14))}&hellip;</span>`
    : `<span class="badge bad">failed</span><br><span class="muted">${esc((e.blockchain.error || "").slice(0, 80))}</span>`;
  const localCell = (e) => !e.last_verification ? '<span class="muted">Not verified</span>'
    : `<span class="badge ${e.last_verification.result === "intact" ? "ok" : "bad"}">${e.last_verification.result}</span><br><span class="muted">${fmt(e.last_verification.verified_at)}</span>`;
  async function load() {
    try {
      const { items } = await api("/api/evidence");
      rows.innerHTML = items.length ? items.map((e) => `<tr><td><b>${esc(e.evidence_id)}</b></td><td><a href="/candidate/${e.candidate_id}">${esc(e.candidate_name || "#" + e.candidate_id)}</a></td><td><span class="hash" title="${esc(e.sha256)}">${esc(e.sha256.slice(0, 20))}&hellip;</span></td><td>${fmt(e.created_at)}</td><td>${localCell(e)}</td><td>${chainCell(e)}<div id="cc-${esc(e.evidence_id)}"></div></td><td><button class="btn sm" data-act="verify" data-id="${esc(e.evidence_id)}">Verify</button> <button class="btn sm secondary" data-act="chain" data-id="${esc(e.evidence_id)}">Send to chain</button> <button class="btn sm secondary" data-act="check" data-id="${esc(e.evidence_id)}">Check chain</button></td></tr>`).join("")
        : '<tr><td colspan="7" class="state">No evidence saved yet. Open a candidate and choose "Save snapshot to Evidence Vault".</td></tr>';
    } catch (e) { rows.innerHTML = `<tr><td colspan="7" class="state err">${esc(errText(e))}</td></tr>`; }
  }
  rows.addEventListener("click", (ev) => {
    const b = ev.target.closest("button[data-act]"); if (!b) return;
    const id = b.dataset.id;
    withBusy(b, async () => {
      try {
        if (b.dataset.act === "verify") {
          const r = await api(`/api/evidence/${id}/verify`, { method: "POST" });
          toast(r.result === "intact" ? "Local check: evidence is intact" : "WARNING: local hash mismatch - evidence changed", r.result === "intact" ? "ok" : "err"); load();
        } else if (b.dataset.act === "chain") {
          const r = await api(`/api/evidence/${id}/blockchain`, { method: "POST" }); toast(`Transaction ${r.status}`, "ok"); load();
        } else {
          const r = await api(`/api/evidence/${id}/chain-check`);
          $(`#cc-${CSS.escape(id)}`).innerHTML = `<small class="muted">${r.recorded ? (r.matches_local ? "On-chain hash matches local" : "On-chain hash DIFFERS") : esc(r.message)}</small>`;
        }
      } catch (e) { toast(errText(e), "err"); load(); }
    });
  });
  loadChain(); load();
}

document.addEventListener("DOMContentLoaded", () => {
  const page = document.body.dataset.page;
  ({ brand: initBrand, monitor: initMonitor, candidate: initCandidate, evidence: initEvidence }[page] || (() => {}))();
});
