from rest_framework.decorators import api_view
from rest_framework.response import Response
from .models import Conversation, Message
from .services import get_ai_response


@api_view(['POST'])
def chat_view(request):
    user_message = request.data.get('message')
    conversation_id = request.data.get('conversation_id')

    if not user_message:
        return Response({'error': 'Поле message обязательно'}, status=400)

    if conversation_id:
        conversation = Conversation.objects.get(id=conversation_id)
    else:
        conversation = Conversation.objects.create()

    history = list(conversation.messages.values('role', 'content'))

    ai_response = get_ai_response(history, user_message)

    Message.objects.create(conversation=conversation, role='user', content=user_message)
    Message.objects.create(conversation=conversation, role='model', content=ai_response)

    return Response({'response': ai_response, 'conversation_id': conversation.id})