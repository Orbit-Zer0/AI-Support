from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APITestCase

from .models import Conversation, Message
from .prompts import build_system_prompt

User = get_user_model()


class SystemPromptTests(TestCase):
    def test_contains_contacts_and_default_language(self):
        prompt = build_system_prompt('- Helpline: 111', 'Кыргызча')
        self.assertIn('- Helpline: 111', prompt)
        self.assertIn('Кыргызча', prompt)

    def test_forbids_inventing_numbers(self):
        prompt = build_system_prompt('- Helpline: 111', 'English')
        self.assertIn('Никогда не меняй', prompt)


class ChatViewTests(APITestCase):
    def setUp(self):
        self.alice = User.objects.create_user('alice', password='Str0ng-pass-111')
        self.bob = User.objects.create_user('bob', password='Str0ng-pass-222')
        self.url = reverse('chat')

    def test_requires_authentication(self):
        response = self.client.post(self.url, {'message': 'hi'}, format='json')
        self.assertEqual(response.status_code, 401)

    @patch('apps.chat.views.get_ai_response', return_value='hello')
    def test_creates_conversation_and_passes_user(self, mock_ai):
        self.client.force_authenticate(self.alice)
        response = self.client.post(self.url, {'message': 'hi'}, format='json')
        self.assertEqual(response.status_code, 200)

        conversation = Conversation.objects.get(id=response.data['conversation_id'])
        self.assertEqual(conversation.user, self.alice)
        self.assertEqual(Message.objects.filter(conversation=conversation).count(), 2)
        self.assertEqual(mock_ai.call_args.args[2], self.alice)

    @patch('apps.chat.views.get_ai_response', return_value='hello')
    def test_cannot_use_someone_elses_conversation(self, mock_ai):
        conversation = Conversation.objects.create(user=self.alice)
        self.client.force_authenticate(self.bob)
        response = self.client.post(
            self.url,
            {'message': 'hi', 'conversation_id': conversation.id},
            format='json',
        )
        self.assertEqual(response.status_code, 404)
        mock_ai.assert_not_called()