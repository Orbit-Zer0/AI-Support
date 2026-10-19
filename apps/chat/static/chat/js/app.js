const TOKEN_KEY = 'token';
const USERNAME_KEY = 'username';

const $ = (id) => document.getElementById(id);

let countryItems = [];
let languageItems = [];
let optionsLoaded = false;

let conversationId = null;
let sending = false;


async function api(path, options = {}) {
  const headers = { 'Content-Type': 'application/json', ...(options.headers || {}) };
  const response = await fetch(path, { ...options, headers });

  let data = null;
  try {
    data = await response.json();
  } catch (error) {
  }
  return { ok: response.ok, status: response.status, data };
}


const ERROR_ALIASES = { blank: 'required', min_length: 'password_too_short' };

function describeError(field, rawCode) {
  const code = ERROR_ALIASES[rawCode] || rawCode;
  const key = 'err.' + code;
  const text = t(key);
  if (text === key) return t('err.generic');
  if (code === 'required') {
    return t('field.' + field) + ': ' + text;
  }
  return text;
}

function formatErrors(data) {
  const codes = data && data.codes;
  if (!codes || typeof codes !== 'object') return t('err.generic');

  const messages = [];
  for (const [field, list] of Object.entries(codes)) {
    for (const code of Array.isArray(list) ? list : [list]) {
      messages.push(describeError(field, code));
    }
  }
  return messages.length ? [...new Set(messages)].join(' ') : t('err.generic');
}

function describeChatError(result) {
  const code = result.data && result.data.code;
  if (code) {
    const key = 'err.' + code;
    const text = t(key);
    if (text !== key) return text;
  }
  return t('err.generic');
}



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

function switchTab(name) {
  document.querySelectorAll('.tab').forEach((button) => {
    button.classList.toggle('active', button.dataset.tab === name);
  });
  $('login-form').hidden = name !== 'login';
  $('register-form').hidden = name !== 'register';
  $('login-error').textContent = '';
  $('register-error').textContent = '';
}

function saveSession(data) {
  localStorage.setItem(TOKEN_KEY, data.token);
  localStorage.setItem(USERNAME_KEY, data.username);
}

function clearSession() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USERNAME_KEY);
}


const PURIFY_CONFIG = {
  ALLOWED_TAGS: [
    'p', 'br', 'hr', 'strong', 'em', 'b', 'i', 'del', 'code', 'pre',
    'ul', 'ol', 'li', 'blockquote', 'a',
    'h1', 'h2', 'h3', 'h4',
    'table', 'thead', 'tbody', 'tr', 'th', 'td',
  ],
  ALLOWED_ATTR: ['href'],
};

if (window.DOMPurify) {
  DOMPurify.addHook('afterSanitizeAttributes', (node) => {
    if (node.tagName === 'A') {
      node.setAttribute('target', '_blank');
      node.setAttribute('rel', 'noopener noreferrer');
    }
  });
}

function renderBotText(element, text) {
  if (window.marked && window.DOMPurify) {
    const html = String(marked.parse(text, { breaks: true }));
    element.innerHTML = DOMPurify.sanitize(html, PURIFY_CONFIG);
  } else {
    element.style.whiteSpace = 'pre-wrap';
    element.textContent = text;
  }
}

function scrollToBottom() {
  const box = $('messages');
  box.scrollTop = box.scrollHeight;
}

function addMessage(role, text) {
  const element = document.createElement('div');
  element.className = `message message-${role}`;
  if (role === 'bot') {
    renderBotText(element, text);
  } else {
    element.textContent = text;
  }
  $('messages').append(element);
  scrollToBottom();
  return element;
}

function addNotice(text) {
  const element = document.createElement('div');
  element.className = 'message-error';
  element.setAttribute('role', 'alert');
  element.textContent = text;
  $('messages').append(element);
  scrollToBottom();
  return element;
}

function addTyping() {
  const element = document.createElement('div');
  element.className = 'message message-bot message-typing';
  element.textContent = t('chat.typing');
  $('messages').append(element);
  scrollToBottom();
  return element;
}

function resetChat() {
  conversationId = null;
  $('messages').replaceChildren();
  addMessage('bot', t('welcome'));
}

