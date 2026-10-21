from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APITestCase

from apps.accounts.models import Country, Language, UserProfile

from .fallback import FALLBACK_URL
from .models import CrisisResource, CrisisResourceText

User = get_user_model()


class CrisisContactsViewTests(APITestCase):
    def setUp(self):
        country, _ = Country.objects.get_or_create(code='UZ', defaults={'name': 'Uzbekistan'})
        english, _ = Language.objects.get_or_create(code='en', defaults={'name': 'English'})
        resource = CrisisResource.objects.create(country=country, phone='911', kind='hotline')
        CrisisResourceText.objects.create(
            resource=resource, language=english, title='Test line', description='24/7'
        )
        self.user = User.objects.create_user('alice', password='Str0ng-pass-111')
        UserProfile.objects.create(user=self.user, country=country, language=english)
        self.url = reverse('crisis-contacts')

    def test_requires_authentication(self):
        self.assertEqual(self.client.get(self.url).status_code, 401)

    def test_returns_contacts_for_users_country(self):
        self.client.force_authenticate(self.user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['contacts'][0]['phone'], '911')
        self.assertEqual(response.data['contacts'][0]['title'], 'Test line')

    def test_user_without_profile_gets_fallback_text(self):
        stranger = User.objects.create_user('nobody', password='Str0ng-pass-333')
        self.client.force_authenticate(stranger)
        response = self.client.get(self.url)
        self.assertEqual(response.data['contacts'], [])
        self.assertIn(FALLBACK_URL, response.data['fallback'])