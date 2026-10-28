import hashlib
from datetime import timezone as dt_timezone

from django.db import transaction
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from apps.chat.models import Conversation, Message
from apps.crisis.detection import detect_crisis
from apps.crisis.services import build_crisis_block_for_user

from .models import UserSettings
from .user_settings import effective_settings
from .views import account_data

EXPORT_FORMAT = 'ai-support-export'
EXPORT_VERSION = 1

MAX_IMPORT_BYTES = 5 * 1024 * 1024
MAX_IMPORT_CONVERSATIONS = 200
MAX_IMPORT_MESSAGES = 20000
MAX_MESSAGES_PER_CONVERSATION = 2000
MAX_MESSAGE_CHARS = 20000
MAX_TITLE_CHARS = 80


class ImportDataError(Exception):

    def __init__(self, code):
        super().__init__(code)
        self.code = code


def build_export(user):
    profile = getattr(user, 'profile', None)
    record = UserSettings.objects.filter(user=user).first()
    account = {key: value for key, value in account_data(user).items() if key != 'avatar_url'}

    conversations = []
    queryset = Conversation.objects.filter(user=user).order_by('id').prefetch_related('messages')
    for conversation in queryset:
        messages = sorted(conversation.messages.all(), key=lambda message: message.id)
        conversations.append({
            'id': conversation.id,
            'title': conversation.title,
            'created_at': conversation.created_at.isoformat(),
            'summary': conversation.summary,
            'messages': [
                {
                    'role': message.role,
                    'content': message.content,
                    'created_at': message.created_at.isoformat(),
                }
                for message in messages
            ],
        })

    return {
        'format': EXPORT_FORMAT,
        'version': EXPORT_VERSION,
        'exported_at': timezone.now().isoformat(),
        'account': {
            **account,
            'created_at': profile.created_at.isoformat() if profile else None,
        },
        'settings': effective_settings(record.data if record else {}),
        'conversations': conversations,
    }


READABLE_LABELS = {
    'ru': {
        'title': 'Мои диалоги в AI Support',
        'exported': 'Выгружено',
        'account': 'Аккаунт',
        'you': 'Ты',
        'ai': 'ИИ',
        'empty': 'Диалогов пока нет.',
        'untitled': 'Без названия',
        'neutral': 'Поддержка',
        'started': 'Начат',
        'note': 'Это копия твоих диалогов для чтения. Чтобы вернуть их в приложение, используй файл JSON («для восстановления»).',
        'help': 'Если тебе тяжело, помощь рядом:',
    },
    'en': {
        'title': 'My conversations in AI Support',
        'exported': 'Exported',
        'account': 'Account',
        'you': 'You',
        'ai': 'AI',
        'empty': 'No conversations yet.',
        'untitled': 'Untitled',
        'neutral': 'Support',
        'started': 'Started',
        'note': 'This is a copy of your conversations for reading. To restore them in the app, use the JSON file ("for restoring").',
        'help': 'If things feel hard, help is available:',
    },
    'ky': {
        'title': 'AI Support ичиндеги диалогдорум',
        'exported': 'Жүктөлгөн',
        'account': 'Аккаунт',
        'you': 'Сен',
        'ai': 'ЖИ',
        'empty': 'Диалогдор азырынча жок.',
        'untitled': 'Аталышы жок',
        'neutral': 'Колдоо',
        'started': 'Башталган',
        'note': 'Бул окуу үчүн диалогдоруңдун көчүрмөсү. Аларды колдонмого кайтаруу үчүн JSON файлын («калыбына келтирүү үчүн») колдон.',
        'help': 'Эгер оор болуп жатса, жардам жакын:',
    },
}


def _format_time(value):
    return value.astimezone(dt_timezone.utc).strftime('%Y-%m-%d %H:%M UTC')


def _readable_title(conversation, first_user_text, labels):
    if conversation.title:
        return conversation.title
    if first_user_text and detect_crisis(first_user_text):
        return labels['neutral']
    text = ' '.join((first_user_text or '').split())
    if not text:
        return labels['untitled']
    return text[:60] + ('…' if len(text) > 60 else '')


def render_readable_export(user):
    profile = getattr(user, 'profile', None)
    language = profile.language_id if profile and profile.language_id in READABLE_LABELS else 'en'
    labels = READABLE_LABELS[language]

    conversations = []
    queryset = (
        Conversation.objects.filter(user=user)
        .order_by('created_at', 'id')
        .prefetch_related('messages')
    )
    for conversation in queryset:
        messages = sorted(conversation.messages.all(), key=lambda message: message.id)
        if not messages:
            continue
        first_user = next((m.content for m in messages if m.role == 'user'), '')
        conversations.append({
            'title': _readable_title(conversation, first_user, labels),
            'started': _format_time(messages[0].created_at),
            'messages': [
                {
                    'css': message.role,
                    'who': labels['you'] if message.role == 'user' else labels['ai'],
                    'iso': message.created_at.isoformat(),
                    'time': _format_time(message.created_at),
                    'content': message.content,
                }
                for message in messages
            ],
        })

    return render_to_string('accounts/export_readable.html', {
        'lang': language,
        'labels': labels,
        'username': user.username,
        'exported_at': _format_time(timezone.now()),
        'conversations': conversations,
        'help_text': build_crisis_block_for_user(user),
    })


