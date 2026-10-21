const TOKEN_KEY = 'token';
const USERNAME_KEY = 'username';
const NOTICE_KEY = 'notice_seen';

const $ = (id) => document.getElementById(id);

function authHeaders() {
  return { Authorization: 'Token ' + localStorage.getItem(TOKEN_KEY) };
}

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

function throttledMessage(data) {
  const seconds = data && data.retry_after;
  if (!seconds) return t('err.ai_quota');
  if (seconds > 90) {
    return t('err.throttled_minutes').replace('{minutes}', Math.ceil(seconds / 60));
  }
  return t('err.throttled').replace('{seconds}', seconds);
}

function describeChatError(result) {
  const code = result.data && result.data.code;
  if (code === 'throttled') return throttledMessage(result.data);
  if (code) {
    const key = 'err.' + code;
    const text = t(key);
    if (text !== key) return text;
  }
  return t('err.generic');
}


const ICON_PATHS = {
  lifebuoy: '<circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="4"/><line x1="4.93" y1="4.93" x2="9.17" y2="9.17"/><line x1="14.83" y1="14.83" x2="19.07" y2="19.07"/><line x1="14.83" y1="9.17" x2="19.07" y2="4.93"/><line x1="4.93" y1="19.07" x2="9.17" y2="14.83"/>',
  sliders: '<line x1="4" y1="21" x2="4" y2="14"/><line x1="4" y1="10" x2="4" y2="3"/><line x1="12" y1="21" x2="12" y2="12"/><line x1="12" y1="8" x2="12" y2="3"/><line x1="20" y1="21" x2="20" y2="16"/><line x1="20" y1="12" x2="20" y2="3"/><line x1="1" y1="14" x2="7" y2="14"/><line x1="9" y1="8" x2="15" y2="8"/><line x1="17" y1="16" x2="23" y2="16"/>',
  palette: '<path d="M12 2.69l5.66 5.66a8 8 0 1 1-11.31 0z"/>',
  user: '<path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/>',
  command: '<path d="M18 3a3 3 0 0 0-3 3v12a3 3 0 0 0 3 3 3 3 0 0 0 3-3 3 3 0 0 0-3-3H6a3 3 0 0 0-3 3 3 3 0 0 0 3 3 3 3 0 0 0 3-3V6a3 3 0 0 0-3-3 3 3 0 0 0-3 3 3 3 0 0 0 3 3h12a3 3 0 0 0 3-3 3 3 0 0 0-3-3z"/>',
  logout: '<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/>',
  plus: '<line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>',
  search: '<circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>',
  'chevron-left': '<polyline points="15 18 9 12 15 6"/>',
  'chevron-right': '<polyline points="9 18 15 12 9 6"/>',
  menu: '<line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="18" x2="21" y2="18"/>',
  trash: '<polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/><path d="M10 11v6"/><path d="M14 11v6"/><path d="M9 6V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2"/>',
  edit: '<path d="M12 20h9"/><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"/>',
};

function renderIcons(root = document) {
  const targets = [...root.querySelectorAll('[data-icon]')];
  if (root.dataset && root.dataset.icon) targets.push(root);

  for (const element of targets) {
    const paths = ICON_PATHS[element.dataset.icon];
    if (!paths) continue;
    element.innerHTML =
      '<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" ' +
      'stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' +
      paths + '</svg>';
  }
}