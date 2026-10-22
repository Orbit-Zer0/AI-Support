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
  { id: 'ai-preset', section: 'ai', label: 'ai.preset', keywords: 'kw.aiPreset' },
  { id: 'ai-sliders', section: 'ai', label: 'ai.custom', keywords: 'kw.aiTone' },
  { id: 'ai-emoji', section: 'ai', label: 'ai.emoji', keywords: 'kw.aiEmoji' },
  { id: 'logout', section: 'profile', label: 'btn.logout', keywords: 'kw.logout' },
];

let activeSection = 'appearance';
let pendingPatch = {};
let saveTimer = null;
let saveInFlight = false;
let statusTimer = null;

const AI_DEFAULTS = { preset: 'balanced', warmth: 3, enthusiasm: 2, emoji: 'off' };

const AI_PRESETS = {
  balanced: { warmth: 3, enthusiasm: 2, emoji: 'off' },
  gentle: { warmth: 5, enthusiasm: 2, emoji: 'rare' },
  calm: { warmth: 3, enthusiasm: 1, emoji: 'off' },
  direct: { warmth: 2, enthusiasm: 2, emoji: 'off' },
  upbeat: { warmth: 4, enthusiasm: 5, emoji: 'often' },
};
const AI_PRESET_NAMES = [...Object.keys(AI_PRESETS), 'custom'];
const AI_EMOJI_VALUES = ['off', 'rare', 'often'];

let currentAiStyle = { ...AI_DEFAULTS };

function isLevel(value) {
  return Number.isInteger(value) && value >= 1 && value <= 5;
}

function sanitizeAiStyle(raw) {
  const result = { ...AI_DEFAULTS };
  if (!raw || typeof raw !== 'object') return result;
  if (isLevel(raw.warmth)) result.warmth = raw.warmth;
  if (isLevel(raw.enthusiasm)) result.enthusiasm = raw.enthusiasm;
  if (AI_EMOJI_VALUES.includes(raw.emoji)) result.emoji = raw.emoji;
  if (AI_PRESET_NAMES.includes(raw.preset)) result.preset = raw.preset;
  return result;
}

function detectPreset(style) {
  for (const [name, values] of Object.entries(AI_PRESETS)) {
    if (
      values.warmth === style.warmth &&
      values.enthusiasm === style.enthusiasm &&
      values.emoji === style.emoji
    ) {
      return name;
    }
  }
  return 'custom';
}

function syncAiControls() {
  const dialog = $('settings-dialog');
  const style = currentAiStyle;

  const preset = dialog.querySelector(`input[data-ai="preset"][value="${style.preset}"]`);
  if (preset) preset.checked = true;
  const emoji = dialog.querySelector(`input[data-ai="emoji"][value="${style.emoji}"]`);
  if (emoji) emoji.checked = true;

  for (const key of ['warmth', 'enthusiasm']) {
    const slider = dialog.querySelector(`input[type="range"][data-ai="${key}"]`);
    slider.value = String(style[key]);
    $(`ai-${key}-value`).textContent = `${style[key]} / 5`;
  }
}

function onAiStyleChange(patch) {
  const merged = { ...currentAiStyle, ...patch };
  if (!('preset' in patch)) merged.preset = detectPreset(merged);
  currentAiStyle = merged;

  queuePatch('ai_style', { ...patch, preset: merged.preset });
  syncAiControls();
}


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

  const resolved = resolveBubbleColors(appearance, effectiveTheme(appearance.theme));
  const colors = [
    ['user_bubble', resolved.userCustom, resolved.user],
    ['bot_bubble', resolved.botCustom, resolved.bot],
  ];
  for (const [key, custom, shown] of colors) {
    const input = dialog.querySelector(`input[data-color="${key}"]`);
    if (input.value !== shown) input.value = shown;
    dialog.querySelector(`.default-tag[data-for="${key}"]`).hidden = Boolean(custom);
    dialog.querySelector(`[data-reset="${key}"]`).hidden = !custom;
  }
}

function syncSettingsControls() {
  syncAppearanceControls();
  syncAiControls();
}


