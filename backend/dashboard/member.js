"use strict";
const $ = (id) => document.getElementById(id);
let token = null, timer = null, busy = false, generation = 0, selectedRace = "", refreshPending = false;
function clearSession(message = "") {
  generation += 1; token = null; refreshPending = false; clearTimeout(timer); timer = null;
  $("workspace").hidden = true; $("login-panel").hidden = false;
  $("signout").hidden = true; $("login-error").textContent = message;
  $("login-form").reset(); selectedRace = "";
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
function leaderboardRow(e, position, unit, ranked = false) {
  const row = element("article", undefined, "leader-row");
  const head = element("button", undefined, "leader-main");
  head.type = "button";
  head.setAttribute("aria-expanded", "false");
  const number = element("span", String(position).padStart(2, "0"), "leader-position");
  const identity = element("span", undefined, "leader-identity");
  identity.append(element("strong", e.official_ring_number), element("small", new Date(e.arrival_at).toLocaleString()));
  const speed = element("span", undefined, "leader-speed");
  speed.append(element("strong", Number(e.display_speed).toFixed(2)), element("small", unit));
  const arrow = element("span", "⌄", "leader-chevron");
  arrow.setAttribute("aria-hidden", "true");
  head.append(number, identity, speed, arrow);
  const details = element("div", undefined, "leader-details");
  details.hidden = true;
  const fields = [
    ["Owner", e.owner_name],
    ["Distance", Number(e.distance_meters).toFixed(0) + " m"],
    ["Capture", e.capture_mode === "simulated" ? "SIMULATED — TEST ONLY" : e.capture_mode],
    ["Qualification", e.qualifying_status || "Pending review"],
    ["Result", "NOT OFFICIAL"]
  ];
  if (ranked) fields.unshift(["Leaderboard", e.leaderboard]);
  for (const [label, value] of fields) {
    const cell = element("div", undefined, "leader-detail");
    cell.append(element("small", label), element("strong", value == null ? "—" : value));
    details.append(cell);
  }
  head.addEventListener("click", () => {
    details.hidden = !details.hidden;
    head.setAttribute("aria-expanded", String(!details.hidden));
  });
  row.append(head, details);
  return row;
}
function drawStandings(data) {
  const arrivals = [...data.entries].sort((a,b) => a.arrival_order - b.arrival_order);
  const unit = data.speed_unit || "m/min";
  const ranked = [...data.entries].filter(e => e.rank != null).sort((a,b) =>
    a.leaderboard.localeCompare(b.leaderboard) || a.rank - b.rank);
  $("arrival-order").replaceChildren(...(arrivals.length ? arrivals.map(e =>
    leaderboardRow(e, e.arrival_order, unit)) :
    [element("p", "No eligible arrivals yet.", "muted empty-board")]));
  $("speed-ranking").replaceChildren(...(ranked.length ? ranked.map(e =>
    leaderboardRow(e, e.rank, unit, true)) :
    [element("p", "No qualifying speed rankings yet. Below-minimum arrivals remain visible in arrival order.", "muted empty-board")]));
  $("standings-status").textContent = data.possibly_truncated ?
    "Limited provisional preview · NOT OFFICIAL" :
    "Updated provisional results · " + data.arrived_entries + " arrivals · NOT OFFICIAL";
  $("leader-arrived").textContent = data.arrived_entries;
  $("leader-qualified").textContent = ranked.length;
  $("leader-fastest").textContent = arrivals.length ? Math.max(...arrivals.map(e => Number(e.display_speed))).toFixed(2) : "—";
  $("leader-unit").textContent = unit;
}

function draw(data) {
  $("welcome").textContent = "Welcome, " + data.full_name;
  const races = [...new Map(data.race_entries.map(e => [e.race_id, {id:e.race_id,name:e.race_name,status:e.race_status}])).values()];
  const select = $("standings-race");
  if (!races.some(r => r.id === selectedRace)) selectedRace = races.find(r => r.status === "active")?.id || races[0]?.id || "";
  select.replaceChildren(...races.map(r => {
    const option = element("option",r.name + " (" + r.status + ")");
    option.value = r.id; return option;
  }));
  select.value = selectedRace;
  $("pigeon-count").textContent = data.pigeons.length;
  $("active-count").textContent = data.race_entries.filter(e => e.race_status === "active").length;
  $("scan-count").textContent = data.race_entries.filter(e => e.first_unrejected_scan_at).length;
  const birds = data.pigeons.map(p => item(p.name || p.official_ring_number, [
    ["Ring", p.official_ring_number], ["Loft", p.loft_name],
    ["RFID", p.has_active_rfid ? "Registered" : "Not registered"], ["Status", p.status]
  ]));
  const entryCards = data.race_entries.map(e => item(e.race_name, [
    ["Ring", e.official_ring_number], ["Race", e.race_status],
    ["Clocking", e.first_unrejected_scan_at ? "Scan detected (provisional)" : "No scan recorded"],
    ["Detected at", e.first_unrejected_scan_at ? new Date(e.first_unrejected_scan_at).toLocaleString() : "—"]
  ]));
  $("pigeons").replaceChildren(...(birds.length ? birds : [element("p","No pigeons registered yet.","muted")]));
  $("entries").replaceChildren(...(entryCards.length ? entryCards : [element("p","No race entries yet.","muted")]));
}
async function refresh() {
  if (!token) return;
  if (busy) { refreshPending = true; return; }
  busy = true;
  const current = generation;
  try {
    const data = await request("/member/overview");
    if (current !== generation) return;
    draw(data);
    const requestedRace = selectedRace;
    if (requestedRace) {
      try {
        const standings = await request("/member/races/" + encodeURIComponent(requestedRace) + "/standings");
        if (current !== generation || requestedRace !== selectedRace) return;
        drawStandings(standings);
      } catch (err) {
        if (current === generation && requestedRace === selectedRace) $("standings-status").textContent = "Standings unavailable: " + err.message;
      }
    } else {
      $("arrival-order").replaceChildren();
      $("speed-ranking").replaceChildren();
      $("standings-status").textContent = "No race entries yet.";
    }
    $("sync-status").textContent = "Updated " + new Date().toLocaleTimeString();
  } catch (err) {
    if (current === generation) $("sync-status").textContent = "Update failed: " + err.message;
  } finally {
    busy = false;
    if (current === generation && token) {
      if (refreshPending) { refreshPending = false; queueMicrotask(refresh); }
      else timer = setTimeout(refresh, 15000);
    }
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

$("standings-race").addEventListener("change", (event) => {
  selectedRace = event.target.value;
  $("arrival-order").replaceChildren();
  $("speed-ranking").replaceChildren();
  $("standings-status").textContent = "Loading selected race standings…";
  clearTimeout(timer);
  refresh();
});
