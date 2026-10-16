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


def get_fallback_text(language_code):
    template = _FALLBACK_TEXTS.get(language_code) or _FALLBACK_TEXTS['en']
    return template.format(url=FALLBACK_URL)    