function setSettingsStatus(key, isError = false) {
  const element = $('settings-status');
  element.textContent = t(key);
  element.classList.toggle('error', isError);
  clearTimeout(statusTimer);
  const clearAfter = { 'settings.saved': 2000, 'colors.tooSimilar': 4000 }[key];
  if (clearAfter) {
    statusTimer = setTimeout(() => { element.textContent = ''; }, clearAfter);
  }
}

function mergePatches(first, second) {
  const result = {};
  for (const source of [first, second]) {
    for (const [section, values] of Object.entries(source)) {
      result[section] = { ...(result[section] || {}), ...values };
    }
  }
  return result;
}

function queuePatch(section, patch) {
  pendingPatch = mergePatches(pendingPatch, { [section]: patch });
  setSettingsStatus('settings.saving');
  clearTimeout(saveTimer);
  saveTimer = setTimeout(flushSettings, 600);
}

function onColorChange(key, value) {
  const candidate = { ...currentAppearance, [key]: value };
  const resolved = resolveBubbleColors(candidate, effectiveTheme(candidate.theme));

  const rejected =
    resolved.userCustom !== candidate.user_bubble ||
    resolved.botCustom !== candidate.bot_bubble;
  if (rejected) {
    setSettingsStatus('colors.tooSimilar', true);
    return;
  }
  onAppearanceChange({ [key]: value });
}

function onAppearanceChange(patch) {
  applyAppearance({ ...currentAppearance, ...patch });
  cacheAppearance(currentAppearance);
  syncAppearanceControls();
  queuePatch('appearance', patch);
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
      body: JSON.stringify(patch),
    });
    if (result.status === 401) {
      logout('err.session_expired');
      return;
    }
    if (!result.ok) {
      pendingPatch = mergePatches(patch, pendingPatch);
      setSettingsStatus('settings.saveFailed', true);
      return;
    }
    setSettingsStatus('settings.saved');
  } catch (error) {
    pendingPatch = mergePatches(patch, pendingPatch);
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
    if (!result.ok || !result.data) return;

    pendingPatch = {};
    if (result.data.appearance) {
      applyAppearance(result.data.appearance);
      cacheAppearance(currentAppearance);
    }
    if (result.data.ai_style) {
      currentAiStyle = sanitizeAiStyle(result.data.ai_style);
    }
    syncSettingsControls();
  } catch (error) {
    console.error(error);
  }
}


function openSettings(section = 'appearance') {
  setRailOpen(false);
  const dialog = $('settings-dialog');
  $('settings-search').value = '';
  showSettingsSection(section);
  syncSettingsControls();
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

  dialog.querySelectorAll('input[type="radio"]:not([data-ai])').forEach((radio) => {
    radio.addEventListener('change', () => {
      if (radio.checked) onAppearanceChange({ [radio.name]: radio.value });
    });
  });

  dialog.querySelectorAll('input[data-color]').forEach((input) => {
    input.addEventListener('input', () => onColorChange(input.dataset.color, input.value));
    input.addEventListener('change', syncAppearanceControls);
  });

  dialog.querySelectorAll('[data-reset]').forEach((button) => {
    button.addEventListener('click', () => onColorChange(button.dataset.reset, null));
  });
  $('settings-reset').addEventListener('click', () => {
    onAppearanceChange({ ...APPEARANCE_DEFAULTS });
  });

  dialog.querySelectorAll('input[data-ai="preset"]').forEach((radio) => {
    radio.addEventListener('change', () => {
      if (!radio.checked) return;
      const values = AI_PRESETS[radio.value];
      onAiStyleChange(values ? { preset: radio.value, ...values } : { preset: 'custom' });
    });
  });

  dialog.querySelectorAll('input[data-ai="emoji"]').forEach((radio) => {
    radio.addEventListener('change', () => {
      if (radio.checked) onAiStyleChange({ emoji: radio.value });
    });
  });

  dialog.querySelectorAll('input[type="range"][data-ai]').forEach((slider) => {
    slider.addEventListener('input', () => {
      onAiStyleChange({ [slider.dataset.ai]: Number(slider.value) });
    });
  });

  $('ai-reset').addEventListener('click', () => {
    onAiStyleChange({ ...AI_DEFAULTS });
  });

  $('settings-logout').addEventListener('click', () => {
    dialog.close();
    logout();
  });
}