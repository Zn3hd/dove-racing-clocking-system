/* Flight Deck presentation. Server data remains authoritative. */
(() => {
  const get = id => document.getElementById(id);
  const time = value => value ? new Date(value).toLocaleString('en-PH', {
    timeZone: 'Asia/Manila', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false
  }) + ' PHT' : '—';
  let freshAt = 0;
  const put = (id, value) => { get(id).textContent = value; };
  window.CommandCenter = {
    reset() {
      freshAt = 0;
      for (const id of ['command-pending', 'command-review-count']) put(id, '—');
      put('command-pending-flags', 'Review summary unavailable');
      put('command-last-arrival', 'No eligible arrivals yet');
      put('command-review-age', 'Select a race to load the review queue.');
      put('command-progress-label', 'Arrival progress —');
      put('command-remaining', '— remaining'); put('command-rate', 'Arrival rate unavailable');
      put('command-activity-state', 'Waiting for race activity');
      get('command-activity-list').replaceChildren(); get('command-progress').value = 0;
      get('live-updated').classList.remove('is-stale');
      delete get('live-status').dataset.state;
    },
    connection(ok) {
      if (!ok) { put('live-updated', 'Updates delayed · last success ' + (freshAt ? time(freshAt) : 'unavailable')); get('live-updated').classList.add('is-stale'); }
    },
    update(data) {
      get('live-status').dataset.state = data.race_status;
      freshAt = Date.now(); get('live-updated').classList.remove('is-stale');
      put('live-updated', 'Connected · ' + time(data.updated_at));
      const fraction = data.registered_entries ? 100 * data.arrived_entries / data.registered_entries : 0;
      get('command-progress').value = fraction;
      put('command-progress-label', `${fraction.toFixed(1)}% (${data.arrived_entries}/${data.registered_entries})`);
      put('command-remaining', `${Math.max(0, data.registered_entries - data.arrived_entries)} remaining${data.possibly_truncated ? ' · partial' : ''}`);
      put('command-last-arrival', data.last_eligible_arrival_at ? 'Last arrival ' + time(data.last_eligible_arrival_at) : data.possibly_truncated ? 'Last arrival unavailable · partial view' : 'No eligible arrivals yet');
      put('command-rate', data.arrival_rate_per_minute == null ? 'Arrival rate unavailable' : `${Number(data.arrival_rate_per_minute).toFixed(1)}/min · last 5 min`);
      const known = Number.isInteger(data.pending_reviews);
      put('command-pending', known ? String(data.pending_reviews) : '—');
      put('command-review-count', known ? String(data.pending_reviews) : '—');
      put('command-pending-flags', known ? `${data.pending_flagged_reviews} flagged · race-wide` : 'Review summary unavailable');
      get('command-review-count').classList.toggle('queue-clear', known && data.pending_reviews === 0);
      get('command-review-count').closest('.command-review').classList.toggle('queue-clear', known && data.pending_reviews === 0);
      const oldest = data.oldest_pending_at ? Math.max(0, Math.floor((Date.parse(data.updated_at) - Date.parse(data.oldest_pending_at)) / 60000)) : null;
      put('command-review-age', !known ? 'Review summary unavailable. Open evidence review to inspect submissions.' : data.pending_reviews === 0 ? 'Review queue clear · official finalization remains disabled.' : `${data.pending_flagged_reviews} flagged · oldest pending ${oldest == null ? '—' : oldest + ' min'} · evidence review is provisional`);
      const activity = data.recent_activity || [];
      put('command-activity-state', data.recent_activity ? activity.length ? 'Submissions and review actions · server timestamps' : 'No submissions recorded for this race.' : 'Activity unavailable for this snapshot');
      const list = get('command-activity-list');
      const scrollTop = list.scrollTop;
      const existing = new Map([...list.children].map(item => [item.dataset.key, item]));
      for (const event of activity) {
        let item = existing.get(event.activity_id);
        if (!item) { item = document.createElement('li'); item.dataset.key = event.activity_id; }
        existing.delete(event.activity_id);
        const title = event.kind === 'review' ? `Review ${event.decision === 'approve' ? 'approved' : 'rejected'}` : event.kind === 'validation' ? 'Validation flagged' : `${event.method} submission received`;
        const summary = event.kind === 'review' ? `${event.reviewer || 'Official'} · provisional evidence` : event.kind === 'validation' ? (event.blocking_flags || []).join(' · ').replaceAll('_', ' ') : event.capture_mode === 'simulated' ? 'Simulated · test evidence only' : 'Submission is not an official result';
        const stamp = document.createElement('time'); stamp.dateTime = event.occurred_at; stamp.textContent = time(event.occurred_at);
        const heading = document.createElement('strong'); heading.className = 'with-icon icon-' + (event.kind === 'review' ? 'user-check' : event.kind === 'validation' ? 'shield' : 'radio'); heading.textContent = title;
        const ring = document.createElement('span'); ring.textContent = event.official_ring_number;
        const detail = document.createElement('small'); detail.textContent = summary;
        item.className = 'activity-' + event.kind;
        item.replaceChildren(stamp, heading, ring, detail); list.append(item);
      }
      for (const item of existing.values()) item.remove();
      list.scrollTop = scrollTop;
    }
  };
  setInterval(() => {
    if (freshAt && !get('live-view').hidden && Date.now() - freshAt > 10000) window.CommandCenter.connection(false);
  }, 1000);
})();
