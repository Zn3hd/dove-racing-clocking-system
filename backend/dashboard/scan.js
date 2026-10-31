"use strict";
(() => {
  const $ = (id) => document.getElementById(id);
  let token = null, owner = null, generation = 0, stream = null, cameraRun = 0, controller = new AbortController();
  let session = new QRClocking.ScanSession(() => crypto.randomUUID());
  function status(text, error = false) { $("scan-status").textContent = text; $("scan-status").classList.toggle("error", error); }
  function stopCamera() {
    cameraRun++;
    if (stream) stream.getTracks().forEach((track) => track.stop());
    stream = null;
    $("scan-video").srcObject = null;
    $("scan-video").hidden = true;
    $("scan-camera-stop").hidden = true;
    $("scan-camera-start").disabled = false;
  }
  function signOut(text = "Signed out.") {
    generation++;
    controller.abort(); controller = new AbortController();
    stopCamera(); token = null; owner = null; session.clear();
    $("scan-outbox").replaceChildren();
    session = new QRClocking.ScanSession(() => crypto.randomUUID());
    $("scan-workspace").hidden = true; $("scan-login").hidden = false;
    $("scan-account").textContent = "";
    $("scan-entry").replaceChildren(new Option("Select an entry", ""));
    $("scan-login-form").reset(); $("scan-form").reset();
    for (const id of ['scan-submit','scan-token','scan-entry','scan-source','scan-reload','scan-camera-start','scan-recover']) $(id).disabled=false;
    status(text);
  }
  async function request(path, body) {
    const version = generation;
    const response = await fetch(path, { method: body ? "POST" : "GET", credentials: "omit", cache: "no-store",
      redirect: "error", signal: controller.signal,
      headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}) },
      ...(body ? { body: JSON.stringify(body) } : {}) });
    let data; try { data = await response.json(); } catch { throw new Error("Unconfirmed response. Retry the same scan."); }
    if (version !== generation) throw new DOMException("Session changed", "AbortError");
    if (response.status === 401 && token && data.detail !== 'Invalid or expired clocking token') { signOut("Session is no longer valid. Sign in to recover receipts."); throw new DOMException("Signed out", "AbortError"); }
    if (!response.ok) {
      const error = new Error(response.status === 429 ? `Too many requests. Retry in ${response.headers.get('Retry-After') || '60'} seconds using the same code.` :
        (typeof data.detail === "string" ? data.detail : "Submission rejected. Check your entry and clocking code."));
      error.status = response.status; throw error;
    }
    return data;
  }
  async function loadEntries() {
    const entries = await request("/clocking/qr/entries");
    $("scan-entry").replaceChildren(new Option("Select an entry", ""));
    for (const entry of entries) $("scan-entry").add(new Option(`${entry.race_name} · ${entry.official_ring_number}`, entry.entry_id));
    if (entries.length === 1) $("scan-entry").selectedIndex = 1;
    status(entries.length ? "Select your entry, then scan." : "No active QR entries. Ask your club to check your registration and race release.");
  }
  async function submit(raw, source) {
    if (!token || session.busy) return;
    const version = generation;
    const controls = ["scan-submit", "scan-token", "scan-entry", "scan-source", "scan-reload", "scan-camera-start"];
    controls.forEach((id) => { $(id).disabled = true; });
    try {
      const account = owner;
      const result = await session.submit(raw, $("scan-entry").value, source, async (body) => {
        if (version !== generation || account !== owner || !token) throw new DOMException('Session changed','AbortError');
        await QROutbox.update(account, body.idempotency_key, 'sending');
        try {
          const reply = await request('/clocking/qr/scans', body);
          if (!QRClocking.isConfirmed(reply)) throw new Error('Unconfirmed response. Retry the same scan.');
          await QROutbox.update(account, body.idempotency_key, reply.status === 'invalid' ? 'rejected' : 'received', reply);
          return reply;
        } catch (error) {
          await QROutbox.update(account, body.idempotency_key, [401,403,409,422].includes(error.status) ? 'needs review' : 'queued');
          throw error;
        }
      });
      if (version !== generation) return;
      $("scan-token").value = "";
      status(`Scan received. Status: ${result.status}. Reference: ${result.event_id}. This is not an official result.`);
    } catch (error) {
      if (version === generation && error.name !== "AbortError") status(error instanceof TypeError ? "Connection failed. Retry the same scan." : error.message, true);
    } finally {
      if (version === generation) controls.forEach((id) => { $(id).disabled = false; });
      if (version === generation && token) $("scan-token").focus();
      if (version === generation && owner) await renderOutbox().catch(() => status('Recovery storage is unavailable. Keep the page open and contact your club.', true));
    }
  }
  $("scan-login-form").addEventListener("submit", async (event) => {
    event.preventDefault(); const version = generation;
    const button = event.currentTarget.querySelector("button"); button.disabled = true;
    try {
      const form = new FormData(event.currentTarget);
      const data = await request("/auth/login", { email: form.get("email"), password: form.get("password") });
      token = data.access_token;
      $("scan-login-form").reset();
      const account = await request("/auth/me");
      if (account.role !== "guest") { signOut("Use your guest account for guest QR clocking."); return; }
      owner = account.id;
      if (!owner) throw new Error('Account identity unavailable. Sign in again.');
      session = new QRClocking.ScanSession(() => crypto.randomUUID(), (parsed, source) => QROutbox.prepare(owner, parsed, source));
      $("scan-account").textContent = account.full_name;
      $("scan-login").hidden = true; $("scan-workspace").hidden = false;
      await loadEntries(); await renderOutbox().catch(() => status('Recovery storage is unavailable. Scans cannot be sent until storage is available.',true)); $("scan-token").focus();
    } catch (error) { if (version === generation && error.name !== "AbortError") signOut(error.message); }
    finally { button.disabled = false; }
  });
  $("scan-form").addEventListener("submit", (event) => { event.preventDefault(); stopCamera(); void submit($("scan-token").value, $("scan-source").value); });
  $("scan-signout").addEventListener("click", () => signOut());
  $("scan-reload").addEventListener("click", () => { stopCamera(); loadEntries().catch((error) => { if (error.name !== "AbortError") status(error.message, true); }); });
  $("scan-entry").addEventListener("change", () => { stopCamera(); $("scan-token").value = ""; });
  $("scan-camera-stop").addEventListener("click", stopCamera);
  $("scan-camera-start").addEventListener("click", async () => {
    if (!token || !$("scan-entry").value) { status("Select your race entry first.", true); return; }
    if (!navigator.mediaDevices?.getUserMedia || !window.isSecureContext) { status("Camera scanning needs HTTPS and camera access. You can use a USB scanner or paste the token.", true); return; }
    stopCamera(); const run = cameraRun;
    $("scan-camera-start").disabled = true;
    try {
      const acquired = await navigator.mediaDevices.getUserMedia({ audio: false, video: { facingMode: { ideal: "environment" }, width: { ideal: 1280 } } });
      if (run !== cameraRun || !token || document.hidden) { acquired.getTracks().forEach((track) => track.stop()); return; }
      stream = acquired;
      const video = $("scan-video"); video.srcObject = stream; video.hidden = false;
      $("scan-camera-stop").hidden = false;
      await video.play();
      status("Point the camera at your clocking QR code.");
      const canvas = $("scan-canvas"), context = canvas.getContext("2d", { willReadFrequently: true });
      async function capture() {
        if (run !== cameraRun) return;
        try {
          if (video.readyState >= 2 && video.videoWidth) {
            canvas.width = Math.min(video.videoWidth, 960);
            canvas.height = Math.round(video.videoHeight * canvas.width / video.videoWidth);
            context.drawImage(video, 0, 0, canvas.width, canvas.height);
            const frame = context.getImageData(0, 0, canvas.width, canvas.height);
            const code = jsQR(frame.data, frame.width, frame.height);
            if (code) { stopCamera(); await submit(code.data, "web_camera"); return; }
          }
          setTimeout(capture, 200);
        } catch { stopCamera(); status("Camera could not read the code. Try again or use a USB scanner.", true); }
      }
      void capture();
    } catch { if (run === cameraRun) { stopCamera(); status("Camera unavailable or permission denied. Use a USB scanner or paste the token.", true); } }
  });
  document.addEventListener("visibilitychange", () => { if (document.hidden) stopCamera(); });
  window.addEventListener("pagehide", () => signOut("Session closed."));
  async function renderOutbox() {
    const account = owner, version = generation;
    const items = await QROutbox.records(account);
    if (account !== owner || version !== generation) return;
    $("scan-outbox").replaceChildren();
    for (const item of items) {
      const row = document.createElement('li');
      row.textContent = `${item.state} · ${item.capture_source} · ${item.idempotency_key}${item.review ? ` · ${item.review}` : ''}`;
      $("scan-outbox").append(row);
    }
  }
  $("scan-recover").addEventListener('click', async () => {
    const account = owner, version = generation;
    if (!account) return;
    $("scan-recover").disabled = true;
    try {
      for (const item of await QROutbox.records(account)) {
        if (version !== generation) return;
        try {
          const receipt = await request(`/clocking/qr/receipts/${item.idempotency_key}`);
          session.reconcile(item.idempotency_key, receipt);
          await QROutbox.update(account, item.idempotency_key,
            receipt.status === 'invalid' || receipt.review_decision === 'reject' ? 'rejected' :
            receipt.blocking_flags.length ? 'needs review' : 'received', receipt);
        } catch (error) {
          if (error.status === 404) await QROutbox.update(account, item.idempotency_key, ['received','rejected','needs review'].includes(item.state) ? 'needs review' : 'queued');
          else throw error;
        }
      }
      if (version !== generation) return;
      await renderOutbox();
      status('Receipts checked. Queued records need the original code rescanned; expired codes or closed races need club review.');
    } catch (error) { if (version === generation && error.name !== 'AbortError') status(error.message, true); }
    finally { $("scan-recover").disabled = false; }
  });
})();
