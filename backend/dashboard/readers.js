/* Device secrets stay in this one-time dialog, never browser storage or configuration. */
(() => {
  const host = document.createElement('section'); host.className='operation-card';
  host.innerHTML=`<h2>Reader setup and live gateway monitoring</h2>
    <p class="field-help">Refreshes every 15 seconds while Race operations is visible. Recent heartbeat means the gateway reached the server within 90 seconds; it does not prove an antenna is working or certify an arrival.</p>
    <form id="reader-create"><div class="form-grid"><label>Loft<select name="loft_id" required></select></label><label>Unique reader name<input name="device_identifier" maxlength="200" required></label><label>Adapter<select name="reader_adapter"><option value="simulator">Simulator (test only)</option><option value="usb_hid">USB keyboard / HID</option><option value="serial">USB serial</option><option value="network">Network text protocol</option></select></label><label>Documented protocol label<input name="reader_protocol" maxlength="120" value="ascii-newline-v1" required></label></div><p class="field-help">Choose the reader's actual output protocol. Frequency alone does not establish compatibility. Only one active reader per loft is supported.</p><button class="primary" type="submit">Register reader</button></form>
    <p id="reader-status" role="status"></p><div id="reader-list"></div>
    <h3>Gateway configuration</h3><label>Reader<select id="reader-config-device"></select></label><label>Race<select id="reader-config-race"></select></label><button id="reader-config-generate" type="button" class="outline">Prepare configuration</button><pre id="reader-config-output"></pre><p class="field-help">Copy this non-secret JSON into gateway/config.local.json. Set PIGEON_DEVICE_TOKEN privately on the gateway computer. Serial and network readers require local port/host settings; consult gateway/README.md before starting capture. Do not put credentials in JSON.</p>
    <dialog id="reader-secret"><h2>One-time device credential</h2><p>Rotation immediately invalidates the previous credential. Copy privately into PIGEON_DEVICE_TOKEN on the gateway computer. Closing clears this display.</p><textarea id="reader-secret-value" readonly rows="3" aria-label="One-time device token"></textarea><button id="reader-secret-close" type="button" class="outline">Close and clear</button></dialog>`;
  document.getElementById('operations-view').append(host);
  const el=id=>document.getElementById(id);
  let generation=0, timer=null, devices=[], busy=false;
  const visible=()=>!!state.token && !document.getElementById('operations-view').hidden && !document.hidden;
  function options(select, rows, label) { const old=select.value; select.replaceChildren(new Option('Select...', '')); rows.forEach(r=>select.add(new Option(label(r),r.id))); if(rows.some(r=>r.id===old)) select.value=old; }
  function clearSecret() { el('reader-secret-value').value=''; el('reader-secret').close(); }
  async function action(button, work) {
    if(busy) return; busy=true; button.disabled=true; const auth=state.token;
    try { await work(auth); } catch(e) { if(state.token===auth && e.name!=='AbortError') el('reader-status').textContent=e.message; }
    finally { busy=false; button.disabled=false; }
  }
  function button(row,label,run) { const b=element('button','outline small',label); b.type='button'; b.addEventListener('click',()=>action(b,run)); row.append(b); }
  async function refresh() {
    clearTimeout(timer); if(!visible()) return;
    const version=generation;
    try {
      const result=await api('/devices'); if(version!==generation || !visible()) return;
      devices=result; options(el('reader-config-device'),devices,d=>d.device_identifier);
      el('reader-list').replaceChildren(...devices.map(d=>{
        const row=element('div','verification-box');
        row.append(element('p','',`${d.device_identifier} | ${d.reader_adapter} / ${d.reader_protocol} | Gateway: ${d.gateway_status} | Credential: ${d.credential_status}`));
        row.append(element('p','field-help',`Heartbeat: ${d.heartbeat_at?new Date(d.heartbeat_at).toLocaleString():'never'} | Reader report: ${d.reported_reader_state || 'unknown'} | Pending: ${d.reported_pending_count ?? 'unknown'} | Rejected: ${d.reported_rejected_count ?? 'unknown'} | Last arrival: ${d.last_seen_at?new Date(d.last_seen_at).toLocaleString():'never'}`));
        button(row,'Provision / rotate token',async auth=>{
          if(d.credential_status==='provisioned' && !window.confirm('Rotate this credential? The existing gateway must be updated before it can send again.')) return;
          const result=await post(`/devices/${d.id}/provision`,{}); if(state.token!==auth) return;
          el('reader-secret-value').value=result.device_token; el('reader-secret').showModal(); await refresh();
        });
        if(d.credential_status==='provisioned') button(row,'Revoke credential',async auth=>{
          if(!window.confirm('Revoke this gateway credential? New heartbeats and arrivals will be blocked. Queued evidence remains on its gateway.')) return;
          await post(`/devices/${d.id}/revoke`,{}); if(state.token===auth) { clearSecret(); await refresh(); }
        });
        return row;
      }));
      el('reader-status').textContent=`Monitor refreshed ${new Date().toLocaleTimeString()}. Queue counts are gateway-reported snapshots.`;
    } catch(e) { if(version===generation && e.name!=='AbortError') el('reader-status').textContent=`Monitor unavailable: ${e.message}. Previously displayed data may be stale.`; }
    finally { if(version===generation && visible()) timer=setTimeout(refresh,15000); }
  }
  el('reader-create').addEventListener('submit',e=>{e.preventDefault(); const form=e.currentTarget; action(form.querySelector('button'),async auth=>{await post('/devices',Object.fromEntries(new FormData(form))); if(state.token===auth) {form.reset(); await refresh();}});});
  el('reader-secret-close').addEventListener('click',clearSecret);
  el('reader-secret').addEventListener('close',()=>{el('reader-secret-value').value='';});
  el('reader-config-generate').addEventListener('click',()=>{
    const d=devices.find(d=>d.id===el('reader-config-device').value), race=el('reader-config-race').value;
    if(!d || !race) {el('reader-status').textContent='Select a reader and race.';return;}
    const config={backend_url:location.origin,device_id:d.id,race_id:race,adapter:d.reader_adapter,protocol:d.reader_protocol,normalization:'preserve',capture_mode:'operator',queue_path:'gateway-queue.sqlite3'};
    if(['localhost','127.0.0.1'].includes(location.hostname) && location.protocol==='http:') config.allow_local_http=true;
    if(d.reader_adapter==='serial') Object.assign(config,{serial_port:'REPLACE_WITH_LOCAL_PORT',baudrate:9600});
    if(d.reader_adapter==='network') Object.assign(config,{network_host:'REPLACE_WITH_READER_HOST',network_port:9000});
    el('reader-config-output').textContent=JSON.stringify(config,null,2);
  });
  document.addEventListener('visibilitychange',()=>{if(visible()) refresh(); else clearTimeout(timer);});
  window.Readers={load(lofts,races){generation++; options(el('reader-create').elements.loft_id,lofts,l=>l.name); options(el('reader-config-race'),races,r=>`${r.name} (${r.status})`); refresh();},stop(){clearTimeout(timer);generation++;clearSecret();},clear(){this.stop();devices=[];el('reader-list').replaceChildren();el('reader-status').textContent='';el('reader-config-output').textContent='';el('reader-create').reset();for(const s of [el('reader-create').elements.loft_id,el('reader-config-device'),el('reader-config-race')]) s.replaceChildren();}};
})();
