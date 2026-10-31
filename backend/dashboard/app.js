"use strict";

// Tokens live only in memory. Refreshing or closing the page signs out.
const $ = (selector) => document.querySelector(selector);
const state = { token: null, club: null, people: [], editing: null, timer: null,
  controller: new AbortController(), loading: false, loadError: false };

function message(text, failure = false) {
  $("#notice").textContent = text;
  $("#notice").classList.toggle("failure", failure);
  $("#notice").hidden = !text;
}

function signOut(reason = "") {
  stopLive();
  live.raceId = "";
  resetLive("Select a race to see its arrivals.");
  state.controller.abort();
  state.controller = new AbortController();
  clearTimeout(state.timer);
  Object.assign(state, { token: null, club: null, people: [], editing: null,
    loading: false, loadError: false });
  document.querySelectorAll("dialog").forEach((dialog) => {
    dialog.close();
    dialog.querySelector("form").reset();
  });
  $("#workspace").hidden = true;
  $("#login-screen").hidden = false;
  $("#member-rows").replaceChildren();
  $("#account-name").textContent = "";
  $("#login-form").reset();
  $("#login-error").textContent = reason;
  $("#login-form input").focus();
}

function errorText(data) {
  if (typeof data.detail === "string") return data.detail;
  if (Array.isArray(data.detail)) return data.detail.map((item) =>
    `${item.loc.filter((part) => part !== "body").join(" · ")}: ${item.msg}`).join("\n");
  return "The request could not be completed. Please try again.";
}

async function api(path, options = {}) {
  const token = state.token;
  const response = await fetch(path, {
    ...options, credentials: "omit", cache: "no-store", signal: state.controller.signal,
    headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}) },
  });
  let data = {};
  try { data = await response.json(); } catch { /* HTTP status still determines failure. */ }
  if (token && token !== state.token) throw new DOMException("Session changed", "AbortError");
  if (response.status === 401 && token && path !== "/auth/change-password") {
    signOut("Your session has expired. Please sign in again.");
    throw new DOMException("Session expired", "AbortError");
  }
  if (!response.ok) throw new Error(errorText(data));
  return data;
}

function post(path, data, method = "POST") {
  return api(path, { method, body: JSON.stringify(data) });
}

function formValues(form) { return Object.fromEntries(new FormData(form)); }

function openDialog(id) {
  const dialog = $(id);
  dialog.querySelector("form").reset();
  dialog.querySelector(".form-error").textContent = "";
  dialog.showModal();
}

document.querySelectorAll(".close-dialog").forEach((button) => {
  button.addEventListener("click", () => {
    const dialog = button.closest("dialog");
    dialog.close();
    dialog.querySelector("form").reset();
  });
});
document.querySelectorAll("dialog").forEach((dialog) => {
  dialog.addEventListener("close", () => dialog.querySelector("form").reset());
});

function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function renderPeople() {
  const query = $("#search").value.trim().toLocaleLowerCase();
  const role = $("#role-filter").value;
  const people = state.people.filter((person) =>
    (role === "all" || person.role_code === role) &&
    [person.full_name, person.email, person.phone].some((value) =>
      String(value || "").toLocaleLowerCase().includes(query)));
  const body = $("#member-rows");
  body.replaceChildren();
  for (const person of people) {
    const row = element("tr");
    const personCell = element("td");
    const personWrap = element("div", "person-cell");
    const initials = person.full_name.trim().split(/\s+/).slice(0, 2).map((name) => name[0]).join("").toUpperCase();
    const avatar = element("span", "avatar", initials || "?");
    avatar.setAttribute("aria-hidden", "true");
    const identity = element("div");
    identity.append(element("span", "person-name", person.full_name), element("span", "person-email", person.email));
    personWrap.append(avatar, identity);
    personCell.append(personWrap);
    const roleCell = element("td");
    roleCell.append(element("span", `badge ${person.role_code === "guest" ? "guest" : ""}`, person.role_code));
    const statusCell = element("td");
    statusCell.append(element("span", `status ${person.status === "active" ? "active" : ""}`, person.status));
    const actions = element("td");
    const edit = element("button", "edit-button", "Edit");
    edit.type = "button";
    edit.setAttribute("aria-label", `Edit ${person.full_name}`);
    edit.addEventListener("click", () => {
      state.editing = person.id;
      openDialog("#edit-dialog");
      $("#edit-form").elements.namedItem("full_name").value = person.full_name;
      $("#edit-form").elements.namedItem("phone").value = person.phone || "";
    });
    actions.append(edit);
    row.append(personCell, roleCell, element("td", "", person.phone || "—"), statusCell, actions);
    body.append(row);
  }
  $("#directory-count").textContent = String(state.people.length);
  $("#stat-total").textContent = state.loading || state.loadError ? "—" : String(state.people.length);
  for (const [key, kind] of [["members", "member"], ["guests", "guest"]]) {
    $(`#stat-${key}`).textContent = state.loading || state.loadError ? "—" : String(state.people.filter(
      (person) => person.role_code === kind && person.status === "active").length);
  }
  $("#directory-state").hidden = people.length > 0;
  $("#directory-state").textContent = state.loading ? "Loading your club…" : state.loadError ?
    "We couldn't load the directory. Select Refresh to try again." : !state.club ?
    "Create or join a club to manage participants." : state.people.length === 0 ?
    "Your directory is ready. Add your first member or link an existing account." : "No participants match your search.";
  $("#visible-count").textContent = state.loading ? "Loading…" : state.loadError ? "Directory unavailable" :
    `${people.length} of ${state.people.length} participants${state.people.length === 1000 ? " · First 1,000 records" : ""}`;
}

