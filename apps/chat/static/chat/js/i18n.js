const STRINGS = {
  ru: {
    'tab.login': 'Вход',
    'tab.register': 'Регистрация',
    'label.username': 'Имя пользователя',
    'label.password': 'Пароль',
    'label.passwordNew': 'Пароль (не меньше 8 символов)',
    'label.passwordConfirm': 'Повтори пароль',
    'label.country': 'Страна',
    'label.language': 'Язык',
    'btn.login': 'Войти',
    'btn.register': 'Создать аккаунт',
    'btn.logout': 'Выйти',
    'btn.send': 'Отправить',
    'placeholder.message': 'Напиши сообщение...',
    'password.show': 'Показать пароль',
    'password.hide': 'Скрыть пароль',
    'select.loading': 'Загрузка...',
    'select.country': 'Выбери страну',
    'hint.language': 'Язык аккаунта выбирается в списке вверху.',
    'welcome': 'Привет! Я ИИ-помощник для эмоциональной поддержки.',
    'field.username': 'Имя пользователя',
    'field.password': 'Пароль',
    'field.country': 'Страна',
    'field.language': 'Язык',
    'err.generic': 'Что-то пошло не так. Попробуй ещё раз.',
    'err.network': 'Нет связи с сервером. Проверь подключение.',
    'err.optionsLoad': 'Не удалось загрузить списки стран и языков. Обнови страницу.',
    'err.password_mismatch': 'Пароли не совпадают.',
    'err.authorization': 'Неверное имя пользователя или пароль.',
    'err.username_taken': 'Это имя уже занято.',
    'err.password_too_common': 'Этот пароль слишком простой.',
    'err.password_entirely_numeric': 'Пароль не может состоять только из цифр.',
    'err.password_too_short': 'Пароль слишком короткий (нужно минимум 8 символов).',
    'err.password_too_similar': 'Пароль слишком похож на имя пользователя.',
    'err.unknown_country': 'Выбранная страна не поддерживается.',
    'err.unknown_language': 'Выбранный язык не поддерживается.',
    'err.required': 'Заполни это поле.',
    'err.max_length': 'Слишком длинное значение.',
  },

  en: {
    'tab.login': 'Log in',
    'tab.register': 'Sign up',
    'label.username': 'Username',
    'label.password': 'Password',
    'label.passwordNew': 'Password (at least 8 characters)',
    'label.passwordConfirm': 'Repeat password',
    'label.country': 'Country',
    'label.language': 'Language',
    'btn.login': 'Log in',
    'btn.register': 'Create account',
    'btn.logout': 'Log out',
    'btn.send': 'Send',
    'placeholder.message': 'Type a message...',
    'password.show': 'Show password',
    'password.hide': 'Hide password',
    'select.loading': 'Loading...',
    'select.country': 'Select your country',
    'hint.language': 'Your account language is the one selected at the top.',
    'welcome': "Hi! I'm an AI assistant for emotional support.",
    'field.username': 'Username',
    'field.password': 'Password',
    'field.country': 'Country',
    'field.language': 'Language',
    'err.generic': 'Something went wrong. Please try again.',
    'err.network': "Can't reach the server. Check your connection.",
    'err.optionsLoad': "Couldn't load countries and languages. Reload the page.",
    'err.password_mismatch': "Passwords don't match.",
    'err.authorization': 'Incorrect username or password.',
    'err.username_taken': 'This username is already taken.',
    'err.password_too_common': 'This password is too common.',
    'err.password_entirely_numeric': "The password can't be only digits.",
    'err.password_too_short': 'Password is too short (minimum 8 characters).',
    'err.password_too_similar': 'The password is too similar to the username.',
    'err.unknown_country': "The selected country isn't supported.",
    'err.unknown_language': "The selected language isn't supported.",
    'err.required': 'Please fill in this field.',
    'err.max_length': 'The value is too long.',
  },

  ky: {
    'tab.login': 'Кирүү',
    'tab.register': 'Катталуу',
    'label.username': 'Колдонуучу аты',
    'label.password': 'Сыр сөз',
    'label.passwordNew': 'Сыр сөз (кеминде 8 символ)',
    'label.passwordConfirm': 'Сыр сөздү кайтала',
    'label.country': 'Өлкө',
    'label.language': 'Тил',
    'btn.login': 'Кирүү',
    'btn.register': 'Аккаунт түзүү',
    'btn.logout': 'Чыгуу',
    'btn.send': 'Жөнөтүү',
    'placeholder.message': 'Билдирүү жаз...',
    'password.show': 'Сыр сөздү көрсөт',
    'password.hide': 'Сыр сөздү жашыр',
    'select.loading': 'Жүктөлүүдө...',
    'select.country': 'Өлкөнү танда',
    'hint.language': 'Аккаунттун тили — жогоруда тандалган тил.',
    'welcome': 'Салам! Мен эмоционалдык колдоо көрсөтүүчү жасалма интеллект жардамчысымын.',
    'field.username': 'Колдонуучу аты',
    'field.password': 'Сыр сөз',
    'field.country': 'Өлкө',
    'field.language': 'Тил',
    'err.generic': 'Бир нерсе туура эмес болду. Дагы аракет кыл.',
    'err.network': 'Сервер менен байланыш жок. Интернетти текшер.',
    'err.optionsLoad': 'Өлкөлөр менен тилдердин тизмеси жүктөлгөн жок. Баракчаны жаңырт.',
    'err.password_mismatch': 'Сыр сөздөр дал келбейт.',
    'err.authorization': 'Колдонуучу аты же сыр сөз туура эмес.',
    'err.username_taken': 'Бул колдонуучу аты бош эмес.',
    'err.password_too_common': 'Бул сыр сөз өтө жөнөкөй.',
    'err.password_entirely_numeric': 'Сыр сөз бир гана сандардан турбашы керек.',
    'err.password_too_short': 'Сыр сөз өтө кыска (кеминде 8 символ).',
    'err.password_too_similar': 'Сыр сөз колдонуучу атына өтө окшош.',
    'err.unknown_country': 'Тандалган өлкө колдоого алынбайт.',
    'err.unknown_language': 'Тандалган тил колдоого алынбайт.',
    'err.required': 'Бул талааны толтур.',
    'err.max_length': 'Маани өтө узун.',
  },
};

const NATIVE_NAMES = { ru: 'Русский', en: 'English', ky: 'Кыргызча' };

const FALLBACK_LANG = 'en';
const LANG_KEY = 'ui_lang';

let currentLang = FALLBACK_LANG;


function t(key) {
  const own = STRINGS[currentLang];
  if (own && key in own) return own[key];
  const fallback = STRINGS[FALLBACK_LANG];
  if (fallback && key in fallback) return fallback[key];
  return key;
}

function detectLanguage() {
  const saved = localStorage.getItem(LANG_KEY);
  if (saved) return saved;
  const browser = (navigator.language || '').slice(0, 2).toLowerCase();
  return STRINGS[browser] ? browser : FALLBACK_LANG;
}

function applyTranslations() {
  document.documentElement.lang = currentLang;

  document.querySelectorAll('[data-i18n]').forEach((el) => {
    el.textContent = t(el.dataset.i18n);
  });
  document.querySelectorAll('[data-i18n-placeholder]').forEach((el) => {
    el.placeholder = t(el.dataset.i18nPlaceholder);
  });
  document.querySelectorAll('[data-i18n-aria-label]').forEach((el) => {
    el.setAttribute('aria-label', t(el.dataset.i18nAriaLabel));
  });
}