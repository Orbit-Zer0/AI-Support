from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APITestCase

from .models import UserSettings
from .user_settings import DEFAULTS

User = get_user_model()


class UserSettingsApiTests(APITestCase):
    def setUp(self):
        self.alice = User.objects.create_user('alice', password='Str0ng-pass-111')
        self.bob = User.objects.create_user('bob', password='Str0ng-pass-222')
        self.client.force_authenticate(self.alice)
        self.url = reverse('user-settings')

    def patch(self, payload):
        return self.client.patch(self.url, payload, format='json')

    def test_requires_authentication(self):
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get(self.url).status_code, 401)
        self.assertEqual(self.patch({}).status_code, 401)

    def test_defaults_for_new_user(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, DEFAULTS)

    def test_patch_saves_and_is_partial(self):
        self.assertEqual(self.patch({'appearance': {'theme': 'dark'}}).status_code, 200)
        response = self.patch({'appearance': {'font_size': 'large'}})
        self.assertEqual(response.data['appearance']['theme'], 'dark')
        self.assertEqual(response.data['appearance']['font_size'], 'large')
        self.assertEqual(self.client.get(self.url).data['appearance']['theme'], 'dark')

    def test_color_is_normalized_and_can_be_reset(self):
        response = self.patch({'appearance': {'user_bubble': '#AABBCC'}})
        self.assertEqual(response.data['appearance']['user_bubble'], '#aabbcc')
        response = self.patch({'appearance': {'user_bubble': None}})
        self.assertIsNone(response.data['appearance']['user_bubble'])

    def test_invalid_values_are_rejected_and_nothing_changes(self):
        bad_payloads = [
            {'appearance': {'theme': 'purple'}},
            {'appearance': {'theme': None}},
            {'appearance': {'user_bubble': 'red'}},
            {'appearance': {'user_bubble': '#12345'}},
            {'appearance': {'bot_bubble': 'url(javascript:alert(1))'}},
            {'appearance': {'bot_bubble': '#fff; background: url(x)'}},
            {'appearance': {'font_size': 12}},
            {'appearance': {'unknown': 1}},
            {'appearance': 'dark'},
            {'unknown': {}},
        ]
        for payload in bad_payloads:
            with self.subTest(payload=payload):
                self.assertEqual(self.patch(payload).status_code, 400)
        self.assertEqual(self.client.get(self.url).data, DEFAULTS)

    def test_non_object_body_is_rejected(self):
        self.assertEqual(self.patch([1, 2, 3]).status_code, 400)

    def test_users_are_isolated(self):
        self.patch({'appearance': {'theme': 'dark'}})
        self.client.force_authenticate(self.bob)
        self.assertEqual(self.client.get(self.url).data['appearance']['theme'], 'auto')

    def test_garbage_in_database_is_ignored(self):
        UserSettings.objects.create(
            user=self.alice,
            data={
                'appearance': {
                    'theme': 'evil',
                    'user_bubble': '<script>',
                    'font_size': 'large',
                },
                'junk': 1,
            },
        )
        appearance = self.client.get(self.url).data['appearance']
        self.assertEqual(appearance['theme'], 'auto')
        self.assertIsNone(appearance['user_bubble'])
        self.assertEqual(appearance['font_size'], 'large')