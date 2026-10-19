from django.urls import reverse
from rest_framework.test import APITestCase


class ErrorCodesTests(APITestCase):
    def register(self, **overrides):
        data = {
            'username': 'newuser',
            'password': 'Str0ng-pass-789',
            'country': 'KG',
            'language': 'en',
        }
        data.update(overrides)
        return self.client.post(reverse('register'), data, format='json')

    def test_username_taken_code(self):
        self.assertEqual(self.register().status_code, 201)
        response = self.register()
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['codes']['username'], ['username_taken'])

    def test_numeric_password_code(self):
        response = self.register(password='12345678')
        self.assertEqual(response.status_code, 400)
        self.assertIn('password_entirely_numeric', response.data['codes']['password'])

    def test_unknown_language_code(self):
        response = self.register(language='de')
        self.assertEqual(response.data['codes']['language'], ['unknown_language'])

    def test_unknown_country_code(self):
        response = self.register(country='XX')
        self.assertEqual(response.data['codes']['country'], ['unknown_country'])

    def test_login_failure_code(self):
        response = self.client.post(
            reverse('login'), {'username': 'nobody', 'password': 'x'}, format='json'
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['codes']['non_field_errors'], ['authorization'])