function autoResizeInput() {
  const input = $('input');
  input.style.height = 'auto';
  input.style.height = Math.min(input.scrollHeight, 160) + 'px';
}

function setSending(value) {
  sending = value;
  $('send').disabled = value;
  $('input').disabled = value;
}

function enterChat() {
  $('whoami').textContent = localStorage.getItem(USERNAME_KEY) || '';
  resetChat();
  showView('chat');
}

function logout(errorKey) {
  clearSession();
  resetChat();
  hideAllPasswords();
  showView('auth');
  switchTab('login');
  if (errorKey) {
    $('login-error').textContent = t(errorKey);
  }
}

async function sendMessage() {
  const input = $('input');
  const text = input.value.trim();
  if (!text || sending) return;

  const token = localStorage.getItem(TOKEN_KEY);
  if (!token) {
    logout('err.session_expired');
    return;
  }

  setSending(true);
  const userBubble = addMessage('user', text);
  input.value = '';
  autoResizeInput();
  const typing = addTyping();

  try {
    const body = { message: text };
    if (conversationId !== null) body.conversation_id = conversationId;

    const result = await api('/api/chat/', {
      method: 'POST',
      headers: { Authorization: 'Token ' + token },
      body: JSON.stringify(body),
    });
    typing.remove();

    if (result.ok) {
      conversationId = result.data.conversation_id;
      const bubble = addMessage('bot', result.data.response);
      if (result.data.crisis) bubble.classList.add('message-crisis');
      return;
    }

    userBubble.remove();
    input.value = text;
    autoResizeInput();

    if (result.status === 401) {
      logout('err.session_expired');
    } else if (result.status === 404 && conversationId !== null) {
      conversationId = null;
      addNotice(t('err.conversation_not_found'));
    } else {
      addNotice(describeChatError(result));
    }
  } catch (error) {
    typing.remove();
    userBubble.remove();
    input.value = text;
    autoResizeInput();
    addNotice(t('err.network'));
    console.error(error);
  } finally {
    setSending(false);
    input.focus();
  }
}


async function submitAuth(form, path, errorElement) {
  errorElement.textContent = '';
  const body = Object.fromEntries(new FormData(form));

  if (path === '/api/register/') {
    if (body.password !== body.password_confirm) {
      errorElement.textContent = t('err.password_mismatch');
      return;
    }
    delete body.password_confirm;
    body.language = currentLang;
  }

  const button = form.querySelector('button[type="submit"]');
  button.disabled = true;

  try {
    const result = await api(path, { method: 'POST', body: JSON.stringify(body) });

    if (result.ok) {
      saveSession(result.data);
      if (result.data.language) setLanguage(result.data.language);
      form.reset();
      hideAllPasswords();
      enterChat();
    } else {
      errorElement.textContent = formatErrors(result.data);
    }
  } catch (error) {
    errorElement.textContent = t('err.network');
    console.error(error);
  } finally {
    button.disabled = false;
  }
}


document.querySelectorAll('.tab').forEach((button) => {
  button.addEventListener('click', () => switchTab(button.dataset.tab));
});

$('ui-language').addEventListener('change', (event) => {
  setLanguage(event.target.value);
});

$('login-form').addEventListener('submit', (event) => {
  event.preventDefault();
  submitAuth(event.target, '/api/login/', $('login-error'));
});

$('register-form').addEventListener('submit', (event) => {
  event.preventDefault();
  submitAuth(event.target, '/api/register/', $('register-error'));
});

$('logout').addEventListener('click', () => logout());

$('new-chat').addEventListener('click', () => {
  if (sending) return;
  resetChat();
  $('input').focus();
});

$('send').addEventListener('click', sendMessage);

$('input').addEventListener('keydown', (event) => {
  if (event.key === 'Enter' && !event.shiftKey && !event.isComposing) {
    event.preventDefault();
    sendMessage();
  }
});

$('input').addEventListener('input', autoResizeInput);

currentLang = detectLanguage();
initPasswordToggles();
applyTranslations();
renderSelects();
loadOptions();

if (localStorage.getItem(TOKEN_KEY)) {
  enterChat();
} else {
  showView('auth');
}