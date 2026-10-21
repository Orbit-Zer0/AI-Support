import logging

from django.db.models import Max, OuterRef, Subquery
from django.shortcuts import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.crisis.detection import detect_crisis

from .models import Conversation, Message
from .services import generate_title
from .throttles import TitleThrottle

logger = logging.getLogger(__name__)

MAX_LIST = 50
TITLE_LENGTH = 60
MAX_TITLE_LENGTH = 80

NEUTRAL_TITLES = {'ru': 'Поддержка', 'en': 'Support', 'ky': 'Колдоо'}


def _make_title(text):
    text = ' '.join((text or '').split())
    if len(text) > TITLE_LENGTH:
        return text[:TITLE_LENGTH].rstrip() + '…'
    return text


def _neutral_title(user):
    profile = getattr(user, 'profile', None)
    code = getattr(profile, 'language_id', None)
    return NEUTRAL_TITLES.get(code) or NEUTRAL_TITLES['en']


def _display_title(conversation, first_message, user):
    if conversation.title:
        return conversation.title
    if detect_crisis(first_message or ''):
        return _neutral_title(user)
    return _make_title(first_message)


def _error(code, message, status):
    return Response({'error': message, 'code': code}, status=status)


class ConversationListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        first_message = (
            Message.objects
            .filter(conversation=OuterRef('pk'), role='user')
            .order_by('id')
            .values('content')[:1]
        )
        conversations = (
            Conversation.objects
            .filter(user=request.user)
            .annotate(
                last_message_at=Max('messages__created_at'),
                first_message=Subquery(first_message),
            )
            .filter(last_message_at__isnull=False)
            .order_by('-last_message_at')[:MAX_LIST]
        )
        return Response([
            {
                'id': c.id,
                'title': _display_title(c, c.first_message, request.user),
                'updated_at': c.last_message_at.isoformat(),
            }
            for c in conversations
        ])


class ConversationDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        conversation = get_object_or_404(Conversation, pk=pk, user=request.user)

        first_user = (
            conversation.messages.filter(role='user')
            .order_by('id').values_list('content', flat=True).first()
        )

        messages = []
        previous_user_was_crisis = False
        for m in conversation.messages.order_by('id').values('id', 'role', 'content'):
            if m['role'] == 'user':
                previous_user_was_crisis = detect_crisis(m['content'])
                crisis = False
            else:
                crisis = previous_user_was_crisis
            messages.append({
                'id': m['id'],
                'role': m['role'],
                'content': m['content'],
                'crisis': crisis,
            })
        return Response({
            'id': conversation.id,
            'title': _display_title(conversation, first_user, request.user),
            'messages': messages,
        })

    def patch(self, request, pk):
        conversation = get_object_or_404(Conversation, pk=pk, user=request.user)
        title = request.data.get('title')
        title = ' '.join(title.split()) if isinstance(title, str) else ''
        if not title:
            return _error('title_required', 'Title is required.', 400)
        if len(title) > MAX_TITLE_LENGTH:
            return _error('title_too_long', 'Title is too long.', 400)
        conversation.title = title
        conversation.save(update_fields=['title'])
        return Response({'id': conversation.id, 'title': title})

    def delete(self, request, pk):
        conversation = get_object_or_404(Conversation, pk=pk, user=request.user)
        conversation.delete()
        return Response(status=204)


class ConversationTitleView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [TitleThrottle]

    def post(self, request, pk):
        conversation = get_object_or_404(Conversation, pk=pk, user=request.user)
        if conversation.title:
            return Response({'id': conversation.id, 'title': conversation.title})

        first_user = conversation.messages.filter(role='user').order_by('id').first()
        first_reply = conversation.messages.filter(role='model').order_by('id').first()
        if first_user is None or first_reply is None:
            return Response({'id': conversation.id, 'title': ''})

        if detect_crisis(first_user.content):
            title = _neutral_title(request.user)
        else:
            try:
                title = generate_title(first_user.content, first_reply.content)
            except Exception:
                logger.exception('Title generation failed')
                title = ''

        if title:
            Conversation.objects.filter(id=conversation.id, title='').update(title=title)
            conversation.refresh_from_db(fields=['title'])

        return Response({
            'id': conversation.id,
            'title': conversation.title or _make_title(first_user.content),
        })