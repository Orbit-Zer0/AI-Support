import re
import unicodedata

_PATTERNS = [
    # --- русский ---
    r'\bсуицид\w*',
    r'\bсамоубийств\w*',
    r'\bпоконч\w* с собой\b',
    r'\bуби(?:ть|ю|л|ла|ли) себя\b',
    r'\bне хо(?:чу|чется|тел|тела)(?: бы)?(?: больше)? жить\b',
    r'\bжить не хо(?:чу|чется)\b',
    r'\bхоч(?:у|ется)(?: бы)? умереть\b',
    r'\bхочу сдохнуть\b',
    r'\b(?:нет|не вижу) смысла жить\b',
    r'\bсвест\w* счеты с жизнью\b',
    r'\bналож\w* на себя руки\b',
    r'\bповеси(?:ться|лся|лась)\b',
    r'\bповешусь\b',
    r'\bвскр\w* вен\w*',
    r'\bлучше бы меня не было\b',
    r'\bлучше бы я умер\w*',
    # --- английский ---
    r'\bsuicid\w*',
    r'\bkill(?:ing)? my ?self\b',
    r'\bend(?:ing)? my (?:own )?life\b',
    r'\bend it all\b',
    r'\btake my (?:own )?life\b',
    r'\bwant(?:ed)? to die\b',
    r'\bwanna die\b',
    r'\bdon ?t want to (?:live|be alive|exist)\b',
    r'\bbetter off dead\b',
    r'\bno reason to live\b',
    r'\bhang my ?self\b',
    r'\b(?:cut|slit) my wrists\b',
    r'\bself ?harm\w*',
    r'\bhurt(?:ing)? my ?self\b',
    # --- кыргызский (ЧЕРНОВИК, нужна проверка носителем) ---
    r'\bөлгүм кел\w*',
    r'\bжашагым келбе\w*',
    r'\bөзүмдү өлтүр\w*',
    r'\bөзүн өзү өлтүр\w*',
]

_CRISIS_RE = re.compile('|'.join(f'(?:{p})' for p in _PATTERNS))


def _normalize(text):
    text = unicodedata.normalize('NFKC', text).lower()
    text = text.replace('ё', 'е')
    text = re.sub(r'[^\w\s]', ' ', text)
    return re.sub(r'\s+', ' ', text).strip()


def detect_crisis(text):
    if not isinstance(text, str) or not text.strip():
        return False
    return _CRISIS_RE.search(_normalize(text)) is not None