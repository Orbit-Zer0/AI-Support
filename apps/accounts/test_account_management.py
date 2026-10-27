import json
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import mail
from django.urls import reverse
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from apps.chat.models import Conversation, Message

from .models import Country, Language, UserProfile
from .tokens import reset_token_generator

User = get_user_model()
PASSWORD = 'Str0ng-pass-111'


def make_user(username='alice', email='alice@example.com', verified=True, language='en'):
    country, _ = Country.objects.get_or_create(code='KG', defaults={'name': 'Kyrgyzstan'})
    lang, _ = Language.objects.get_or_create(code=language, defaults={'name': language})
    user = User.objects.create_user(username, password=PASSWORD)
    UserProfile.objects.create(
        user=user, country=country, language=lang, email=email, email_verified=verified
    )
    return user


def make_conversation(user, question, answer):
    conversation = Conversation.objects.create(user=user)
    Message.objects.create(conversation=conversation, role='user', content=question)
    Message.objects.create(conversation=conversation, role='model', content=answer)
    return conversation


class TokenAuthTestCase(APITestCase):
    def sign_in(self, user):
        token = Token.objects.create(user=user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')
        return token


class AccountUpdateTests(APITestCase):
    def setUp(self):
        self.user = make_user()
        self.client.force_authenticate(self.user)
        self.url = reverse('account')

    def test_requires_authentication(self):
        self.client.force_authenticate(None)
        self.assertEqual(self.client.patch(self.url, {}, format='json').status_code, 401)

    def test_country_and_language_can_be_changed(self):
        Country.objects.get_or_create(code='KZ', defaults={'name': 'Kazakhstan'})
        Language.objects.get_or_create(code='ru', defaults={'name': 'Русский'})
        response = self.client.patch(self.url, {'country': 'kz', 'language': 'RU'}, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual((response.data['country'], response.data['language']), ('KZ', 'ru'))
        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.profile.country_id, 'KZ')

    def test_unknown_or_inactive_values_are_rejected(self):
        Country.objects.create(code='ZZ', name='Hidden', is_active=False)
        for payload, field, code in [
            ({'country': 'XX'}, 'country', 'unknown_country'),
            ({'country': 'ZZ'}, 'country', 'unknown_country'),
            ({'language': 'de'}, 'language', 'unknown_language'),
        ]:
            with self.subTest(payload=payload):
                response = self.client.patch(self.url, payload, format='json')
                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.data['codes'][field], [code])


class ChangePasswordTests(TokenAuthTestCase):
    def setUp(self):
        self.user = make_user()
        self.old_token = self.sign_in(self.user)
        self.url = reverse('account-password')

    def change(self, **overrides):
        data = {'current_password': PASSWORD, 'new_password': 'N3w-Strong-pass-5'}
        data.update(overrides)
        return self.client.post(self.url, data, format='json')

    def test_wrong_current_password_is_rejected(self):
        response = self.change(current_password='wrong-password-1')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['codes']['current_password'], ['wrong_password'])
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(PASSWORD))

    def test_weak_and_same_passwords_are_rejected(self):
        weak = self.change(new_password='12345678')
        self.assertIn('password_entirely_numeric', weak.data['codes']['new_password'])
        same = self.change(new_password=PASSWORD)
        self.assertEqual(same.data['codes']['new_password'], ['same_password'])

    def test_success_changes_password_and_replaces_token(self):
        response = self.change()
        self.assertEqual(response.status_code, 200)
        new_key = response.data['token']
        self.assertNotEqual(new_key, self.old_token.key)

        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('N3w-Strong-pass-5'))
        self.assertFalse(Token.objects.filter(key=self.old_token.key).exists())

        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.old_token.key}')
        self.assertEqual(self.client.get(reverse('account')).status_code, 401)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {new_key}')
        self.assertEqual(self.client.get(reverse('account')).status_code, 200)

    def test_requires_authentication(self):
        self.client.credentials()
        self.assertEqual(self.change().status_code, 401)


