import logging

from .fallback import get_fallback_text
from .models import CrisisResource

logger = logging.getLogger(__name__)

LANGUAGE_FALLBACK_ORDER = ['en', 'ru']


def _language_chain(language_code):
    chain = []
    for code in [language_code, *LANGUAGE_FALLBACK_ORDER]:
        if code and code not in chain:
            chain.append(code)
    return chain


def get_crisis_contacts(country_code, language_code):
    if not country_code:
        return []

    chain = _language_chain(language_code)
    resources = (
        CrisisResource.objects
        .filter(country_id=country_code, is_active=True)
        .prefetch_related('texts')
        .order_by('priority')
    )

    contacts = []
    for resource in resources:
        texts = {t.language_id: t for t in resource.texts.all()}
        text = next((texts[code] for code in chain if code in texts), None)
        if text is None and texts:
            text = next(iter(texts.values()))
        contacts.append({
            'phone': resource.phone,
            'kind': resource.kind,
            'title': text.title if text else resource.get_kind_display(),
            'description': text.description if text else '',
        })
    return contacts


def build_crisis_block(country_code, language_code):
    try:
        contacts = get_crisis_contacts(country_code, language_code)
    except Exception:
        logger.exception('Failed to load crisis contacts')
        contacts = []

    if not contacts:
        return get_fallback_text(language_code)

    lines = []
    for c in contacts:
        line = f"- {c['title']}: {c['phone']}"
        if c['description']:
            line += f" ({c['description']})"
        lines.append(line)
    return '\n'.join(lines)


def build_crisis_block_for_user(user):
    profile = getattr(user, 'profile', None)
    country = profile.country_id if profile else None
    language = profile.language_id if profile else None
    return build_crisis_block(country, language)