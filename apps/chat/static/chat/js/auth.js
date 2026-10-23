let countryItems = [];
let languageItems = [];
let optionsLoaded = false;

let accountInfo = null;

let pendingReset = null;


function makeCountryLabeler() {
  let names = null;
  try {
    names = new Intl.DisplayNames([currentLang], { type: 'region' });
  } catch (error) {
  }
  return (item) => {
    try {
      const label = names && names.of(item.code);
      if (label && label !== item.code) return label;
    } catch (error) {
    }
    return item.name;
  };
}

function renderSelects() {
  const countrySelect = $('reg-country');
  const previous = countrySelect.value;
  countrySelect.replaceChildren(
    new Option(optionsLoaded ? t('select.country') : t('select.loading'), '')
  );
  const labelOf = makeCountryLabeler();
  for (const item of countryItems) {
    countrySelect.append(new Option(labelOf(item), item.code));
  }
  countrySelect.value = previous;

  const languageSelect = $('ui-language');
  languageSelect.replaceChildren();
  for (const item of languageItems) {
    languageSelect.append(new Option(item.name, item.code));
  }
  languageSelect.value = currentLang;
}

function setLanguage(code) {
  currentLang = code || FALLBACK_LANG;
  localStorage.setItem(LANG_KEY, currentLang);
  applyTranslations();
  renderSelects();
}

async function loadOptions() {
  try {
    const [countries, languages] = await Promise.all([
      api('/api/countries/'),
      api('/api/languages/'),
    ]);
    if (!countries.ok || !languages.ok) {
      throw new Error('Не удалось получить списки');
    }
    countryItems = countries.data;
    languageItems = languages.data;
    optionsLoaded = true;
  } catch (error) {
    languageItems = Object.keys(STRINGS).map((code) => ({
      code,
      name: NATIVE_NAMES[code] || code,
    }));
    $('register-error').textContent = t('err.optionsLoad');
    console.error(error);
  }
  renderSelects();
}


const EYE_ICONS = `
  <svg class="icon-eye" viewBox="0 0 24 24" width="20" height="20" fill="none"
       stroke="currentColor" stroke-width="2" stroke-linecap="round"
       stroke-linejoin="round" aria-hidden="true">
    <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/>
    <circle cx="12" cy="12" r="3"/>
  </svg>
  <svg class="icon-eye-off" viewBox="0 0 24 24" width="20" height="20" fill="none"
       stroke="currentColor" stroke-width="2" stroke-linecap="round"
       stroke-linejoin="round" aria-hidden="true">
    <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"/>
    <line x1="1" y1="1" x2="23" y2="23"/>
  </svg>`;

function setPasswordVisible(field, visible) {
  const input = field.querySelector('input');
  const button = field.querySelector('.toggle-password');
  input.type = visible ? 'text' : 'password';
  button.classList.toggle('is-visible', visible);
  button.setAttribute('aria-pressed', String(visible));
  button.dataset.i18nAriaLabel = visible ? 'password.hide' : 'password.show';
  button.setAttribute('aria-label', t(button.dataset.i18nAriaLabel));
}

function initPasswordToggles() {
  document.querySelectorAll('.password-field').forEach((field) => {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'toggle-password';
    button.innerHTML = EYE_ICONS;
    field.append(button);
    setPasswordVisible(field, false);

    button.addEventListener('click', () => {
      const input = field.querySelector('input');
      setPasswordVisible(field, input.type === 'password');
    });
  });
}

function hideAllPasswords() {
  document.querySelectorAll('.password-field').forEach((field) => {
    setPasswordVisible(field, false);
  });
}


function showView(name) {
  $('auth-view').hidden = name !== 'auth';
  $('chat-view').hidden = name !== 'chat';
}

const AUTH_FORMS = ['login', 'register', 'forgot', 'reset'];

function setAuthNoticeText(text, isError = false) {
  const box = $('auth-notice');
  box.textContent = text || '';
  box.classList.toggle('error', Boolean(text) && isError);
  box.hidden = !text;
}

function setAuthNotice(key, isError = false) {
  setAuthNoticeText(key ? t(key) : '', isError);
}

function showAuthForm(name) {
  for (const form of AUTH_FORMS) {
    $(`${form}-form`).hidden = form !== name;
  }
  $('auth-tabs').hidden = !(name === 'login' || name === 'register');
  document.querySelectorAll('.tab').forEach((button) => {
    button.classList.toggle('active', button.dataset.tab === name);
  });
  for (const form of AUTH_FORMS) {
    $(`${form}-error`).textContent = '';
  }
}

function switchTab(name) {
  showAuthForm(name);
  setAuthNotice(null);
}


function saveSession(data) {
  localStorage.setItem(TOKEN_KEY, data.token);
  localStorage.setItem(USERNAME_KEY, data.username);
}

function clearSession() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USERNAME_KEY);
}

function enterApp() {
  $('whoami').textContent = localStorage.getItem(USERNAME_KEY) || '';
  closeSidebarDrawer();
  resetChat();
  showView('chat');
  refreshChatList();
  maybeShowNotice();
  loadServerSettings();
  refreshAccount();
}

function logout(errorKey) {
  clearSession();
  accountInfo = null;
  pendingReset = null;
  hideBanner();
  document.querySelectorAll('dialog[open]').forEach((dialog) => dialog.close());
  closeUserMenu();
  setRailOpen(false);
  closeSidebarDrawer();
  resetChat();
  clearChatList();
  hideAllPasswords();
  showView('auth');
  switchTab('login');
  if (errorKey) {
    $('login-error').textContent = t(errorKey);
  }
}