async function loadClub() {
  state.loading = true;
  state.loadError = false;
  state.people = [];
  $("#refresh-button").disabled = true;
  $("#add-member-button").disabled = true;
  $("#assign-button").disabled = true;
  renderPeople();
  try {
    const clubs = await api("/clubs");
    state.club = clubs[0] || null;
    $("#sidebar-club").textContent = state.club ? state.club.name : "No club assigned";
    $("#club-description").textContent = state.club ? `${state.club.name} · Manage the people behind every flight.` : "Manage the people behind every flight.";
    $("#club-setup").hidden = Boolean(state.club);
    if (state.club) state.people = await api(`/participants?club_id=${encodeURIComponent(state.club.id)}`);
    $("#add-member-button").disabled = !state.club;
    $("#assign-button").disabled = !state.club;
  } catch (error) {
    if (error.name !== "AbortError") {
      state.loadError = true;
      message(error.message || "Unable to reach the server.", true);
    }
  } finally {
    state.loading = false;
    $("#refresh-button").disabled = false;
    renderPeople();
  }
}

$("#login-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  const button = form.querySelector("button[type=submit]");
  $("#login-error").textContent = "";
  button.disabled = true;
  try {
    const credentials = await post("/auth/login", formValues(form));
    state.token = credentials.access_token;
    const user = await api("/auth/me");
    if (!["chairman", "president"].includes(user.role)) {
      signOut("This workspace requires a chairman or president account.");
      return;
    }
    state.timer = setTimeout(() => signOut("Your session has expired. Please sign in again."), credentials.expires_in * 1000);
    form.reset();
    $("#account-name").textContent = user.full_name;
    $("#login-screen").hidden = true;
    $("#workspace").hidden = false;
    showView("members");
    $("#search").value = "";
    $("#role-filter").value = "all";
    message("");
    await loadClub();
  } catch (error) {
    if (error.name !== "AbortError") signOut(error.message || "Unable to reach the server. Please try again.");
  } finally { button.disabled = false; }
});

function bindForm(selector, action) {
  $(selector).addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = event.currentTarget;
    const button = form.querySelector("button[type=submit]");
    const errorBox = form.querySelector(".form-error");
    errorBox.textContent = "";
    button.disabled = true;
    // Prevent closing and resubmitting while a write is in flight.
    const dialog = form.closest("dialog");
    const stopCancel = (event) => event.preventDefault();
    dialog.addEventListener("cancel", stopCancel);
    form.querySelectorAll(".close-dialog").forEach((item) => { item.disabled = true; });
    try { await action(formValues(form), dialog); }
    catch (error) {
      if (error.name !== "AbortError") errorBox.textContent = error.message || "Unable to reach the server. Please try again.";
    } finally {
      button.disabled = false;
      dialog.removeEventListener("cancel", stopCancel);
      form.querySelectorAll(".close-dialog").forEach((item) => { item.disabled = false; });
    }
  });
}

