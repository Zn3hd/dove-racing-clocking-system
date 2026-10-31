/* Administrator workflows use the existing same-origin, club-authorized APIs. */
(() => {
  const host = document.getElementById('operations-view');
  host.innerHTML = `
    <div class="page-heading"><div><p class="eyebrow">PREPARE · RELEASE · REVIEW</p><h1>Race operations</h1><p class="muted">Manage registration and provisional evidence. Official finalization stays disabled.</p></div><button id="ops-refresh" class="outline" type="button">Refresh</button></div>
    <div class="operations-grid">
      <section class="operation-card"><h2>Register a pigeon</h2><form id="ops-pigeon"><label>Verified loft<select name="loft_id" required></select></label><label>Official ring number<input name="official_ring_number" required maxlength="100"></label><label>Pigeon name (optional)<input name="name" maxlength="200"></label><button class="primary" type="submit">Register pigeon</button></form>
      <details><summary>Assign an RFID ring</summary><form id="ops-ring"><label>Pigeon<select name="pigeon_id" required></select></label><label>Exact normalized RFID ID<input name="uid" required maxlength="200"></label><button class="outline" type="submit">Assign ring</button></form></details></section>
      <section class="operation-card"><h2>Create a race</h2><form id="ops-race-create"><label>Race name<input name="name" required maxlength="200"></label><div class="form-grid"><label>Release latitude<input name="release_latitude" type="number" step="any" min="-90" max="90" required></label><label>Release longitude<input name="release_longitude" type="number" step="any" min="-180" max="180" required></label></div><div class="form-grid"><label>Minimum m/min<input name="minimum_speed_mpm" type="number" step="any" min="0" value="500" required></label><label>Maximum m/min<input name="maximum_speed_mpm" type="number" step="any" min="1" value="3000" required></label></div><label>Ranking<select name="guest_ranking_mode"><option value="separate">Separate guest/member</option><option value="combined">Combined provisional</option></select></label><button class="primary" type="submit">Create draft race</button></form></section>
    </div>
    <section class="operation-card"><h2>Race registration and release</h2><label>Selected race<select id="ops-race"></select></label><p id="ops-race-status" class="muted"></p><div class="location-tools"><button id="ops-open" class="outline" type="button">Open registration</button><button id="ops-release" class="primary" type="button">Record release now</button><button id="ops-close" class="outline" type="button">Close race</button></div><p class="field-help">Release uses server time. Closing stops new arrivals; exact received-submission recovery remains available.</p><form id="ops-entry"><div class="form-grid"><label>Pigeon<select name="pigeon_id" required></select></label><label>Clocking method<select name="expected_method"><option value="QR">Guest QR</option><option value="RFID">Member RFID</option></select></label></div><button class="primary" type="submit">Register entry</button></form><ul id="ops-entries"></ul></section>
    <div class="operations-grid">
      <section class="operation-card"><h2>Private QR labels</h2><form id="ops-qr"><label>Guest entry<select name="entry_id" required></select></label><label>Validity in minutes<input name="expires_in_minutes" type="number" min="1" max="1440" value="120" required></label><p class="field-help">Issuing a new label revokes earlier labels for that entry. Share privately. Codes are generated here without a third-party QR service.</p><button class="primary" type="submit">Issue / rotate QR label</button></form><div id="ops-tokens"></div></section>
      <section class="operation-card"><h2>Arrival evidence review</h2><label>Event<select id="ops-event"></select></label><p id="ops-event-detail" class="field-help"></p><form id="ops-review"><label>Decision<select name="decision"><option value="approve">Approve provisional evidence</option><option value="reject">Reject evidence</option></select></label><label>Review reason<textarea name="reason" minlength="8" required rows="2"></textarea></label><button class="primary" type="submit">Record review</button></form><details><summary>Independent physical guest verification</summary><form id="ops-physical"><label>Decision<select name="decision"><option value="confirmed">Confirmed in person</option><option value="rejected">Rejected</option></select></label><label>Observed ring number<input name="ring_number_seen" required maxlength="200"></label><label>Physical evidence note<textarea name="evidence_note" minlength="12" required rows="2"></textarea></label><p class="field-help">Record only a verification you actually performed. This does not certify clock integrity or create official results.</p><button class="outline" type="submit">Record physical verification</button></form></details></section>
    </div>
    <section class="operation-card"><h2>Reader health and recovery</h2><p class="field-help">Last receipt is not a connection probe. Unsent guest outbox records stay on the guest device; use Recover receipts there. Flagged evidence is available in Live race.</p><ul id="ops-devices"></ul></section>
    <dialog id="ops-label"><h2>Private clocking QR</h2><p id="ops-label-expiry" class="muted"></p><canvas id="ops-label-canvas" aria-label="Private QR clocking label"></canvas><p class="field-help">Keep this label private. Closing clears it from this page. Lost labels must be rotated.</p><div class="dialog-actions"><button id="ops-label-close" class="outline" type="button">Close</button><button id="ops-label-download" class="primary" type="button">Download PNG</button></div></dialog>`;
  const get = id => document.getElementById(id);
  const fields = form => Object.fromEntries(new FormData(form));
  const data = { races: [], pigeons: [], lofts: [], entries: [], events: [], race: '', version: 0, transition: false };
  function syncControls() {
    const status = data.races.find(r => r.id === data.race)?.status;
    for (const [id, required] of [['ops-open','draft'],['ops-release','open'],['ops-close','active']]) get(id).disabled=data.transition || status!==required;
    get('ops-entry').querySelector('button[type=submit]').disabled=data.transition || status!=='open';
    get('ops-qr').querySelector('button[type=submit]').disabled=data.transition || !['open','active'].includes(status);
  }
  function options(select, items, value, label) {
    const previous = select.value;
    select.replaceChildren(new Option('Select...', ''));
    for (const item of items) select.add(new Option(label(item), String(value(item))));
    if ([...select.options].some(option => option.value === previous)) select.value = previous;
  }
  const pigeon = id => data.pigeons.find(p => p.id === id);
  function closeLabel() { get('ops-label').close(); get('ops-label-canvas').width = 0; get('ops-label-expiry').textContent = ''; }
  async function load() {
    const version = ++data.version;
    if (!state.club) { message('Create or join your club in Members first.', true); return; }
    get('ops-refresh').disabled = true;
    try {
      const [races, pigeons, lofts, devices] = await Promise.all([api('/races'), api('/pigeons'), api('/lofts'), api('/devices')]);
      if (version !== data.version || !state.token) return;
      Object.assign(data, { races, pigeons, lofts });
      options(get('ops-pigeon').elements.loft_id, lofts.filter(l => l.verified_at), l => l.id, l => l.name);
      for (const form of ['ops-ring', 'ops-entry']) options(get(form).elements.pigeon_id, pigeons.filter(p => p.status === 'active'), p => p.id, p => p.official_ring_number);
      options(get('ops-race'), races, r => r.id, r => `${r.name} (${r.status})`);
      data.race = races.some(r => r.id === data.race) ? data.race : races[0]?.id || '';
      get('ops-race').value = data.race;
      get('ops-devices').replaceChildren(...devices.map(d => element('li', '', `${d.device_identifier} · ${d.reader_adapter} · ${d.status} · Last receipt: ${d.last_seen_at ? new Date(d.last_seen_at).toLocaleString() : 'never'}`)));
      await loadRace();
    } catch (error) { if (error.name !== 'AbortError') message(error.message, true); }
    finally { get('ops-refresh').disabled = false; }
  }
  async function loadRace() {
    const race = data.race, version = data.version;
    const selected = data.races.find(r => r.id === race);
    get('ops-race-status').textContent = selected ? `Status: ${selected.status} · ${selected.minimum_speed_mpm}–${selected.maximum_speed_mpm} m/min` : 'No race selected';
    syncControls();
    data.entries = []; data.events = [];
    get('ops-entries').replaceChildren(); get('ops-tokens').replaceChildren();
    options(get('ops-qr').elements.entry_id, [], e => e.id, e => e.id);
    options(get('ops-event'), [], e => e.id, e => e.id);
    if (!race) return;
    try {
      const [entries, events, tokens] = await Promise.all([api(`/races/${race}/entries`), api(`/clocking/events?race_id=${race}`), api(`/clocking/qr/tokens/race/${race}`)]);
      if (race !== data.race || version !== data.version || !state.token) return;
      Object.assign(data, { entries, events });
      get('ops-entries').replaceChildren(...entries.map(e => element('li', '', `${pigeon(e.pigeon_id)?.official_ring_number || e.pigeon_id} · ${e.expected_method} · ${(Number(e.distance_meters)/1000).toFixed(3)} km`)));
      options(get('ops-qr').elements.entry_id, entries.filter(e => e.expected_method === 'QR'), e => e.id, e => pigeon(e.pigeon_id)?.official_ring_number || e.id);
      options(get('ops-event'), events, e => e.id, e => `${pigeon(entries.find(x => x.id === e.entry_id)?.pigeon_id)?.official_ring_number || e.entry_id} · ${e.method} · ${e.status} · ${new Date(e.received_at).toLocaleTimeString()}`);
      if (events.length === 1) get('ops-event').selectedIndex = 1;
      eventDetails();
      for (const token of tokens) {
        const row = element('p', 'field-help', `${token.official_ring_number} · ${token.revoked_at ? 'revoked' : new Date(token.expires_at) <= new Date() ? 'expired' : 'active'} · Expires ${new Date(token.expires_at).toLocaleString()} `);
        if (!token.revoked_at) {
          const button = element('button', 'outline small', 'Revoke'); button.type = 'button';
          button.addEventListener('click', () => perform(button, async () => { await post(`/clocking/qr/tokens/${token.id}/revoke`, {}); await loadRace(); }));
          row.append(button);
        }
        get('ops-tokens').append(row);
      }
    } catch (error) { if (error.name !== 'AbortError') message(error.message, true); }
  }
  function eventDetails() {
    const event = data.events.find(e => e.id === get('ops-event').value);
    get('ops-event-detail').textContent = event ? `Blocking flags: ${event.blocking_flags.join(', ') || 'none'}. Warnings: ${event.validation_warnings.join(', ') || 'none'}. Approval cannot override validation blocks.` : 'Select an event. Refresh to retrieve new arrivals.';
  }
  async function perform(button, action) {
    const auth = state.token;
    const transitioning = ['ops-open','ops-release','ops-close'].includes(button.id);
    if (transitioning) { data.transition=true; syncControls(); }
    button.disabled = true;
    try { await action(); if (state.token === auth) message('Operation saved.'); }
    catch (error) { if (state.token === auth && error.name !== 'AbortError') message(error.message || 'Unconfirmed operation. Refresh before retrying.', true); }
    finally {
      button.disabled = false;
      if (transitioning) data.transition=false;
      syncControls();
    }
  }
  function form(id, action) {
    get(id).addEventListener('submit', event => {
      event.preventDefault(); const target = event.currentTarget;
      perform(target.querySelector('button[type=submit]'), () => action(fields(target)));
    });
  }
  form('ops-pigeon', async value => { await post('/pigeons', { ...value, name:value.name.trim() || null }); get('ops-pigeon').reset(); await load(); });
  form('ops-ring', async value => { await post(`/pigeons/${value.pigeon_id}/rfid`, { uid:value.uid }); await load(); });
  form('ops-race-create', async value => {
    const result = await post('/races', { ...value, club_id:state.club.id,
      release_latitude:Number(value.release_latitude), release_longitude:Number(value.release_longitude),
      minimum_speed_mpm:Number(value.minimum_speed_mpm), maximum_speed_mpm:Number(value.maximum_speed_mpm) });
    data.race = result.id; await load();
  });
  form('ops-entry', async value => {
    if (!data.race) throw new Error('Select a race first.');
    await post(`/races/${data.race}/entries`, value); await loadRace();
  });
  form('ops-qr', async value => {
    const auth = state.token;
    const result = await post('/clocking/qr/tokens', { entry_id:value.entry_id, expires_in_minutes:Number(value.expires_in_minutes), include_image:true });
    const bytes = Uint8Array.from(atob(result.qr_png_base64), x => x.charCodeAt(0));
    const bitmap = await createImageBitmap(new Blob([bytes], { type:'image/png' }));
    if (state.token !== auth) { bitmap.close(); return; }
    const canvas = get('ops-label-canvas'); canvas.width=bitmap.width; canvas.height=bitmap.height;
    canvas.getContext('2d').drawImage(bitmap,0,0); bitmap.close();
    get('ops-label-expiry').textContent = `Expires ${new Date(result.expires_at).toLocaleString()}. Earlier labels were revoked.`;
    get('ops-label').showModal(); await loadRace();
  });
  form('ops-review', async value => { if (!get('ops-event').value) throw new Error('Select an event.'); await post(`/clocking/events/${get('ops-event').value}/review`, value); await loadRace(); });
  form('ops-physical', async value => { if (!get('ops-event').value) throw new Error('Select an event.'); await post(`/clocking/events/${get('ops-event').value}/guest-verification`, value); await loadRace(); });
  for (const [button, suffix] of [['ops-open','open'],['ops-release','activate'],['ops-close','close']]) {
    get(button).addEventListener('click', () => perform(get(button), async () => { await post(`/races/${data.race}/${suffix}`, {}); await load(); }));
  }
  get('ops-race').addEventListener('change', () => { data.race=get('ops-race').value; data.version++; closeLabel(); loadRace(); });
  get('ops-refresh').addEventListener('click', load);
  get('ops-event').addEventListener('change', eventDetails);
  get('ops-label-close').addEventListener('click', closeLabel);
  get('ops-label').addEventListener('close', () => { get('ops-label-canvas').width=0; });
  get('ops-label-download').addEventListener('click', () => {
    const auth = state.token;
    get('ops-label-canvas').toBlob(blob => { if (!blob || state.token !== auth) return; const url=URL.createObjectURL(blob);
      const link=document.createElement('a'); link.href=url; link.download='private-clocking-qr.png'; link.click(); setTimeout(() => URL.revokeObjectURL(url),1000); });
  });
  get('operations-nav').addEventListener('click', () => showView('operations'));
  window.Operations = { load, clear() {
    data.version++; Object.assign(data,{races:[],pigeons:[],lofts:[],entries:[],events:[],race:'',transition:false}); closeLabel();
    host.querySelectorAll('form').forEach(item => item.reset());
    for (const selector of ['#ops-pigeon [name=loft_id]','#ops-ring [name=pigeon_id]',
      '#ops-entry [name=pigeon_id]','#ops-race','#ops-qr [name=entry_id]','#ops-event']) host.querySelector(selector).replaceChildren();
    for (const id of ['ops-entries','ops-tokens','ops-devices']) get(id).replaceChildren();
    get('ops-event-detail').textContent=''; get('ops-race-status').textContent='';
  }};
})();