let bannerTimer = null;
let bannerLocked = false;

function showBanner(text, { action = false, autoHide = 0 } = {}) {
  clearTimeout(bannerTimer);
  bannerLocked = autoHide > 0;
  $('email-banner-text').textContent = text;
  $('email-resend').hidden = !action;
  $('email-banner').hidden = false;
  if (autoHide) {
    bannerTimer = setTimeout(() => {
      bannerLocked = false;
      updateEmailBanner();
    }, autoHide);
  }
}

function hideBanner() {
  clearTimeout(bannerTimer);
  bannerLocked = false;
  $('email-banner').hidden = true;
}

function updateEmailBanner() {
  if (bannerLocked) return;
  if (accountInfo && accountInfo.email && !accountInfo.email_verified) {
    showBanner(t('email.unverified').replace('{email}', accountInfo.email), { action: true });
  } else {
    hideBanner();
  }
}

async function refreshAccount() {
  try {
    const result = await api('/api/account/', { headers: authHeaders() });
    if (result.status === 401) {
      logout('err.session_expired');
      return;
    }
    if (!result.ok || !result.data) return;
    accountInfo = result.data;
    $('whoami').textContent = accountInfo.username;
    updateEmailBanner();
  } catch (error) {
    console.error(error);
  }
}

async function resendVerification() {
  const button = $('email-resend');
  button.disabled = true;
  try {
    const result = await api('/api/email/resend/', { method: 'POST', headers: authHeaders() });
    if (result.status === 401) {
      logout('err.session_expired');
      return;
    }

    let message;
    if (result.ok) {
      if (result.data && result.data.email_verified) {
        await refreshAccount();
        message = t('email.verified');
      } else {
        message = t('email.sent').replace('{email}', accountInfo ? accountInfo.email : '');
      }
    } else if (result.status === 429) {
      message = throttledMessage(result.data);
    } else {
      message = describeChatError(result);
    }
    showBanner(message, { autoHide: 6000 });
  } catch (error) {
    showBanner(t('err.network'), { autoHide: 6000 });
    console.error(error);
  } finally {
    button.disabled = false;
  }
}


const AUTH_ENDPOINTS = {
  login: '/api/login/',
  register: '/api/register/',
  forgot: '/api/password/forgot/',
  reset: '/api/password/reset/',
};

async function submitAuth(kind) {
  const form = $(`${kind}-form`);
  const errorElement = $(`${kind}-error`);
  errorElement.textContent = '';
  const body = Object.fromEntries(new FormData(form));

  if (kind === 'register' || kind === 'reset') {
    if (body.password !== body.password_confirm) {
      errorElement.textContent = t('err.password_mismatch');
      return;
    }
    delete body.password_confirm;
  }
  if (kind === 'register') {
    body.language = currentLang;
  }
  if (kind === 'reset') {
    if (!pendingReset) {
      errorElement.textContent = t('err.invalid_token');
      return;
    }
    body.uid = pendingReset.uid;
    body.token = pendingReset.token;
  }

  const button = form.querySelector('button[type="submit"]');
  button.disabled = true;

  try {
    const result = await api(AUTH_ENDPOINTS[kind], { method: 'POST', body: JSON.stringify(body) });

    if (!result.ok) {
      errorElement.textContent = result.status === 429
        ? throttledMessage(result.data)
        : formatErrors(result.data);
      return;
    }

    if (kind === 'forgot') {
      form.reset();
      showAuthForm('login');
      setAuthNotice('forgot.sent');
      return;
    }
    if (kind === 'reset') {
      form.reset();
      hideAllPasswords();
      pendingReset = null;
      showAuthForm('login');
      setAuthNotice('reset.done');
      return;
    }

    saveSession(result.data);
    if (result.data.language) setLanguage(result.data.language);
    form.reset();
    hideAllPasswords();
    setAuthNotice(null);
    enterApp();
  } catch (error) {
    errorElement.textContent = t('err.network');
    console.error(error);
  } finally {
    button.disabled = false;
  }
}


async function verifyEmail(token) {
  const loggedIn = Boolean(localStorage.getItem(TOKEN_KEY));
  let ok = false;
  let message;

  try {
    const result = await api('/api/email/verify/', {
      method: 'POST',
      body: JSON.stringify({ token }),
    });
    ok = result.ok;
    if (ok) {
      message = t('email.verified');
    } else if (result.status === 429) {
      message = throttledMessage(result.data);
    } else {
      message = formatErrors(result.data);
    }
  } catch (error) {
    message = t('err.network');
    console.error(error);
  }

  if (loggedIn) {
    if (ok) await refreshAccount();
    showBanner(message, { autoHide: 7000 });
  } else {
    setAuthNoticeText(message, !ok);
  }
}

function openResetForm(value) {
  const dot = value.indexOf('.');
  if (dot <= 0) return false;

  pendingReset = { uid: value.slice(0, dot), token: value.slice(dot + 1) };
  clearSession();
  showView('auth');
  showAuthForm('reset');
  setAuthNotice(null);
  return true;
}

async function start() {
  const params = new URLSearchParams(window.location.search);
  const verifyToken = params.get('verify');
  const resetValue = params.get('reset');

  if (verifyToken || resetValue) {
    window.history.replaceState(null, '', window.location.pathname);
  }

  if (resetValue && openResetForm(resetValue)) return;

  if (localStorage.getItem(TOKEN_KEY)) {
    enterApp();
  } else {
    showView('auth');
    if (resetValue) setAuthNotice('err.invalid_token', true);
  }

  if (verifyToken) await verifyEmail(verifyToken);
}