class ChangeEmailTests(APITestCase):
    def setUp(self):
        self.user = make_user()
        self.client.force_authenticate(self.user)
        self.url = reverse('account-email')

    def change(self, **overrides):
        data = {'email': 'New@Example.com', 'current_password': PASSWORD}
        data.update(overrides)
        return self.client.post(self.url, data, format='json')

    def test_wrong_password_is_rejected(self):
        response = self.change(current_password='wrong-password-1')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['codes']['current_password'], ['wrong_password'])
        self.assertEqual(len(mail.outbox), 0)

    def test_success_makes_email_unverified_and_sends_link_to_new_address(self):
        response = self.change()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['email'], 'new@example.com')
        self.assertFalse(response.data['email_verified'])
        self.assertTrue(response.data['email_sent'])

        profile = UserProfile.objects.get(user=self.user)
        self.assertEqual(profile.email, 'new@example.com')
        self.assertFalse(profile.email_verified)
        self.assertEqual(mail.outbox[0].to, ['new@example.com'])

    def test_address_verified_by_someone_else_is_refused(self):
        make_user('bob', email='bob@example.com', verified=True)
        response = self.change(email='bob@example.com')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['codes']['email'], ['email_taken'])

    def test_current_verified_address_is_refused(self):
        response = self.change(email='alice@example.com')
        self.assertEqual(response.data['codes']['email'], ['same_email'])

    def test_old_reset_links_stop_working(self):
        old_link_token = reset_token_generator.make_token(self.user)
        self.change()
        fresh_user = User.objects.get(pk=self.user.pk)
        self.assertFalse(reset_token_generator.check_token(fresh_user, old_link_token))

    @patch('apps.accounts.account_views.send_verification_email', side_effect=RuntimeError('smtp down'))
    def test_email_is_saved_even_if_sending_fails(self, _):
        response = self.change()
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data['email_sent'])
        self.assertEqual(UserProfile.objects.get(user=self.user).email, 'new@example.com')


class ExportTests(APITestCase):
    def test_export_contains_only_own_data_and_no_password_hash(self):
        alice = make_user('alice')
        bob = make_user('bob', email='bob@example.com')
        make_conversation(alice, 'my question', 'my answer')
        make_conversation(bob, 'secret of bob', 'bobs answer')

        self.client.force_authenticate(alice)
        response = self.client.get(reverse('account-export'))
        self.assertEqual(response.status_code, 200)
        self.assertIn('attachment', response['Content-Disposition'])

        dumped = json.dumps(response.data)
        self.assertEqual(len(response.data['conversations']), 1)
        self.assertIn('my question', dumped)
        self.assertNotIn('secret of bob', dumped)
        self.assertNotIn(alice.password, dumped)
        self.assertEqual(response.data['account']['username'], 'alice')

    def test_requires_authentication(self):
        self.assertEqual(self.client.get(reverse('account-export')).status_code, 401)


class LogoutAllTests(TokenAuthTestCase):
    def test_token_is_deleted_and_stops_working(self):
        user = make_user()
        token = self.sign_in(user)
        response = self.client.post(reverse('account-logout-all'))
        self.assertEqual(response.status_code, 204)
        self.assertFalse(Token.objects.filter(key=token.key).exists())
        self.assertEqual(self.client.get(reverse('account')).status_code, 401)


class DeleteAccountTests(APITestCase):
    def setUp(self):
        self.user = make_user('alice')
        self.other = make_user('bob', email='bob@example.com')
        make_conversation(self.user, 'q', 'a')
        make_conversation(self.other, 'bobs q', 'bobs a')
        self.client.force_authenticate(self.user)
        self.url = reverse('account-delete')

    def test_wrong_password_deletes_nothing(self):
        response = self.client.post(self.url, {'password': 'wrong-password-1'}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['codes']['password'], ['wrong_password'])
        self.assertTrue(User.objects.filter(pk=self.user.pk).exists())

    def test_success_removes_account_and_all_its_data_only(self):
        response = self.client.post(self.url, {'password': PASSWORD}, format='json')
        self.assertEqual(response.status_code, 204)

        self.assertFalse(User.objects.filter(username='alice').exists())
        self.assertFalse(UserProfile.objects.filter(email='alice@example.com').exists())
        self.assertFalse(Conversation.objects.filter(messages__content='q').exists())
        self.assertFalse(Message.objects.filter(content='q').exists())

        self.assertTrue(User.objects.filter(username='bob').exists())
        self.assertTrue(Message.objects.filter(content='bobs q').exists())

    def test_staff_accounts_cannot_be_deleted_here(self):
        self.user.is_staff = True
        self.user.save()
        response = self.client.post(self.url, {'password': PASSWORD}, format='json')
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.data['code'], 'staff_account')
        self.assertTrue(User.objects.filter(pk=self.user.pk).exists())

    def test_requires_authentication(self):
        self.client.force_authenticate(None)
        self.assertEqual(self.client.post(self.url, {'password': PASSWORD}, format='json').status_code, 401)