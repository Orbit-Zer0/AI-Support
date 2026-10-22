const SECTION_LABELS = {
  appearance: 'settings.appearance',
  ai: 'settings.ai',
  profile: 'settings.profile',
  hotkeys: 'settings.hotkeys',
};

const SETTINGS_INDEX = [
  { id: 'theme', section: 'appearance', label: 'theme.label', keywords: 'kw.theme' },
  { id: 'colors', section: 'appearance', label: 'colors.title', keywords: 'kw.colors' },
  { id: 'font-size', section: 'appearance', label: 'font.size', keywords: 'kw.fontSize' },
  { id: 'font-family', section: 'appearance', label: 'font.family', keywords: 'kw.fontFamily' },
  { id: 'logout', section: 'profile', label: 'btn.logout', keywords: 'kw.logout' },
];

let activeSection = 'appearance';
let pendingPatch = {};
let saveTimer = null;
let saveInFlight = false;
let statusTimer = null;


function showSettingsSection(name) {
  activeSection = name;
  document.querySelectorAll('.settings-tab').forEach((tab) => {
    const active = tab.dataset.section === name;
    tab.classList.toggle('active', active);
    tab.setAttribute('aria-current', active ? 'page' : 'false');
  });
  document.querySelectorAll('.settings-panel').forEach((panel) => {
    panel.hidden = panel.dataset.section !== name;
  });
  $('settings-results').hidden = true;
  document.querySelector('.settings-content').scrollTop = 0;
}

function searchSettings(query) {
  const tokens = query.toLowerCase().split(/\s+/).filter(Boolean);
  if (tokens.length === 0) return [];

  const entries = [
    ...Object.entries(SECTION_LABELS).map(([section, label]) => ({
      section, id: null, label, keywords: null,
    })),
    ...SETTINGS_INDEX,
  ];
  return entries.filter((entry) => {
    const text = (t(entry.label) + ' ' + (entry.keywords ? t(entry.keywords) : '')).toLowerCase();
    return tokens.every((token) => text.includes(token));
  });
}

function goToSetting(entry) {
  $('settings-search').value = '';
  showSettingsSection(entry.section);
  if (!entry.id) return;

  const target = document.querySelector(`[data-setting="${entry.id}"]`);
  if (!target) return;
  target.scrollIntoView({ block: 'center', behavior: 'smooth' });
  target.classList.add('flash');
  setTimeout(() => target.classList.remove('flash'), 1400);
}

function renderSearchResults(query) {
  const box = $('settings-results');
  if (!query.trim()) {
    showSettingsSection(activeSection);
    return;
  }

  document.querySelectorAll('.settings-panel').forEach((panel) => { panel.hidden = true; });
  box.replaceChildren();
  box.hidden = false;

  const results = searchSettings(query);
  if (results.length === 0) {
    const empty = document.createElement('p');
    empty.className = 'settings-soon';
    empty.textContent = t('settings.noResults');
    box.append(empty);
    return;
  }

  for (const entry of results) {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'settings-result';

    const title = document.createElement('span');
    title.textContent = t(entry.label);
    button.append(title);

    if (entry.id) {
      const section = document.createElement('small');
      section.textContent = t(SECTION_LABELS[entry.section]);
      button.append(section);
    }
    button.addEventListener('click', () => goToSetting(entry));
    box.append(button);
  }
}

function cssColor(variableName) {
  const value = getComputedStyle(document.documentElement).getPropertyValue(variableName).trim();
  return HEX_COLOR.test(value) ? value : '#000000';
}

function syncAppearanceControls() {
  const appearance = currentAppearance;
  const dialog = $('settings-dialog');

  for (const name of ['theme', 'font_size', 'font_family']) {
    const radio = dialog.querySelector(`input[name="${name}"][value="${appearance[name]}"]`);
    if (radio) radio.checked = true;
  }

  const colors = [['user_bubble', '--user-bubble'], ['bot_bubble', '--bot-bubble']];
  for (const [key, cssVariable] of colors) {
    const input = dialog.querySelector(`input[data-color="${key}"]`);
    const value = appearance[key] || cssColor(cssVariable);
    if (input.value !== value) input.value = value;
    dialog.querySelector(`.default-tag[data-for="${key}"]`).hidden = Boolean(appearance[key]);
    dialog.querySelector(`[data-reset="${key}"]`).hidden = !appearance[key];
  }
}

