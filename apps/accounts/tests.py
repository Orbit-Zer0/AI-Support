from django.urls import reverse
from rest_framework.test import APITestCase

from .models import Country


class PublicListsTests(APITestCase):
    def test_countries_are_public_and_only_active(self):
        Country.objects.create(code='ZZ', name='Hidden', is_active=False)
        response = self.client.get(reverse('countries'))
        self.assertEqual(response.status_code, 200)
        codes = [c['code'] for c in response.data]
        self.assertIn('KG', codes)
        self.assertNotIn('ZZ', codes)

    def test_languages_list(self):
        response = self.client.get(reverse('languages'))
        self.assertEqual(response.status_code, 200)
        codes = [l['code'] for l in response.data]
        for code in ('ru', 'en', 'ky'):
            self.assertIn(code, codes)

    def test_stale_token_does_not_break_public_endpoints(self):
        self.client.credentials(HTTP_AUTHORIZATION='Token not-a-real-token')
        self.assertEqual(self.client.get(reverse('countries')).status_code, 200)
        self.assertEqual(self.client.get(reverse('languages')).status_code, 200)