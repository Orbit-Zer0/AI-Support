from datetime import timedelta

from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APITestCase

from .conversations import TITLE_LENGTH
from .models import Conversation, Message

User = get_user_model()


def make_conversation(user, first_text, hours_ago, reply='ok'):
    conversation = Conversation.objects.create(user=user)
    when = timezone.now() - timedelta(hours=hours_ago)
    Message.objects.create(conversation=conversation, role='user', content=first_text)
    Message.objects.create(conversation=conversation, role='model', content=reply)
    Message.objects.filter(conversation=conversation).update(created_at=when)
    return conversation


class ConversationHistoryTests(APITestCase):
    def setUp(self):
        self.alice = User.objects.create_user('alice', password='Str0ng-pass-111')
        self.bob = User.objects.create_user('bob', password='Str0ng-pass-222')
        self.client.force_authenticate(self.alice)

    def test_requires_authentication(self):
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get(reverse('conversation-list')).status_code, 401)

    def test_list_shows_only_own_conversations_newest_first(self):
        older = make_conversation(self.alice, 'older chat', hours_ago=5)
        newer = make_conversation(self.alice, 'newer chat', hours_ago=1)
        make_conversation(self.bob, 'bobs secret', hours_ago=2)

        response = self.client.get(reverse('conversation-list'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual([c['id'] for c in response.data], [newer.id, older.id])
        self.assertEqual(response.data[0]['title'], 'newer chat')

    def test_list_skips_empty_conversations(self):
        Conversation.objects.create(user=self.alice)
        self.assertEqual(self.client.get(reverse('conversation-list')).data, [])

    def test_long_title_is_shortened(self):
        make_conversation(self.alice, 'word ' * 50, hours_ago=1)
        title = self.client.get(reverse('conversation-list')).data[0]['title']
        self.assertTrue(title.endswith('…'))
        self.assertLessEqual(len(title), TITLE_LENGTH + 1)

    def test_detail_returns_messages_in_order(self):
        conversation = make_conversation(self.alice, 'hello', hours_ago=1, reply='hi')
        response = self.client.get(reverse('conversation-detail', args=[conversation.id]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [(m['role'], m['content']) for m in response.data['messages']],
            [('user', 'hello'), ('model', 'hi')],
        )

    def test_detail_marks_crisis_replies(self):
        conversation = make_conversation(self.alice, 'I want to die', hours_ago=1, reply='call 111')
        normal = make_conversation(self.alice, 'hello', hours_ago=2, reply='hi')

        crisis_data = self.client.get(reverse('conversation-detail', args=[conversation.id])).data
        normal_data = self.client.get(reverse('conversation-detail', args=[normal.id])).data
        self.assertEqual([m['crisis'] for m in crisis_data['messages']], [False, True])
        self.assertEqual([m['crisis'] for m in normal_data['messages']], [False, False])

    def test_cannot_read_or_delete_someone_elses_conversation(self):
        conversation = make_conversation(self.bob, 'private', hours_ago=1)
        detail = reverse('conversation-detail', args=[conversation.id])
        self.assertEqual(self.client.get(detail).status_code, 404)
        self.assertEqual(self.client.delete(detail).status_code, 404)
        self.assertTrue(Conversation.objects.filter(id=conversation.id).exists())

    def test_delete_removes_conversation_and_messages(self):
        conversation = make_conversation(self.alice, 'bye', hours_ago=1)
        response = self.client.delete(reverse('conversation-detail', args=[conversation.id]))
        self.assertEqual(response.status_code, 204)
        self.assertFalse(Conversation.objects.filter(id=conversation.id).exists())
        self.assertFalse(Message.objects.filter(conversation_id=conversation.id).exists())