function setSettingsStatus(key, isError = false) {
  const element = $('settings-status');
  element.textContent = t(key);
  element.classList.toggle('error', isError);
  clearTimeout(statusTimer);
  if (key === 'settings.saved') {
    statusTimer = setTimeout(() => { element.textContent = ''; }, 2000);
  }
}

function onAppearanceChange(patch) {
  applyAppearance({ ...currentAppearance, ...patch });
  cacheAppearance(currentAppearance);
  syncAppearanceControls();

  Object.assign(pendingPatch, patch);
  setSettingsStatus('settings.saving');
  clearTimeout(saveTimer);
  saveTimer = setTimeout(flushSettings, 600);
}

async function flushSettings() {
  if (saveInFlight) {
    saveTimer = setTimeout(flushSettings, 300);
    return;
  }
  if (Object.keys(pendingPatch).length === 0) return;
  if (!localStorage.getItem(TOKEN_KEY)) {
    pendingPatch = {};
    return;
  }

  const patch = pendingPatch;
  pendingPatch = {};
  saveInFlight = true;
  try {
    const result = await api('/api/settings/', {
      method: 'PATCH',
      headers: authHeaders(),
      body: JSON.stringify({ appearance: patch }),
    });
    if (result.status === 401) {
      logout('err.session_expired');
      return;
    }
    if (!result.ok) {
      pendingPatch = { ...patch, ...pendingPatch };
      setSettingsStatus('settings.saveFailed', true);
      return;
    }
    setSettingsStatus('settings.saved');
  } catch (error) {
    pendingPatch = { ...patch, ...pendingPatch };
    setSettingsStatus('settings.saveFailed', true);
    console.error(error);
  } finally {
    saveInFlight = false;
  }
}

async function loadServerSettings() {
  try {
    const result = await api('/api/settings/', { headers: authHeaders() });
    if (result.status === 401) {
      logout('err.session_expired');
      return;
    }
    if (!result.ok || !result.data || !result.data.appearance) return;

    pendingPatch = {};
    applyAppearance(result.data.appearance);
    cacheAppearance(currentAppearance);
    syncAppearanceControls();
  } catch (error) {
    console.error(error);
  }
}


function openSettings(section = 'appearance') {
  const dialog = $('settings-dialog');
  $('settings-search').value = '';
  showSettingsSection(section);
  syncAppearanceControls();
  if (!dialog.open) dialog.showModal();
}

function initSettings() {
  const dialog = $('settings-dialog');

  document.querySelectorAll('.settings-tab').forEach((tab) => {
    tab.addEventListener('click', () => {
      $('settings-search').value = '';
      showSettingsSection(tab.dataset.section);
    });
  });

  $('settings-search').addEventListener('input', (event) => {
    renderSearchResults(event.target.value);
  });

  $('settings-close').addEventListener('click', () => dialog.close());
  dialog.addEventListener('click', (event) => {
    if (event.target === dialog) dialog.close();
  });
  dialog.addEventListener('close', () => { $('settings-search').value = ''; });

  dialog.querySelectorAll('input[type="radio"]').forEach((radio) => {
    radio.addEventListener('change', () => {
      if (radio.checked) onAppearanceChange({ [radio.name]: radio.value });
    });
  });

  dialog.querySelectorAll('input[data-color]').forEach((input) => {
    input.addEventListener('input', () => {
      onAppearanceChange({ [input.dataset.color]: input.value });
    });
  });

  dialog.querySelectorAll('[data-reset]').forEach((button) => {
    button.addEventListener('click', () => {
      onAppearanceChange({ [button.dataset.reset]: null });
    });
  });

  $('settings-reset').addEventListener('click', () => {
    onAppearanceChange({ ...APPEARANCE_DEFAULTS });
  });

  $('settings-logout').addEventListener('click', () => {
    dialog.close();
    logout();
  });
}