bindForm("#club-form", async (data, dialog) => {
  await post("/clubs", { name: data.name.trim(), description: data.description.trim() || null });
  dialog.close();
  message("Your racing club has been created.");
  await loadClub();
});
bindForm("#member-form", async (data, dialog) => {
  await post("/participants", { ...data, club_id: state.club.id,
    full_name: data.full_name.trim(), email: data.email.trim(), phone: data.phone.trim() || null });
  dialog.close();
  message("Participant account created and added to your club.");
  await loadClub();
});
bindForm("#assign-form", async (data, dialog) => {
  await post(`/clubs/${state.club.id}/members`, { user_id: data.user_id.trim() });
  dialog.close();
  message("Existing account added to your club.");
  await loadClub();
});
bindForm("#edit-form", async (data, dialog) => {
  await post(`/participants/${state.editing}`, { full_name: data.full_name.trim(), phone: data.phone.trim() || null }, "PUT");
  dialog.close();
  message("Participant details updated.");
  await loadClub();
});
bindForm("#password-form", async (data) => {
  if (data.new_password !== data.confirmation) throw new Error("The new passwords do not match.");
  await post("/auth/change-password", { current_password: data.current_password, new_password: data.new_password });
  signOut("Password changed. Sign in with your new password.");
});
$("#create-club-button").addEventListener("click", () => openDialog("#club-dialog"));
$("#add-member-button").addEventListener("click", () => openDialog("#member-dialog"));
$("#assign-button").addEventListener("click", () => openDialog("#assign-dialog"));
$("#password-button").addEventListener("click", () => openDialog("#password-dialog"));
$("#logout-button").addEventListener("click", () => signOut());
$("#refresh-button").addEventListener("click", () => { message(""); loadClub(); });
$("#search").addEventListener("input", renderPeople);
$("#role-filter").addEventListener("change", renderPeople);

const live = { active: false, timer: null, version: 0, raceId: "" };

function stopLive() {
  live.active = false;
  live.version += 1;
  clearTimeout(live.timer);
}

function showView(view) {
  stopLive();
  $("#members-view").hidden = view !== "members";
  $("#live-view").hidden = view !== "live";
  for (const name of ["members", "live"]) {
    $(`#${name}-nav`).classList.toggle("selected", name === view);
    if (name === view) $(`#${name}-nav`).setAttribute("aria-current", "page");
    else $(`#${name}-nav`).removeAttribute("aria-current");
  }
  $(".crumb").textContent = view === "live" ? "/ Live race" : "/ Members";
  if (view === "live") { live.active = true; loadRaces(); }
}

function resetLive(text) {
  $("#live-rows").replaceChildren();
  $("#validation-rows").replaceChildren();
  $("#validation-summary").textContent = "Select a race to inspect clocking evidence.";
  $("#validation-empty").hidden = false;
  $("#validation-empty").textContent = "No validation data loaded.";
  $("#live-state").textContent = text;
  $("#live-state").hidden = false;
  $("#live-total").textContent = "-";
  $("#live-arrived").textContent = "-";
  $("#live-status").textContent = "-";
  $("#live-release").textContent = "Release not loaded";
  $("#live-updated").textContent = "Not synchronized";
}

async function loadRaces() {
  const version = ++live.version;
  clearTimeout(live.timer);
  resetLive("Loading races...");
  $("#reload-races").disabled = true;
  $("#live-feed-state").textContent = "Loading races...";
  try {
    const races = await api("/races");
    if (!live.active || version !== live.version) return;
    const selector = $("#live-race");
    selector.replaceChildren(element("option", "", "Select a race"));
    selector.firstChild.value = "";
    for (const race of races) {
      const option = element("option", "", `${race.name} (${race.status})`);
      option.value = race.id;
      selector.append(option);
    }
    live.raceId = races.some((race) => race.id === live.raceId) ? live.raceId :
      (races.find((race) => race.status === "active")?.id || "");
    selector.value = live.raceId;
    if (live.raceId) await pollLive(version);
    else {
      resetLive(races.length ? "Select a race to see its arrivals." : "No races are available for your account. Create a race through the API to begin this pilot.");
      $("#live-feed-state").textContent = "No race selected";
    }
  } catch (error) {
    if (error.name !== "AbortError" && version === live.version) {
      resetLive("Unable to load races. Select Reload races to retry.");
      $("#live-feed-state").textContent = error.message;
    }
  } finally { $("#reload-races").disabled = false; }
}

