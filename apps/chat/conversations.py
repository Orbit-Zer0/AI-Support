from django.db.models import Max, OuterRef, Subquery
from django.shortcuts import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.crisis.detection import detect_crisis

from .models import Conversation, Message

MAX_LIST = 50
TITLE_LENGTH = 60


def _make_title(text):
    text = ' '.join((text or '').split())
    if len(text) > TITLE_LENGTH:
        return text[:TITLE_LENGTH].rstrip() + '…'
    return text


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
                'title': _make_title(c.first_message),
                'updated_at': c.last_message_at.isoformat(),
            }
            for c in conversations
        ])


class ConversationDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        conversation = get_object_or_404(Conversation, pk=pk, user=request.user)

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
        return Response({'id': conversation.id, 'messages': messages})

    def delete(self, request, pk):
        conversation = get_object_or_404(Conversation, pk=pk, user=request.user)
        conversation.delete()
        return Response(status=204)