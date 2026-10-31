"use strict";
(() => {
  const $ = (id) => document.getElementById(id);
  let token = null, generation = 0, stream = null, cameraRun = 0, controller = new AbortController();
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
    stopCamera(); token = null; session.clear();
    session = new QRClocking.ScanSession(() => crypto.randomUUID());
    $("scan-workspace").hidden = true; $("scan-login").hidden = false;
    $("scan-account").textContent = "";
    $("scan-entry").replaceChildren(new Option("Select an entry", ""));
    $("scan-login-form").reset(); $("scan-form").reset();
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
    if (response.status === 401 && token) { signOut("Session or clocking token is no longer valid. Sign in and check with your club."); throw new DOMException("Signed out", "AbortError"); }
    if (!response.ok) throw new Error(typeof data.detail === "string" ? data.detail : "Submission rejected. Check your entry and clocking code.");
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
      const result = await session.submit(raw, $("scan-entry").value, source, (body) => request("/clocking/qr/scans", body));
      if (version !== generation) return;
      $("scan-token").value = "";
      status(`Scan received. Status: ${result.status}. Reference: ${result.event_id}. This is not an official result.`);
    } catch (error) {
      if (version === generation && error.name !== "AbortError") status(error instanceof TypeError ? "Connection failed. Retry the same scan." : error.message, true);
    } finally {
      controls.forEach((id) => { $(id).disabled = false; });
      if (version === generation && token) $("scan-token").focus();
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
      $("scan-account").textContent = account.full_name;
      $("scan-login").hidden = true; $("scan-workspace").hidden = false;
      await loadEntries(); $("scan-token").focus();
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
})();
