const APPEARANCE_KEY = 'appearance';

const APPEARANCE_DEFAULTS = {
  theme: 'auto',
  user_bubble: null,
  bot_bubble: null,
  font_size: 'medium',
  font_family: 'system',
};

const HEX_COLOR = /^#[0-9a-f]{6}$/i;
const THEMES = ['light', 'dark', 'auto'];
const FONT_SIZES = ['small', 'medium', 'large', 'xlarge'];
const FONT_FAMILIES = ['system', 'serif', 'mono', 'readable'];

let currentAppearance = { ...APPEARANCE_DEFAULTS };
const darkQuery = window.matchMedia('(prefers-color-scheme: dark)');


function sanitizeAppearance(raw) {
  const result = { ...APPEARANCE_DEFAULTS };
  if (!raw || typeof raw !== 'object') return result;

  if (THEMES.includes(raw.theme)) result.theme = raw.theme;
  if (FONT_SIZES.includes(raw.font_size)) result.font_size = raw.font_size;
  if (FONT_FAMILIES.includes(raw.font_family)) result.font_family = raw.font_family;
  for (const key of ['user_bubble', 'bot_bubble']) {
    if (typeof raw[key] === 'string' && HEX_COLOR.test(raw[key])) {
      result[key] = raw[key].toLowerCase();
    }
  }
  return result;
}


function hexToRgb(hex) {
  const number = parseInt(hex.slice(1), 16);
  return [(number >> 16) & 255, (number >> 8) & 255, number & 255];
}

function relativeLuminance([r, g, b]) {
  const channel = (value) => {
    const c = value / 255;
    return c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4);
  };
  return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b);
}

function contrastRatio(a, b) {
  const [light, dark] = a > b ? [a, b] : [b, a];
  return (light + 0.05) / (dark + 0.05);
}

function readableTextColor(hex) {
  const luminance = relativeLuminance(hexToRgb(hex));
  return contrastRatio(luminance, 1) >= contrastRatio(luminance, 0.01)
    ? '#ffffff'
    : '#111827';
}

function hueInfo(hex) {
  const [r, g, b] = hexToRgb(hex).map((value) => value / 255);
  const max = Math.max(r, g, b);
  const min = Math.min(r, g, b);
  const delta = max - min;

  let hue = 0;
  if (delta !== 0) {
    if (max === r) hue = ((g - b) / delta) % 6;
    else if (max === g) hue = (b - r) / delta + 2;
    else hue = (r - g) / delta + 4;
    hue *= 60;
    if (hue < 0) hue += 360;
  }
  const lightness = (max + min) / 2;
  const saturation = delta === 0 ? 0 : delta / (1 - Math.abs(2 * lightness - 1));
  return { hue, saturation, lightness };
}

function isYellowish(hex) {
  const { hue, saturation, lightness } = hueInfo(hex);
  return hue >= 25 && hue <= 75 && saturation >= 0.35 && lightness >= 0.25 && lightness <= 0.85;
}


function effectiveTheme(theme) {
  if (theme === 'auto') return darkQuery.matches ? 'dark' : 'light';
  return theme;
}

function setColorVariables(root, backgroundVar, textVar, hex) {
  if (hex) {
    root.style.setProperty(backgroundVar, hex);
    root.style.setProperty(textVar, readableTextColor(hex));
  } else {
    root.style.removeProperty(backgroundVar);
    root.style.removeProperty(textVar);
  }
}

function applyAppearance(raw) {
  const appearance = sanitizeAppearance(raw);
  currentAppearance = appearance;

  const root = document.documentElement;
  const theme = effectiveTheme(appearance.theme);
  root.dataset.theme = theme;
  root.dataset.fontSize = appearance.font_size;
  root.dataset.font = appearance.font_family;

  setColorVariables(root, '--user-bubble', '--user-text', appearance.user_bubble);
  setColorVariables(root, '--bot-bubble', '--bot-text', appearance.bot_bubble);

  const yellowish = [appearance.user_bubble, appearance.bot_bubble]
    .some((color) => color && isYellowish(color));
  if (yellowish) {
    root.style.setProperty('--crisis', theme === 'dark' ? '#f87171' : '#dc2626');
  } else {
    root.style.removeProperty('--crisis');
  }
}


function cacheAppearance(appearance) {
  try {
    localStorage.setItem(APPEARANCE_KEY, JSON.stringify(appearance));
  } catch (error) {
  }
}

function loadCachedAppearance() {
  try {
    return JSON.parse(localStorage.getItem(APPEARANCE_KEY));
  } catch (error) {
    return null;
  }
}

darkQuery.addEventListener('change', () => {
  if (currentAppearance.theme === 'auto') applyAppearance(currentAppearance);
});

applyAppearance(loadCachedAppearance());