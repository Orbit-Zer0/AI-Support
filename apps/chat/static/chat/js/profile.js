let profileStatusTimer = null;

function showProfileStatus(text, isError = false) {
  const element = $('settings-status');
  element.textContent = text;
  element.classList.toggle('error', isError);
  clearTimeout(profileStatusTimer);
  profileStatusTimer = setTimeout(() => { element.textContent = ''; }, 5000);
}

function describeAccountError(result) {
  if (result.status === 429) return throttledMessage(result.data);
  if (result.data && result.data.codes) return formatErrors(result.data);
  return describeChatError(result);
}


function fillProfileSelects() {
  const countrySelect = $('profile-country');
  const languageSelect = $('profile-language');
  const labelOf = makeCountryLabeler();

  countrySelect.replaceChildren();
  for (const item of countryItems) {
    countrySelect.append(new Option(labelOf(item), item.code));
  }
  languageSelect.replaceChildren();
  for (const item of languageItems) {
    languageSelect.append(new Option(item.name, item.code));
  }

  if (accountInfo) {
    countrySelect.value = accountInfo.country || '';
    languageSelect.value = accountInfo.language || '';
  }
}

function syncProfileControls() {
  const info = accountInfo;
  $('profile-username').textContent =
    info ? info.username : (localStorage.getItem(USERNAME_KEY) || '');

  const email = info && info.email;
  $('profile-email').textContent = email || t('profile.emailNone');

  const status = $('profile-email-status');
  const resend = $('profile-resend');
  if (!email) {
    status.hidden = true;
    resend.hidden = true;
  } else {
    status.hidden = false;
    status.textContent = info.email_verified
      ? t('profile.emailVerified')
      : t('profile.emailUnverified');
    status.classList.toggle('ok', Boolean(info.email_verified));
    status.classList.toggle('warn', !info.email_verified);
    resend.hidden = Boolean(info.email_verified);
  }

  fillProfileSelects();
  applyAvatar();
}

async function saveLocale(patch) {
  try {
    const result = await api('/api/account/', {
      method: 'PATCH',
      headers: authHeaders(),
      body: JSON.stringify(patch),
    });
    if (result.status === 401) {
      logout('err.session_expired');
      return;
    }
    if (!result.ok) {
      showProfileStatus(describeAccountError(result), true);
      syncProfileControls();
      return;
    }
    accountInfo = { ...accountInfo, ...result.data };
    if (patch.language) setLanguage(result.data.language);
    syncProfileControls();
    showProfileStatus(t('settings.saved'));
  } catch (error) {
    showProfileStatus(t('err.network'), true);
    syncProfileControls();
    console.error(error);
  }
}


async function submitProfileForm(form, errorId, run) {
  const error = $(errorId);
  error.textContent = '';
  const button = form.querySelector('button[type="submit"]');
  button.disabled = true;
  try {
    await run(error);
  } catch (exception) {
    error.textContent = t('err.network');
    console.error(exception);
  } finally {
    button.disabled = false;
  }
}


function onEmailSubmit(event) {
  event.preventDefault();
  const form = $('email-form');
  $('email-form-ok').textContent = '';

  submitProfileForm(form, 'email-form-error', async (error) => {
    const body = Object.fromEntries(new FormData(form));
    const result = await api('/api/account/email/', {
      method: 'POST',
      headers: authHeaders(),
      body: JSON.stringify(body),
    });
    if (result.status === 401) {
      logout('err.session_expired');
      return;
    }
    if (!result.ok) {
      error.textContent = describeAccountError(result);
      return;
    }

    accountInfo = {
      ...accountInfo,
      email: result.data.email,
      email_verified: result.data.email_verified,
    };
    form.reset();
    hideAllPasswords();
    $('email-form-ok').textContent = result.data.email_sent
      ? t('profile.emailSent').replace('{email}', result.data.email)
      : t('profile.emailNotSent');
    updateEmailBanner();
    syncProfileControls();
  });
}

