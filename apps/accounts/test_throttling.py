from unittest.mock import patch

from django.core.cache import cache
from django.test import override_settings
from django.urls import reverse
from rest_framework.test import APITestCase

from .throttles import AuthThrottle

REAL_CACHE = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'auth-throttle-tests',
    }
}


@override_settings(CACHES=REAL_CACHE)
class AuthThrottleTests(APITestCase):
    def setUp(self):
        cache.clear()

    def test_login_attempts_are_limited(self):
        payload = {'username': 'nobody', 'password': 'wrong'}
        with patch.dict(AuthThrottle.THROTTLE_RATES, {'auth': '2/min'}):
            first = self.client.post(reverse('login'), payload, format='json')
            second = self.client.post(reverse('login'), payload, format='json')
            third = self.client.post(reverse('login'), payload, format='json')

        self.assertEqual(first.status_code, 400)
        self.assertEqual(second.status_code, 400)
        self.assertEqual(third.status_code, 429)
        self.assertEqual(third.data['code'], 'throttled')