DEFAULT_WARMTH = 3
DEFAULT_ENTHUSIASM = 2
DEFAULT_EMOJI = 'off'

WARMTH = {
    1: 'Тон сдержанный и деловой: поддерживай коротко, без лишних ласковых слов.',
    2: 'Тон спокойный и вежливый, немного сдержанный.',
    3: 'Тон тёплый и дружелюбный.',
    4: 'Тон очень тёплый и заботливый: часто показывай, что понимаешь чувства человека.',
    5: 'Тон максимально мягкий и ласковый: много сочувствия и поддержки.',
}

ENTHUSIASM = {
    1: 'Говори ровно и спокойно, без восклицаний и восторга.',
    2: 'Говори спокойно, восклицания допустимы изредка.',
    3: 'Говори живо и ободряюще.',
    4: 'Говори энергично и воодушевляюще, подбадривай человека.',
    5: 'Говори очень бодро и вдохновляюще, но без преувеличений и давления.',
}

EMOJI = {
    'off': 'Не используй эмодзи.',
    'rare': 'Эмодзи используй редко: не больше одного-двух за ответ и только когда это уместно.',
    'often': 'Можно использовать эмодзи, чтобы ответ был живее, но без перебора.',
}


def _level(value, default):
    if isinstance(value, int) and not isinstance(value, bool) and 1 <= value <= 5:
        return value
    return default


def build_style_block(style):
    style = style if isinstance(style, dict) else {}
    warmth = _level(style.get('warmth'), DEFAULT_WARMTH)
    enthusiasm = _level(style.get('enthusiasm'), DEFAULT_ENTHUSIASM)
    emoji = style.get('emoji')
    if emoji not in EMOJI:
        emoji = DEFAULT_EMOJI

    return (
        'НАСТРОЙКИ ТОНА ОТ ПОЛЬЗОВАТЕЛЯ:\n'
        f'- {WARMTH[warmth]}\n'
        f'- {ENTHUSIASM[enthusiasm]}\n'
        f'- {EMOJI[emoji]}\n'
        'Эти настройки уточняют общий стиль общения выше и имеют над ним приоритет, '
        'но не отменяют границы и правила безопасности.'
    )