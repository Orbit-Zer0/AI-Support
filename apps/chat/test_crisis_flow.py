from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APITestCase

from apps.accounts.models import Country, Language, UserProfile
from apps.crisis.models import CrisisResource, CrisisResourceText

from .models import Message

User = get_user_model()


class CrisisFlowTests(APITestCase):
    def setUp(self):
        country, _ = Country.objects.get_or_create(code='UZ', defaults={'name': 'Uzbekistan'})
        english, _ = Language.objects.get_or_create(code='en', defaults={'name': 'English'})
        resource = CrisisResource.objects.create(country=country, phone='911', kind='hotline')
        CrisisResourceText.objects.create(resource=resource, language=english, title='Test line')

        self.user = User.objects.create_user('alice', password='Str0ng-pass-111')
        UserProfile.objects.create(user=self.user, country=country, language=english)
        self.client.force_authenticate(self.user)
        self.url = reverse('chat')

    @patch('apps.chat.views.get_ai_response', return_value='I am here for you.')
    def test_contacts_are_appended_when_model_forgets_them(self, _):
        response = self.client.post(self.url, {'message': 'I want to die'}, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['crisis'])
        self.assertIn('911', response.data['response'])
        saved = Message.objects.filter(role='model').latest('id')
        self.assertIn('911', saved.content)

    @patch('apps.chat.views.get_ai_response', return_value='Please call 911 now.')
    def test_no_duplicate_block_when_model_already_included_numbers(self, _):
        response = self.client.post(self.url, {'message': 'I want to die'}, format='json')
        self.assertTrue(response.data['crisis'])
        self.assertEqual(response.data['response'], 'Please call 911 now.')

    @patch('apps.chat.views.get_ai_response', side_effect=RuntimeError('boom'))
    def test_crisis_message_gets_contacts_even_if_model_fails(self, _):
        response = self.client.post(self.url, {'message': 'I want to die'}, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['crisis'])
        self.assertIn('911', response.data['response'])

    @patch('apps.chat.views.get_ai_response', side_effect=RuntimeError('boom'))
    def test_normal_message_still_gets_error_if_model_fails(self, _):
        response = self.client.post(self.url, {'message': 'Hello'}, format='json')
        self.assertEqual(response.status_code, 503)

    @patch('apps.chat.views.get_ai_response', return_value='Hi there!')
    def test_normal_message_is_left_untouched(self, _):
        response = self.client.post(self.url, {'message': 'Hello'}, format='json')
        self.assertFalse(response.data['crisis'])
        self.assertEqual(response.data['response'], 'Hi there!')