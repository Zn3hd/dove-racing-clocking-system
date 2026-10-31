const { test } = require('node:test');
const assert = require('node:assert/strict');
const { parseScan, ScanSession } = require('../dashboard/qr-core.js');
const entry = '00000000-0000-0000-0000-000000000001';
const key = '00000000-0000-0000-0000-000000000002';
const event = '00000000-0000-0000-0000-000000000003';
const token = 'A_-0'.repeat(12);
const ack = { event_id: event, status: 'pending', official_result_created: false };

test('USB text and versioned camera QR preserve the same token and entry', () => {
  assert.deepEqual(parseScan(token + '\r\n', entry), { entry_id: entry, token });
  assert.deepEqual(parseScan(JSON.stringify({ version: 1, entry_id: entry, token }), entry), { entry_id: entry, token });
});
test('wrong entry, arbitrary URL, malformed and oversized QR are rejected', () => {
  for (const raw of ['https://evil.test/?token=' + token, ' ' + token, 'short', '{', 'x'.repeat(1025),
    JSON.stringify({ version: 1, entry_id: key, token }), JSON.stringify({ version: 2, entry_id: entry, token })]) {
    assert.throws(() => parseScan(raw, entry));
  }
});
test('lost response retries the identical envelope; repeated scans do not duplicate', async () => {
  let ids = 0, bodies = [];
  const session = new ScanSession(() => { ids++; return key; });
  await assert.rejects(session.submit(token, entry, 'usb_qr', async (body) => {
    bodies.push(JSON.stringify(body)); throw new TypeError('Offline');
  }));
  const result = await session.submit(token, entry, 'web_camera', async (body) => {
    bodies.push(JSON.stringify(body)); return ack;
  });
  assert.deepEqual(result, ack); assert.equal(ids, 1); assert.equal(bodies[0], bodies[1]);
  await session.submit(token, entry, 'usb_qr', () => { throw new Error('must not send again'); });
});
test('invalid acknowledgement retains the original key', async () => {
  const session = new ScanSession(() => key);
  for (const result of [{}, { ...ack, official_result_created: true }]) {
    await assert.rejects(session.submit(token, entry, 'manual', async () => result));
  }
  assert.equal((await session.submit(token, entry, 'manual', async (body) => {
    assert.equal(body.idempotency_key, key); return ack;
  })).event_id, event);
});
test('concurrent scans are blocked, and signout removes tokens from memory', async () => {
  const session = new ScanSession(() => key);
  let finish;
  const first = session.submit(token, entry, 'web_camera', () => new Promise(resolve => { finish = resolve; }));
  await assert.rejects(session.submit(token, entry, 'usb_qr', async () => ack), /already/);
  finish(ack); await first;
  session.clear(); assert.equal(session.attempts.size, 0);
});
