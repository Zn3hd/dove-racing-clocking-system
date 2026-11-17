/* Decorative, self-hosted Feather icons. Labels remain the accessible names. */
(() => {
  const decorate = (selector, icon, kind = '') => {
    document.querySelectorAll(selector).forEach(node => {
      node.classList.add('with-icon', `icon-${icon}`);
      if (kind) node.classList.add(kind);
    });
  };
  // Run after the existing operation and reader templates have been created.
  document.addEventListener('DOMContentLoaded', () => {
    const controls = {
      '#members-nav': 'users', '#operations-nav': 'flag', '#live-nav': 'activity',
      '#password-button': 'key', '#logout-button, #signout, #scan-signout': 'log-out',
      '#add-member-button': 'plus', '#refresh-button, #reload-races, #refresh, #ops-refresh, #scan-reload': 'refresh-cw',
      '#review-arrival-evidence': 'clipboard', '#capture-gps': 'map-pin',
      '#scan-camera-start': 'camera', '#scan-submit': 'upload', '#scan-recover': 'refresh-cw',
      '#verify-location': 'check-circle', '#ops-open': 'flag', '#ops-release': 'send', '#ops-close': 'check-circle',
      '.role-links a[href="/dashboard/"]': 'shield',
      '.role-links a[href="/dashboard/member.html"]': 'user',
      '.role-links a[href="/dashboard/scan.html"]': 'camera',
      '.operations-nav a[href="#ops-registration"]': 'flag',
      '.operations-nav a[href="#ops-pigeon-panel"]': 'home',
      '.operations-nav a[href="#ops-race-panel"]': 'plus',
      '.operations-nav a[href="#ops-evidence"]': 'clipboard',
      '.operations-nav a[href="#reader-setup"]': 'radio'
    };
    for (const [selector, icon] of Object.entries(controls)) decorate(selector, icon);
    const statistics = {
      '#stat-total': 'users', '#stat-members': 'user-check', '#stat-guests': 'user',
      '#live-total': 'grid', '#live-arrived, #member-arrived': 'check-circle',
      '#race-in-transit, #member-transit': 'send', '#race-top-speed, #member-top-speed': 'zap',
      '#race-participants, #member-participants': 'users', '#command-pending': 'clipboard'
    };
    for (const [selector, icon] of Object.entries(statistics)) {
      document.querySelectorAll(selector).forEach(value => {
        const label = value.parentElement.querySelector('span');
        if (label) { label.classList.add('with-icon', `icon-${icon}`, 'stat-icon-label'); }
      });
    }
    decorate('#standings-heading, .leaderboard-panel .section-title h2', 'activity', 'section-icon');
    decorate('#ops-registration h2, #ops-race-panel h2', 'flag', 'section-icon');
    decorate('#ops-pigeon-panel h2', 'home', 'section-icon');
    decorate('#ops-evidence h2, #validation-heading', 'clipboard', 'section-icon');
    decorate('#reader-setup>h2', 'radio', 'section-icon');
    decorate('#telemetry-heading', 'activity', 'section-icon');
    // Replace the legacy text-symbol illustration with an actual library asset.
    const flight = document.querySelector('.flight-art .bird');
    if (flight) { flight.textContent = ''; flight.classList.add('with-icon', 'icon-send'); }
    const signInArrow = document.querySelector('#login-form button span[aria-hidden=true]');
    if (signInArrow) { signInArrow.textContent = ''; signInArrow.classList.add('with-icon', 'icon-arrow-right'); }
  });
})();
