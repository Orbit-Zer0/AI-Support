FALLBACK_URL = 'https://findahelpline.com'

_FALLBACK_TEXTS = {
    'en': (
        'If you are in immediate danger, call your local emergency number. '
        'You can find a helpline for your country here: {url}'
    ),
    'ru': (
        'Если тебе грозит опасность, позвони в местную службу экстренной помощи. '
        'Линию помощи в своей стране можно найти здесь: {url}'
    ),
}

_HEADERS = {
    'en': 'If you need help right now:',
    'ru': 'Если тебе нужна помощь прямо сейчас:',
}

_UNAVAILABLE = {
    'en': "I can't reply as usual right now, but you are not alone and help is available:",
    'ru': 'Прямо сейчас я не могу ответить как обычно, но ты не один, и помощь доступна:',
}


def _pick(texts, language_code):
    return texts.get(language_code) or texts['en']


def get_fallback_text(language_code):
    return _pick(_FALLBACK_TEXTS, language_code).format(url=FALLBACK_URL)


def get_header_text(language_code):
    return _pick(_HEADERS, language_code)


def get_unavailable_text(language_code):
    return _pick(_UNAVAILABLE, language_code)