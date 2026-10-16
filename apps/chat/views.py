import logging

from django.shortcuts import get_object_or_404
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.crisis.layer import apply_crisis_layer, build_emergency_reply

from .models import Conversation, Message
from .services import get_ai_response

logger = logging.getLogger(__name__)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def chat_view(request):
    user_message = request.data.get('message')
    conversation_id = request.data.get('conversation_id')

    if not isinstance(user_message, str) or not user_message.strip():
        return Response({'error': 'Field "message" is required.'}, status=400)

    if conversation_id is not None:
        try:
            conversation_id = int(conversation_id)
        except (TypeError, ValueError):
            return Response({'error': 'conversation_id must be a number.'}, status=400)
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
            status = 429 if getattr(exc, 'code', None) == 429 else 503
            return Response(
                {'error': 'The AI service is temporarily unavailable, please try again later.'},
                status=status,
            )
        ai_response, crisis = emergency, True
    else:
        ai_response, crisis = apply_crisis_layer(user_message, ai_response, request.user)

    if not ai_response or not ai_response.strip():
        return Response(
            {'error': 'The AI service returned an empty response.'}, status=502
        )

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