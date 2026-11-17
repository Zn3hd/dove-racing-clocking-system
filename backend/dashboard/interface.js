/* Shared sign-in affordances. No credentials or clocking evidence are persisted. */
(() => {
  for (const formId of ['login-form', 'scan-login-form']) {
    const form = document.getElementById(formId);
    const password = form?.querySelector('input[name=password]');
    if (!password) continue;
    const label = password.closest('label');
    if (!label) continue;
    password.id ||= `${formId}-password`;
    const control = document.createElement('label');
    control.className = 'visibility-control';
    const toggle = document.createElement('input');
    toggle.type = 'checkbox';
    toggle.setAttribute('aria-controls', password.id);
    control.append(toggle, document.createTextNode('Show password'));
    label.after(control);
    toggle.addEventListener('change', () => { password.type = toggle.checked ? 'text' : 'password'; });
    form.addEventListener('reset', () => { password.type = 'password'; toggle.checked = false; });
  }
})();
