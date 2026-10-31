/* Shared by the browser and Node's contract tests. No storage or logging. */
(function (root) {
  "use strict";
  const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
  function parseScan(raw, selectedEntry) {
    if (typeof raw !== "string" || raw.length > 1024 || !uuid.test(selectedEntry)) {
      throw new Error("Select a race entry and scan a valid clocking QR code.");
    }
    let token = raw.replace(/[\r\n]+$/, "");
    if (token.startsWith("{")) {
      let data;
      try { data = JSON.parse(token); } catch { throw new Error("Unreadable clocking QR code."); }
      if (data?.version !== 1 || typeof data.entry_id !== "string" || data.entry_id.toLowerCase() !== selectedEntry.toLowerCase()) {
        throw new Error("This QR code does not match the selected entry.");
      }
      token = data.token;
    }
    if (typeof token !== "string" || !/^[A-Za-z0-9_-]{32,256}$/.test(token)) {
      throw new Error("Scan the clocking token supplied by your club.");
    }
    return { entry_id: selectedEntry.toLowerCase(), token };
  }

  class ScanSession {
    constructor(makeId) { this.makeId = makeId; this.attempts = new Map(); this.busy = false; }
    clear() { this.attempts.clear(); }
    async submit(raw, entry, source, send) {
      if (this.busy) throw new Error("A scan is already being submitted.");
      if (!["usb_qr", "web_camera", "manual"].includes(source)) throw new Error("Unknown scan source.");
      const parsed = parseScan(raw, entry);
      const identity = JSON.stringify(parsed);
      let attempt = this.attempts.get(identity);
      if (attempt?.result) return attempt.result;
      if (!attempt) {
        if (this.attempts.size >= 100) throw new Error("Session scan limit reached. Sign out before starting another session.");
        attempt = { body: { ...parsed, capture_source: source, idempotency_key: this.makeId() } };
        this.attempts.set(identity, attempt);
      }
      this.busy = true;
      try {
        const result = await send(attempt.body);
        if (!result || !uuid.test(result.event_id) || !["pending", "invalid", "valid"].includes(result.status)
            || result.official_result_created === true) throw new Error("Unconfirmed response. Retry the same scan.");
        attempt.result = result;
        return result;
      } finally { this.busy = false; }
    }
  }
  const api = { parseScan, ScanSession };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.QRClocking = api;
})(globalThis);
