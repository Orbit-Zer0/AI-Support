from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import override_settings
from django.urls import reverse
from rest_framework.test import APITestCase

from .throttles import ChatBurstThrottle

User = get_user_model()

REAL_CACHE = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'throttle-tests',
    }
}


@override_settings(CACHES=REAL_CACHE)
class ChatThrottleTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user('alice', password='Str0ng-pass-111')
        self.client.force_authenticate(self.user)
        self.url = reverse('chat')

    def post(self):
        return self.client.post(self.url, {'message': 'hello'}, format='json')

    @patch('apps.chat.views.get_ai_response', return_value='ok')
    def test_burst_limit_returns_429_with_code(self, _):
        with patch.dict(ChatBurstThrottle.THROTTLE_RATES, {'chat_burst': '2/min'}):
            self.assertEqual(self.post().status_code, 200)
            self.assertEqual(self.post().status_code, 200)
            third = self.post()

        self.assertEqual(third.status_code, 429)
        self.assertEqual(third.data['code'], 'throttled')
        self.assertIsNotNone(third.data['retry_after'])

    def test_unauthenticated_request_is_rejected_before_throttle(self):
        self.client.force_authenticate(None)
        self.assertEqual(self.post().status_code, 401)