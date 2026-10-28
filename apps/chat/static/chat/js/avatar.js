// ===== Аватарка =====
const AVATAR_URL_PATTERN = /^\/media\/avatars\/[a-f0-9]+\.webp$/;
const MAX_AVATAR_FILE_BYTES = 2 * 1024 * 1024;
const AVATAR_TYPES = ['image/jpeg', 'image/png', 'image/webp'];

function applyAvatar() {
  const url = accountInfo && accountInfo.avatar_url;
  const valid = typeof url === 'string' && AVATAR_URL_PATTERN.test(url);
  const value = valid ? `url("${url}")` : '';
  for (const id of ['avatar', 'profile-avatar']) {
    $(id).style.backgroundImage = value;
  }
  $('avatar-remove').hidden = !valid;
}

async function uploadAvatar(file) {
  const error = $('avatar-error');
  error.textContent = '';
  if (!file) return;

  if (!AVATAR_TYPES.includes(file.type)) {
    error.textContent = t('err.avatar_invalid');
    return;
  }
  if (file.size > MAX_AVATAR_FILE_BYTES) {
    error.textContent = t('err.avatar_too_large');
    return;
  }

  const form = new FormData();
  form.append('avatar', file);

  const button = $('avatar-upload');
  button.disabled = true;
  try {
    const response = await fetch('/api/account/avatar/', {
      method: 'POST',
      headers: authHeaders(),
      body: form,
    });
    let data = null;
    try {
      data = await response.json();
    } catch (exception) {
    }
    const result = { ok: response.ok, status: response.status, data };

    if (result.status === 401) {
      logout('err.session_expired');
      return;
    }
    if (!result.ok) {
      error.textContent = describeAccountError(result);
      return;
    }

    accountInfo = { ...accountInfo, avatar_url: result.data.avatar_url };
    applyAvatar();
    showProfileStatus(t('settings.saved'));
  } catch (exception) {
    error.textContent = t('err.network');
    console.error(exception);
  } finally {
    button.disabled = false;
    $('avatar-input').value = '';
  }
}

async function removeAvatar() {
  const error = $('avatar-error');
  error.textContent = '';
  try {
    const result = await api('/api/account/avatar/', { method: 'DELETE', headers: authHeaders() });
    if (result.status === 401) {
      logout('err.session_expired');
      return;
    }
    if (!result.ok) {
      error.textContent = describeAccountError(result);
      return;
    }
    accountInfo = { ...accountInfo, avatar_url: null };
    applyAvatar();
    showProfileStatus(t('settings.saved'));
  } catch (exception) {
    error.textContent = t('err.network');
    console.error(exception);
  }
}

function initAvatar() {
  $('avatar-upload').addEventListener('click', () => $('avatar-input').click());
  $('avatar-input').addEventListener('change', (event) => uploadAvatar(event.target.files[0]));
  $('avatar-remove').addEventListener('click', removeAvatar);
}