def _parse_time(value, now):
    if not isinstance(value, str):
        return None
    try:
        parsed = parse_datetime(value)
    except (ValueError, OverflowError):
        return None
    if parsed is None:
        return None
    if timezone.is_naive(parsed):
        parsed = timezone.make_aware(parsed, dt_timezone.utc)
    return min(parsed, now)


def _clean_title(value):
    if not isinstance(value, str):
        return ''
    title = ' '.join(value.replace('\x00', '').split())[:MAX_TITLE_CHARS].strip()
    if title and detect_crisis(title):
        return ''
    return title


def _clean_conversation(raw, now):
    if not isinstance(raw, dict):
        return None
    messages = raw.get('messages')
    if (
        not isinstance(messages, list)
        or not messages
        or len(messages) > MAX_MESSAGES_PER_CONVERSATION
        or len(messages) % 2 != 0
    ):
        return None

    cleaned = []
    for index, item in enumerate(messages):
        if not isinstance(item, dict):
            return None
        expected_role = 'user' if index % 2 == 0 else 'model'
        content = item.get('content')
        if item.get('role') != expected_role or not isinstance(content, str):
            return None
        content = content.replace('\x00', '')
        if not content.strip() or len(content) > MAX_MESSAGE_CHARS:
            return None
        cleaned.append({
            'role': expected_role,
            'content': content,
            'created_at': _parse_time(item.get('created_at'), now),
        })

    return {'title': _clean_title(raw.get('title')), 'messages': cleaned}


def _update_digest(digest, role, content):
    digest.update(role.encode())
    digest.update(b'\x00')
    digest.update(content.encode('utf-8'))
    digest.update(b'\x01')


def _fingerprint(messages):
    digest = hashlib.sha256()
    for item in messages:
        _update_digest(digest, item['role'], item['content'])
    return digest.hexdigest()


def _existing_fingerprints(user):
    digests = {}
    rows = (
        Message.objects.filter(conversation__user=user)
        .order_by('conversation_id', 'id')
        .values_list('conversation_id', 'role', 'content')
    )
    for conversation_id, role, content in rows.iterator():
        _update_digest(digests.setdefault(conversation_id, hashlib.sha256()), role, content)
    return {digest.hexdigest() for digest in digests.values()}


def _create_conversation(user, cleaned, now):
    times = [item['created_at'] or now for item in cleaned['messages']]
    conversation = Conversation.objects.create(
        user=user, title=cleaned['title'], created_at=times[0]
    )
    Message.objects.bulk_create([
        Message(
            conversation=conversation,
            role=item['role'],
            content=item['content'],
            created_at=when,
        )
        for item, when in zip(cleaned['messages'], times)
    ])


def import_conversations(user, payload):
    if not isinstance(payload, dict):
        raise ImportDataError('import_invalid')

    file_format = payload.get('format')
    if file_format is not None and file_format != EXPORT_FORMAT:
        raise ImportDataError('import_unsupported')
    version = payload.get('version')
    if version is not None and (
        not isinstance(version, int) or isinstance(version, bool) or version > EXPORT_VERSION
    ):
        raise ImportDataError('import_unsupported')

    conversations = payload.get('conversations')
    if not isinstance(conversations, list):
        raise ImportDataError('import_invalid')
    if len(conversations) > MAX_IMPORT_CONVERSATIONS:
        raise ImportDataError('import_too_many')

    total_messages = sum(
        len(raw['messages'])
        for raw in conversations
        if isinstance(raw, dict) and isinstance(raw.get('messages'), list)
    )
    if total_messages > MAX_IMPORT_MESSAGES:
        raise ImportDataError('import_too_large')

    now = timezone.now()
    existing = _existing_fingerprints(user)
    imported = invalid = duplicates = 0

    with transaction.atomic():
        for raw in conversations:
            cleaned = _clean_conversation(raw, now)
            if cleaned is None:
                invalid += 1
                continue
            fingerprint = _fingerprint(cleaned['messages'])
            if fingerprint in existing:
                duplicates += 1
                continue
            existing.add(fingerprint)
            _create_conversation(user, cleaned, now)
            imported += 1

    return {'imported': imported, 'skipped': {'invalid': invalid, 'duplicates': duplicates}}