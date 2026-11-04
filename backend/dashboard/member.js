"use strict";
const $ = (id) => document.getElementById(id);
let token = null, timer = null, busy = false, generation = 0;
function clearSession(message = "") {
  generation += 1; token = null; clearTimeout(timer); timer = null;
  $("workspace").hidden = true; $("login-panel").hidden = false;
  $("signout").hidden = true; $("login-error").textContent = message;
  $("login-form").reset();
}
async function request(path, options = {}) {
  const response = await fetch(path, { ...options, cache:"no-store", credentials:"omit",
    headers:{"Content-Type":"application/json", ...(token ? {Authorization:"Bearer " + token}: {})} });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    if (response.status === 401 && token) clearSession("Session expired. Please sign in again.");
    throw new Error(typeof data.detail === "string" ? data.detail : "Request failed (" + response.status + ")");
  }
  return data;
}
function element(tag, text, className) {
  const node = document.createElement(tag);
  if (text !== undefined) node.textContent = String(text);
  if (className) node.className = className;
  return node;
}
function item(title, lines) {
  const card = element("article", undefined, "item");
  card.append(element("h3", title));
  for (const [label, value] of lines) card.append(element("p", label + ": " + value));
  return card;
}
function draw(data) {
  $("welcome").textContent = "Welcome, " + data.full_name;
  $("pigeon-count").textContent = data.pigeons.length;
  $("active-count").textContent = data.race_entries.filter(e => e.race_status === "active").length;
  $("scan-count").textContent = data.race_entries.filter(e => e.first_unrejected_scan_at).length;
  const birds = data.pigeons.map(p => item(p.name || p.official_ring_number, [
    ["Ring", p.official_ring_number], ["Loft", p.loft_name],
    ["RFID", p.has_active_rfid ? "Registered" : "Not registered"], ["Status", p.status]
  ]));
  const races = data.race_entries.map(e => item(e.race_name, [
    ["Ring", e.official_ring_number], ["Race", e.race_status],
    ["Clocking", e.first_unrejected_scan_at ? "Scan detected (provisional)" : "No scan recorded"],
    ["Detected at", e.first_unrejected_scan_at ? new Date(e.first_unrejected_scan_at).toLocaleString() : "—"]
  ]));
  $("pigeons").replaceChildren(...(birds.length ? birds : [element("p","No pigeons registered yet.","muted")]));
  $("entries").replaceChildren(...(races.length ? races : [element("p","No race entries yet.","muted")]));
}
async function refresh() {
  if (!token || busy) return;
  busy = true;
  const current = generation;
  try {
    const data = await request("/member/overview");
    if (current !== generation) return;
    draw(data); $("sync-status").textContent = "Updated " + new Date().toLocaleTimeString();
  } catch (err) {
    if (current === generation) $("sync-status").textContent = "Update failed: " + err.message;
  } finally {
    busy = false;
    if (current === generation && token) timer = setTimeout(refresh, 15000);
  }
}
$("login-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  $("login-error").textContent = "";
  const submit = event.currentTarget.querySelector("button");
  submit.disabled = true;
  try {
    const form = new FormData(event.currentTarget);
    const auth = await request("/auth/login", {method:"POST", body:JSON.stringify({
      email:form.get("email"),password:form.get("password")})});
    token = auth.access_token;
    const me = await request("/auth/me");
    if (me.role !== "member") { clearSession("This dashboard is for member accounts only."); return; }
    generation += 1;
    $("login-panel").hidden = true; $("workspace").hidden = false; $("signout").hidden = false;
    refresh();
  } catch (err) { $("login-error").textContent = err.message; }
  finally { submit.disabled = false; }
});
$("signout").addEventListener("click", () => clearSession());
$("refresh").addEventListener("click", () => {clearTimeout(timer);refresh();});
document.addEventListener("visibilitychange", () => {if (!document.hidden && token) {clearTimeout(timer);refresh();}});

function publicPanel(id) {
  $("login-panel").hidden = id !== "login-panel";
  $("apply-panel").hidden = id !== "apply-panel";
  $("status-panel").hidden = id !== "status-panel";
}
$("show-apply").addEventListener("click", async () => {
  $("apply-message").textContent = "";
  publicPanel("apply-panel");
  try {
    const clubs = await request("/membership/clubs");
    const select = $("apply-form").elements.namedItem("club_id");
    select.replaceChildren(...clubs.map(club => {
      const option = element("option", club.name); option.value = club.id; return option;
    }));
    if (!clubs.length) $("apply-message").textContent = "No racing clubs are accepting applications yet.";
  } catch (error) { $("apply-message").textContent = error.message; }
});
$("show-status").addEventListener("click", () => publicPanel("status-panel"));
document.querySelectorAll(".back-login").forEach(button =>
  button.addEventListener("click", () => publicPanel("login-panel")));
$("apply-form").addEventListener("submit", async event => {
  event.preventDefault();
  const button = event.currentTarget.querySelector('[type="submit"]');
  button.disabled = true;
  try {
    const payload = Object.fromEntries(new FormData(event.currentTarget));
    const data = await request("/membership/applications", {
      method: "POST", body: JSON.stringify(payload)
    });
    $("apply-message").textContent = data.message;
    event.currentTarget.reset();
  } catch (error) { $("apply-message").textContent = error.message; }
  finally { button.disabled = false; }
});
$("status-form").addEventListener("submit", async event => {
  event.preventDefault();
  const button = event.currentTarget.querySelector('[type="submit"]');
  button.disabled = true;
  try {
    const data = await request("/membership/status", {
      method: "POST", body: JSON.stringify(Object.fromEntries(new FormData(event.currentTarget)))
    });
    $("status-message").textContent = "Status: " + data.status +
      (data.reason ? ". Reason: " + data.reason : "") +
      (data.status === "approved" ? ". You can now sign in." : "");
  } catch (error) { $("status-message").textContent = error.message; }
  finally { button.disabled = false; }
});
