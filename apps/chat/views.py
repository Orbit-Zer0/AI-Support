import logging

from django.shortcuts import get_object_or_404
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.crisis.layer import apply_crisis_layer, build_emergency_reply

from .models import Conversation, Message
from .services import get_ai_response

logger = logging.getLogger(__name__)

MAX_MESSAGE_LENGTH = 4000


def _error(code, message, status):
    return Response({'error': message, 'code': code}, status=status)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def chat_view(request):
    user_message = request.data.get('message')
    conversation_id = request.data.get('conversation_id')

    if not isinstance(user_message, str) or not user_message.strip():
        return _error('message_required', 'Field "message" is required.', 400)
    if len(user_message) > MAX_MESSAGE_LENGTH:
        return _error(
            'message_too_long',
            f'Message is too long (max {MAX_MESSAGE_LENGTH} characters).',
            400,
        )

    if conversation_id is not None:
        try:
            conversation_id = int(conversation_id)
        except (TypeError, ValueError):
            return _error('invalid_conversation_id', 'conversation_id must be a number.', 400)
        conversation = get_object_or_404(
            Conversation, id=conversation_id, user=request.user
        )
        history = list(conversation.messages.values('role', 'content'))
    else:
        conversation = None
        history = []

    crisis = False
    try:
        ai_response = get_ai_response(history, user_message, request.user)
    except Exception as exc:
        logger.exception('AI call failed')
        emergency = build_emergency_reply(user_message, request.user)
        if emergency is None:
            if getattr(exc, 'code', None) == 429:
                return _error('ai_quota', 'Too many requests, try again later.', 429)
            return _error(
                'ai_unavailable',
                'The AI service is temporarily unavailable, please try again later.',
                503,
            )
        ai_response, crisis = emergency, True
    else:
        ai_response, crisis = apply_crisis_layer(user_message, ai_response, request.user)

    if not ai_response or not ai_response.strip():
        return _error('ai_empty', 'The AI service returned an empty response.', 502)

    if conversation is None:
        conversation = Conversation.objects.create(user=request.user)

    Message.objects.create(conversation=conversation, role='user', content=user_message)
    Message.objects.create(conversation=conversation, role='model', content=ai_response)

    return Response(
        {
            'response': ai_response,
            'conversation_id': conversation.id,
            'crisis': crisis,
        }
    )