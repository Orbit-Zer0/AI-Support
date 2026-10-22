import logging
import re

from .detection import detect_crisis
from .fallback import FALLBACK_URL, get_header_text, get_unavailable_text
from .services import build_crisis_block, get_crisis_contacts

logger = logging.getLogger(__name__)


def _country_and_language(user):
    profile = getattr(user, 'profile', None)
    if profile is None:
        return None, None
    return profile.country_id, profile.language_id


def _contains_phone(text, phone):
    digits = re.sub(r'\D', '', phone)
    if not digits:
        return False
    pattern = r'(?<!\d)' + r'[\s\-()]*'.join(re.escape(d) for d in digits) + r'(?!\d)'
    return re.search(pattern, text) is not None

_EMOJI_RE = re.compile(
    '[\U0001F000-\U0001FAFF\U00002600-\U000027BF\uFE0F]'
)

def strip_emoji(text):
    cleaned = _EMOJI_RE.sub('', text)
    return re.sub(r'[ \t]{2,}', ' ', cleaned)

def apply_crisis_layer(user_message, ai_response, user):
    if not detect_crisis(user_message):
        return ai_response, False

    ai_response = ai_response or ''
    ai_response = strip_emoji(ai_response)
    country, language = _country_and_language(user)

    try:
        contacts = get_crisis_contacts(country, language)
    except Exception:
        logger.exception('Failed to load crisis contacts')
        contacts = []

    if contacts:
        if all(_contains_phone(ai_response, c['phone']) for c in contacts):
            return ai_response, True
    elif FALLBACK_URL in ai_response:
        return ai_response, True

    block = build_crisis_block(country, language)
    header = get_header_text(language)
    return f"{ai_response.rstrip()}\n\n---\n{header}\n{block}".strip(), True


def build_emergency_reply(user_message, user):
    if not detect_crisis(user_message):
        return None
    country, language = _country_and_language(user)
    return f"{get_unavailable_text(language)}\n\n{build_crisis_block(country, language)}"