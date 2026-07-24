(() => {
  'use strict';

  const settingsList = document.querySelector('#page-settings .settings-list');
  if (!settingsList || document.querySelector('#open-change-password')) return;

  const logoutButton = document.querySelector('#settings-logout');
  const openButton = document.createElement('button');
  openButton.id = 'open-change-password';
  openButton.type = 'button';
  openButton.innerHTML = `
    <span aria-hidden="true" style="font-size:22px">🔐</span>
    <div><b>Change Password</b><small>Current password verify karke naya password set karein</small></div>
    <i data-icon="chevron"></i>
  `;
  settingsList.insertBefore(openButton, logoutButton || null);

  document.body.insertAdjacentHTML('beforeend', `
    <dialog id="change-password-dialog" class="modal">
      <form id="change-password-form" method="dialog">
        <div class="modal-head">
          <div><span class="eyebrow">ACCOUNT SECURITY</span><h2>Change Password</h2></div>
          <button type="button" class="icon-button" id="close-change-password" aria-label="Close"><span data-icon="close"></span></button>
        </div>
        <div class="form-grid one">
          <label>
            Current Password
            <div class="password-field-wrap">
              <input name="current_password" type="password" required maxlength="128" autocomplete="current-password" />
              <button type="button" class="password-eye" data-toggle-password="current_password" aria-label="Show current password">Show</button>
            </div>
          </label>
          <label>
            New Password / PIN
            <div class="password-field-wrap">
              <input name="new_password" type="password" required minlength="4" maxlength="128" autocomplete="new-password" />
              <button type="button" class="password-eye" data-toggle-password="new_password" aria-label="Show new password">Show</button>
            </div>
            <small>Minimum 4 characters. Purane password se alag rakhein.</small>
          </label>
          <label>
            Confirm New Password
            <div class="password-field-wrap">
              <input name="confirm_password" type="password" required minlength="4" maxlength="128" autocomplete="new-password" />
              <button type="button" class="password-eye" data-toggle-password="confirm_password" aria-label="Show confirm password">Show</button>
            </div>
          </label>
          <div class="password-security-note">Password बदलने के बाद दूसरे phones/browsers की पुरानी login sessions बंद हो जाएँगी। यह phone logged in रहेगा।</div>
          <button id="save-new-password" class="btn primary wide" type="submit">Change Password</button>
        </div>
      </form>
    </dialog>
  `);

  const style = document.createElement('style');
  style.textContent = `
    .password-field-wrap{position:relative;display:flex;align-items:center}
    .password-field-wrap input{padding-right:70px!important;width:100%}
    .password-eye{position:absolute;right:8px;border:0;background:transparent;color:#087bc1;font-weight:800;padding:8px;cursor:pointer}
    .password-security-note{padding:12px;border-radius:10px;background:#eef8ff;color:#40505f;line-height:1.45;font-size:13px}
    #change-password-dialog{width:min(94vw,520px)}
  `;
  document.head.appendChild(style);

  const dialog = document.querySelector('#change-password-dialog');
  const form = document.querySelector('#change-password-form');
  const submitButton = document.querySelector('#save-new-password');

  function openDialog() {
    form.reset();
    form.querySelectorAll('input').forEach(input => input.type = 'password');
    form.querySelectorAll('.password-eye').forEach(button => button.textContent = 'Show');
    dialog.showModal();
    setTimeout(() => form.elements.current_password.focus(), 50);
  }

  openButton.addEventListener('click', openDialog);
  document.querySelector('#close-change-password').addEventListener('click', () => dialog.close());

  form.addEventListener('click', event => {
    const button = event.target.closest('[data-toggle-password]');
    if (!button) return;
    const input = form.elements[button.dataset.togglePassword];
    if (!input) return;
    const reveal = input.type === 'password';
    input.type = reveal ? 'text' : 'password';
    button.textContent = reveal ? 'Hide' : 'Show';
  });

  form.addEventListener('submit', async event => {
    event.preventDefault();
    const data = Object.fromEntries(new FormData(form));
    if (data.new_password !== data.confirm_password) {
      toast('New password aur Confirm password same nahi hain', true);
      return;
    }
    if ((data.new_password || '').length < 4) {
      toast('New password minimum 4 characters ka hona chahiye', true);
      return;
    }

    submitButton.disabled = true;
    submitButton.textContent = 'Changing…';
    try {
      const result = await api('/api/account/change-password', {method: 'POST', body: data});
      dialog.close();
      form.reset();
      const count = Number(result.other_sessions_logged_out || 0);
      toast(`Password changed${count ? ` · ${count} other session logged out` : ''}`);
    } catch (error) {
      toast(error.message, true);
    } finally {
      submitButton.disabled = false;
      submitButton.textContent = 'Change Password';
    }
  });
})();
