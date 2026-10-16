from django.shortcuts import get_object_or_404
from google.genai import errors as genai_errors
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Conversation, Message
from .services import get_ai_response

import logging

logger = logging.getLogger(__name__)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def chat_view(request):
    user_message = request.data.get('message')
    conversation_id = request.data.get('conversation_id')

    if not user_message:
        return Response({'error': 'Поле message обязательно'}, status=400)

    if conversation_id is not None:
        try:
            conversation_id = int(conversation_id)
        except (TypeError, ValueError):
            return Response({'error': 'conversation_id должен быть числом'}, status=400)
        conversation = get_object_or_404(
            Conversation, id=conversation_id, user=request.user
        )
        history = list(conversation.messages.values('role', 'content'))
    else:
        conversation = None
        history = []

    try:
        ai_response = get_ai_response(history, user_message, request.user)
    except genai_errors.APIError as e:
        status = 429 if e.code == 429 else 503
        logger.error("Gemini API error: %s %s", e.code, e)
        return Response(
            {'error': 'Сервис ИИ временно недоступен, попробуйте позже.'},
            status=status,
        )

    if conversation is None:
        conversation = Conversation.objects.create(user=request.user)

    Message.objects.create(conversation=conversation, role='user', content=user_message)
    Message.objects.create(conversation=conversation, role='model', content=ai_response)

    return Response({'response': ai_response, 'conversation_id': conversation.id})