async function resendFromProfile() {
  const button = $('profile-resend');
  button.disabled = true;
  try {
    const result = await api('/api/email/resend/', { method: 'POST', headers: authHeaders() });
    if (result.status === 401) {
      logout('err.session_expired');
      return;
    }
    if (!result.ok) {
      showProfileStatus(describeAccountError(result), true);
      return;
    }
    if (result.data && result.data.email_verified) {
      await refreshAccount();
      showProfileStatus(t('email.verified'));
    } else {
      showProfileStatus(t('email.sent').replace('{email}', accountInfo ? accountInfo.email : ''));
    }
  } catch (error) {
    showProfileStatus(t('err.network'), true);
    console.error(error);
  } finally {
    button.disabled = false;
  }
}


function onPasswordSubmit(event) {
  event.preventDefault();
  const form = $('password-form');
  $('password-form-ok').textContent = '';

  submitProfileForm(form, 'password-form-error', async (error) => {
    const body = Object.fromEntries(new FormData(form));
    if (body.new_password !== body.new_password_confirm) {
      error.textContent = t('err.password_mismatch');
      return;
    }
    delete body.new_password_confirm;

    const result = await api('/api/account/password/', {
      method: 'POST',
      headers: authHeaders(),
      body: JSON.stringify(body),
    });
    if (result.status === 401) {
      logout('err.session_expired');
      return;
    }
    if (!result.ok) {
      error.textContent = describeAccountError(result);
      return;
    }

    localStorage.setItem(TOKEN_KEY, result.data.token);
    form.reset();
    hideAllPasswords();
    $('password-form-ok').textContent = t('profile.passwordChanged');
  });
}


async function exportData() {
  const button = $('export-btn');
  const error = $('export-error');
  error.textContent = '';
  button.disabled = true;
  try {
    const result = await api('/api/account/export/', { headers: authHeaders() });
    if (result.status === 401) {
      logout('err.session_expired');
      return;
    }
    if (!result.ok) {
      error.textContent = result.status === 429
        ? throttledMessage(result.data)
        : t('profile.exportFailed');
      return;
    }

    const blob = new Blob([JSON.stringify(result.data, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `ai-support-export-${new Date().toISOString().slice(0, 10)}.json`;
    document.body.append(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  } catch (exception) {
    error.textContent = t('err.network');
    console.error(exception);
  } finally {
    button.disabled = false;
  }
}

async function logoutEverywhere() {
  if (!window.confirm(t('confirm.logoutAll'))) return;
  try {
    const result = await api('/api/account/logout-all/', {
      method: 'POST',
      headers: authHeaders(),
    });
    if (result.ok || result.status === 401) {
      logout();
      return;
    }
    showProfileStatus(describeAccountError(result), true);
  } catch (error) {
    showProfileStatus(t('err.network'), true);
    console.error(error);
  }
}

function openDeleteDialog() {
  $('delete-form').reset();
  hideAllPasswords();
  $('delete-error').textContent = '';
  $('settings-dialog').close();
  $('delete-dialog').showModal();
}

function onDeleteSubmit(event) {
  event.preventDefault();
  const form = $('delete-form');

  submitProfileForm(form, 'delete-error', async (error) => {
    const body = Object.fromEntries(new FormData(form));
    const result = await api('/api/account/delete/', {
      method: 'POST',
      headers: authHeaders(),
      body: JSON.stringify(body),
    });
    if (result.status === 401) {
      logout('err.session_expired');
      return;
    }
    if (!result.ok) {
      error.textContent = describeAccountError(result);
      return;
    }

    form.reset();
    hideAllPasswords();
    logout();
    setAuthNotice('delete.done');
  });
}

function initProfile() {
  $('profile-country').addEventListener('change', (event) => {
    saveLocale({ country: event.target.value });
  });
  $('profile-language').addEventListener('change', (event) => {
    saveLocale({ language: event.target.value });
  });

  $('email-form').addEventListener('submit', onEmailSubmit);
  $('password-form').addEventListener('submit', onPasswordSubmit);
  $('profile-resend').addEventListener('click', resendFromProfile);

  $('export-btn').addEventListener('click', exportData);
  $('logout-all').addEventListener('click', logoutEverywhere);

  $('delete-account-btn').addEventListener('click', openDeleteDialog);
  $('delete-cancel').addEventListener('click', () => $('delete-dialog').close());
  $('delete-form').addEventListener('submit', onDeleteSubmit);
}