function renderLive(data) {
  $("#validation-summary").textContent = `${data.suspicious_events} flagged · ${data.repeat_scans} repeat scans · ${data.simulated_events} simulated · Maximum ${data.maximum_speed_mpm} m/min`;
  const flaggedBody = $("#validation-rows");
  flaggedBody.replaceChildren();
  for (const item of data.flagged_events) {
    const tr = element("tr");
    const flags = element("td");
    for (const flag of item.blocking_flags) flags.append(element("div", "validation-flag", flag.replaceAll("_", " ")));
    tr.append(element("td", "person-name", item.official_ring_number), flags,
      element("td", "", item.speed_mpm === null ? "Not calculable" : `${Number(item.speed_mpm).toFixed(2)} m/min`),
      element("td", "", new Date(item.received_at).toLocaleString()));
    flaggedBody.append(tr);
  }
  $("#validation-empty").hidden = data.flagged_events.length > 0;
  $("#validation-empty").textContent = "No blocking flags detected. This does not certify official timing.";
  $("#live-total").textContent = String(data.registered_entries);
  $("#live-arrived").textContent = String(data.arrived_entries);
  $("#live-status").textContent = data.race_status;
  $("#live-release").textContent = data.release_at ? `Released ${new Date(data.release_at).toLocaleString()}` : "Not released";
  $("#live-updated").textContent = `Updated ${new Date(data.updated_at).toLocaleTimeString()}`;
  const body = $("#live-rows");
  body.replaceChildren();
  for (const row of data.entries) {
    const tr = element("tr");
    const rank = element("td");
    rank.append(element("span", "person-name", row.rank === null ? "Below minimum" : `#${row.rank}`),
      element("span", "person-email", row.leaderboard));
    const bird = element("td");
    bird.append(element("span", "person-name", row.official_ring_number), element("span", "person-email", row.owner_name));
    const arrival = element("td");
    arrival.append(element("span", "person-name", `Arrival #${row.arrival_order}`),
      element("span", "person-email", new Date(row.arrival_at).toLocaleString()));
    const evidence = element("td");
    evidence.append(element("span", "badge", `${row.capture_mode} / ${row.clocking_method}`),
      element("span", "person-email", `${row.reviewed ? "Reviewed" : "Unreviewed"} · ${row.offline_buffered ? "Buffered / " : ""}server time`));
    tr.append(rank, bird, arrival, element("td", "", `${(row.distance_meters / 1000).toFixed(3)} km`),
      element("td", "", `${row.display_speed.toLocaleString(undefined, { maximumFractionDigits: 4 })} ${data.speed_unit}`), evidence);
    body.append(tr);
  }
  $("#live-state").hidden = data.entries.length > 0;
  $("#live-state").textContent = data.release_at ? "Waiting for eligible arrivals. Unreviewed operator/manual scans are excluded." : "This race has not been released.";
  $("#live-feed-state").textContent = data.possibly_truncated ? "Showing the first 1,000 eligible entries" : "Connected · refreshes every 3 seconds";
}

async function pollLive(version = live.version) {
  if (!live.active || !live.raceId || !state.token || version !== live.version) return;
  try {
    const data = await api(`/races/${encodeURIComponent(live.raceId)}/live`);
    if (live.active && version === live.version) renderLive(data);
  } catch (error) {
    if (error.name !== "AbortError" && version === live.version) {
      // Keep last received rows visible but explicitly mark them stale.
      $("#live-feed-state").textContent = `Not synchronized · showing last received data. ${error.message}`;
    }
  } finally {
    if (live.active && state.token && version === live.version) live.timer = setTimeout(() => pollLive(version), 3000);
  }
}

$("#members-nav").addEventListener("click", () => showView("members"));
$("#live-nav").addEventListener("click", () => showView("live"));
$("#reload-races").addEventListener("click", loadRaces);
$("#live-race").addEventListener("change", () => {
  clearTimeout(live.timer);
  live.version += 1;
  live.raceId = $("#live-race").value;
  resetLive(live.raceId ? "Loading arrivals..." : "Select a race to see its arrivals.");
  $("#live-feed-state").textContent = live.raceId ? "Connecting..." : "No race selected";
  pollLive();
});
