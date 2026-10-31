/* Durable receipt metadata only. QR secrets and login tokens never enter IndexedDB. */
(() => {
  const database = () => new Promise((resolve, reject) => {
    const request = indexedDB.open('pigeon-qr-outbox', 1);
    request.onupgradeneeded = () => {
      const store = request.result.createObjectStore('receipts', { keyPath: 'identity' });
      store.createIndex('owner', 'owner');
    };
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(new Error('Local recovery storage is unavailable. No scan was sent.'));
  });
  async function transact(mode, work) {
    const db = await database();
    try {
      return await new Promise((resolve, reject) => {
        const tx = db.transaction('receipts', mode);
        let result;
        tx.oncomplete = () => resolve(result);
        tx.onerror = tx.onabort = () => reject(new Error('Could not save local recovery state.'));
        work(tx.objectStore('receipts'), (value) => { result = value; });
      });
    } finally { db.close(); }
  }
  async function prepare(owner, parsed, source) {
    const digest = [...new Uint8Array(await crypto.subtle.digest('SHA-256', new TextEncoder().encode(parsed.token)))].map(x => x.toString(16).padStart(2, '0')).join('');
    const identity = `${owner}:${parsed.entry_id}:${digest}`;
    const record = await transact('readwrite', (store, done) => {
      const get = store.get(identity);
      get.onsuccess = () => {
        const item = get.result || { identity, owner, entry_id: parsed.entry_id, capture_source: source,
          idempotency_key: crypto.randomUUID(), state: 'queued', created_at: new Date().toISOString() };
        store.put(item); done(item);
      };
    });
    return { entry_id: record.entry_id, capture_source: record.capture_source,
      idempotency_key: record.idempotency_key, token: parsed.token, client_queued_at:record.created_at };
  }
  async function records(owner) {
    return transact('readonly', (store, done) => {
      const get = store.index('owner').getAll(owner);
      get.onsuccess = () => done(get.result.sort((a,b) => b.created_at.localeCompare(a.created_at)));
    });
  }
  async function update(owner, key, state, receipt = null) {
    return transact('readwrite', (store) => {
      const get = store.index('owner').openCursor(IDBKeyRange.only(owner));
      get.onsuccess = () => {
        const cursor = get.result;
        if (!cursor) return;
        if (cursor.value.idempotency_key === key) cursor.update({ ...cursor.value, state,
          event_id: receipt?.event_id || cursor.value.event_id || null,
          review: receipt?.review_decision || null, updated_at: new Date().toISOString() });
        cursor.continue();
      };
    });
  }
  window.QROutbox = { prepare, records, update };
})();
