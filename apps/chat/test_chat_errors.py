from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APITestCase

from .views import MAX_MESSAGE_LENGTH

User = get_user_model()


class QuotaError(Exception):
    code = 429


class ChatErrorCodesTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user('alice', password='Str0ng-pass-111')
        self.client.force_authenticate(self.user)
        self.url = reverse('chat')

    def test_empty_message_code(self):
        response = self.client.post(self.url, {'message': '   '}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['code'], 'message_required')

    @patch('apps.chat.views.get_ai_response', return_value='ok')
    def test_too_long_message_code(self, mock_ai):
        text = 'a' * (MAX_MESSAGE_LENGTH + 1)
        response = self.client.post(self.url, {'message': text}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['code'], 'message_too_long')
        mock_ai.assert_not_called()

    def test_invalid_conversation_id_code(self):
        response = self.client.post(
            self.url, {'message': 'hi', 'conversation_id': 'abc'}, format='json'
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['code'], 'invalid_conversation_id')

    @patch('apps.chat.views.get_ai_response', side_effect=RuntimeError('boom'))
    def test_unavailable_code(self, _):
        response = self.client.post(self.url, {'message': 'hello'}, format='json')
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.data['code'], 'ai_unavailable')

    @patch('apps.chat.views.get_ai_response', side_effect=QuotaError())
    def test_quota_code(self, _):
        response = self.client.post(self.url, {'message': 'hello'}, format='json')
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.data['code'], 'ai_quota')

    @patch('apps.chat.views.get_ai_response', return_value='   ')
    def test_empty_ai_response_code(self, _):
        response = self.client.post(self.url, {'message': 'hello'}, format='json')
        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.data['code'], 'ai_empty')