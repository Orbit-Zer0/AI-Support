import re
import time
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.cache import cache
from django.test import override_settings
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from .models import Country, Language, UserProfile
from .tokens import make_verification_token, reset_token_generator

User = get_user_model()

REAL_CACHE = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'email-account-tests',
    }
}


def make_user(username='alice', email='alice@example.com', verified=True,
              password='Str0ng-pass-111', language='en'):
    country, _ = Country.objects.get_or_create(code='KG', defaults={'name': 'Kyrgyzstan'})
    lang, _ = Language.objects.get_or_create(code=language, defaults={'name': language})
    user = User.objects.create_user(username, password=password)
    UserProfile.objects.create(
        user=user, country=country, language=lang, email=email, email_verified=verified
    )
    return user


def first_link(message):
    return re.search(r'https?://\S+', message.body).group(0)


class RegistrationEmailTests(APITestCase):
    def register(self, **overrides):
        data = {
            'username': 'newuser',
            'email': 'newuser@example.com',
            'password': 'Str0ng-pass-789',
            'country': 'KG',
            'language': 'en',
        }
        data.update(overrides)
        return self.client.post(reverse('register'), data, format='json')

    def test_registration_stores_unverified_email_and_sends_link(self):
        response = self.register()
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['email'], 'newuser@example.com')
        self.assertFalse(response.data['email_verified'])

        profile = UserProfile.objects.get(user__username='newuser')
        self.assertFalse(profile.email_verified)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['newuser@example.com'])
        self.assertIn('/?verify=', first_link(mail.outbox[0]))

    def test_email_is_stored_in_lowercase(self):
        self.register(email='NewUser@Example.COM')
        self.assertEqual(UserProfile.objects.get(user__username='newuser').email, 'newuser@example.com')

    def test_at_sign_is_not_allowed_in_username(self):
        response = self.register(username='bad@name')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['codes']['username'], ['username_no_at'])

    def test_invalid_email_is_rejected(self):
        response = self.register(email='not-an-email')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['codes']['email'], ['invalid'])

    def test_email_is_required(self):
        response = self.client.post(
            reverse('register'),
            {'username': 'x1', 'password': 'Str0ng-pass-789', 'country': 'KG', 'language': 'en'},
            format='json',
        )
        self.assertEqual(response.data['codes']['email'], ['required'])

    def test_verified_email_cannot_be_reused(self):
        make_user(email='taken@example.com', verified=True)
        response = self.register(email='TAKEN@example.com')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['codes']['email'], ['email_taken'])

    def test_unverified_email_can_be_used_by_several_accounts(self):
        self.assertEqual(self.register(username='one', email='same@example.com').status_code, 201)
        self.assertEqual(self.register(username='two', email='same@example.com').status_code, 201)

    @patch('apps.accounts.views.send_verification_email', side_effect=RuntimeError('smtp down'))
    def test_registration_succeeds_even_if_email_cannot_be_sent(self, _):
        self.assertEqual(self.register().status_code, 201)
        self.assertTrue(User.objects.filter(username='newuser').exists())


class LoginTests(APITestCase):
    def login(self, login, password='Str0ng-pass-111'):
        return self.client.post(
            reverse('login'), {'login': login, 'password': password}, format='json'
        )

    def test_login_by_username_is_case_insensitive(self):
        make_user('Alice')
        response = self.login('alice')
        self.assertEqual(response.status_code, 200)
        self.assertIn('token', response.data)
        self.assertEqual(response.data['email'], 'alice@example.com')

    def test_login_by_verified_email(self):
        make_user()
        response = self.login('ALICE@example.com')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['username'], 'alice')

    def test_unverified_email_cannot_be_used_to_log_in(self):
        make_user(verified=False)
        response = self.login('alice@example.com')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['codes']['non_field_errors'], ['authorization'])

    def test_username_still_works_with_unverified_email(self):
        make_user(verified=False)
        self.assertEqual(self.login('alice').status_code, 200)

    def test_wrong_password_and_unknown_login_give_same_error(self):
        make_user()
        wrong = self.login('alice', 'wrong-password-1')
        unknown = self.login('nobody')
        self.assertEqual(wrong.data['codes'], unknown.data['codes'])
        self.assertEqual(wrong.status_code, 400)

    def test_inactive_user_cannot_log_in(self):
        user = make_user()
        user.is_active = False
        user.save()
        self.assertEqual(self.login('alice').status_code, 400)


class VerifyEmailTests(APITestCase):
    def verify(self, token):
        return self.client.post(reverse('email-verify'), {'token': token}, format='json')

    def test_valid_token_verifies_email(self):
        user = make_user(verified=False)
        response = self.verify(make_verification_token(user, 'alice@example.com'))
        self.assertEqual(response.status_code, 200)
        user.profile.refresh_from_db()
        self.assertTrue(user.profile.email_verified)

    def test_verifying_twice_is_fine(self):
        user = make_user(verified=False)
        token = make_verification_token(user, 'alice@example.com')
        self.verify(token)
        self.assertEqual(self.verify(token).status_code, 200)

    def test_garbage_token_is_rejected(self):
        for token in ('garbage', '', None, 123):
            with self.subTest(token=token):
                response = self.verify(token)
                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.data['codes']['token'], ['invalid_token'])

    def test_token_for_old_address_is_rejected(self):
        user = make_user(verified=False)
        response = self.verify(make_verification_token(user, 'old-address@example.com'))
        self.assertEqual(response.status_code, 400)
        user.profile.refresh_from_db()
        self.assertFalse(user.profile.email_verified)

    def test_expired_token_is_rejected(self):
        user = make_user(verified=False)
        token = make_verification_token(user, 'alice@example.com')
        with patch('django.core.signing.time.time', return_value=time.time() + 2 * 24 * 3600):
            response = self.verify(token)
        self.assertEqual(response.status_code, 400)

    def test_first_to_verify_owns_the_address(self):
        first = make_user('first', email='shared@example.com', verified=False)
        second = make_user('second', email='shared@example.com', verified=False)
        self.verify(make_verification_token(first, 'shared@example.com'))

        second.profile.refresh_from_db()
        self.assertEqual(second.profile.email, '')
        self.assertFalse(second.profile.email_verified)

    def test_address_verified_by_someone_else_is_refused(self):
        make_user('owner', email='shared@example.com', verified=True)
        latecomer = make_user('late', email='shared@example.com', verified=False)
        response = self.verify(make_verification_token(latecomer, 'shared@example.com'))
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['codes']['email'], ['email_taken'])


@override_settings(CACHES=REAL_CACHE)
class ForgotPasswordTests(APITestCase):
    def setUp(self):
        cache.clear()

    def forgot(self, email):
        return self.client.post(reverse('password-forgot'), {'email': email}, format='json')

    def test_verified_email_receives_reset_link(self):
        make_user()
        response = self.forgot('ALICE@example.com')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('/?reset=', first_link(mail.outbox[0]))

    def test_unknown_and_unverified_addresses_get_the_same_answer_without_mail(self):
        make_user(verified=False)
        known_but_unverified = self.forgot('alice@example.com')
        unknown = self.forgot('nobody@example.com')
        self.assertEqual(known_but_unverified.status_code, 200)
        self.assertEqual(known_but_unverified.data, unknown.data)
        self.assertEqual(len(mail.outbox), 0)

    def test_second_request_within_a_minute_sends_no_second_mail(self):
        make_user()
        self.forgot('alice@example.com')
        self.forgot('alice@example.com')
        self.assertEqual(len(mail.outbox), 1)

    def test_invalid_email_format_is_rejected(self):
        self.assertEqual(self.forgot('not-an-email').status_code, 400)

    @patch('apps.accounts.views.send_reset_email', side_effect=RuntimeError('smtp down'))
    def test_mail_failure_does_not_leak_through_the_answer(self, _):
        make_user()
        self.assertEqual(self.forgot('alice@example.com').status_code, 200)


class ResetPasswordTests(APITestCase):
    def credentials(self, user):
        return {
            'uid': urlsafe_base64_encode(force_bytes(user.pk)),
            'token': reset_token_generator.make_token(user),
        }

    def reset(self, payload):
        return self.client.post(reverse('password-reset'), payload, format='json')

    def test_valid_link_changes_password_and_logs_out_everywhere(self):
        user = make_user()
        Token.objects.create(user=user)
        payload = {**self.credentials(user), 'password': 'N3w-Strong-pass-5'}

        response = self.reset(payload)
        self.assertEqual(response.status_code, 200)
        user.refresh_from_db()
        self.assertTrue(user.check_password('N3w-Strong-pass-5'))
        self.assertFalse(Token.objects.filter(user=user).exists())

    def test_link_works_only_once(self):
        user = make_user()
        payload = {**self.credentials(user), 'password': 'N3w-Strong-pass-5'}
        self.assertEqual(self.reset(payload).status_code, 200)
        again = self.reset({**payload, 'password': 'An0ther-Strong-pass-6'})
        self.assertEqual(again.status_code, 400)
        self.assertEqual(again.data['codes']['token'], ['invalid_token'])

    def test_garbage_credentials_are_rejected(self):
        user = make_user()
        good = self.credentials(user)
        bad_payloads = [
            {'uid': good['uid'], 'token': 'wrong-token', 'password': 'N3w-Strong-pass-5'},
            {'uid': 'not-base64!!', 'token': good['token'], 'password': 'N3w-Strong-pass-5'},
            {'uid': urlsafe_base64_encode(b'99999'), 'token': good['token'], 'password': 'N3w-Strong-pass-5'},
        ]
        for payload in bad_payloads:
            with self.subTest(payload=payload):
                response = self.reset(payload)
                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.data['codes']['token'], ['invalid_token'])

    def test_weak_password_is_rejected_and_link_stays_valid(self):
        user = make_user()
        credentials = self.credentials(user)
        weak = self.reset({**credentials, 'password': '12345678'})
        self.assertEqual(weak.status_code, 400)
        self.assertIn('password_entirely_numeric', weak.data['codes']['password'])
        self.assertEqual(self.reset({**credentials, 'password': 'N3w-Strong-pass-5'}).status_code, 200)

    def test_changing_email_invalidates_old_reset_links(self):
        user = make_user()
        credentials = self.credentials(user)
        user.profile.email = 'changed@example.com'
        user.profile.save()
        response = self.reset({**credentials, 'password': 'N3w-Strong-pass-5'})
        self.assertEqual(response.status_code, 400)


class ResendAndAccountTests(APITestCase):
    def test_resend_requires_authentication(self):
        self.assertEqual(self.client.post(reverse('email-resend')).status_code, 401)

    def test_resend_sends_link_for_unverified_email(self):
        user = make_user(verified=False)
        self.client.force_authenticate(user)
        response = self.client.post(reverse('email-resend'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('/?verify=', first_link(mail.outbox[0]))

    def test_resend_for_verified_email_sends_nothing(self):
        self.client.force_authenticate(make_user(verified=True))
        response = self.client.post(reverse('email-resend'))
        self.assertTrue(response.data['email_verified'])
        self.assertEqual(len(mail.outbox), 0)

    def test_resend_without_email_is_an_error(self):
        user = User.objects.create_user('plain', password='Str0ng-pass-111')
        UserProfile.objects.create(user=user)
        self.client.force_authenticate(user)
        response = self.client.post(reverse('email-resend'))
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['code'], 'no_email')

    @patch('apps.accounts.views.send_verification_email', side_effect=RuntimeError('smtp down'))
    def test_resend_reports_failure(self, _):
        self.client.force_authenticate(make_user(verified=False))
        response = self.client.post(reverse('email-resend'))
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.data['code'], 'email_failed')

    def test_account_endpoint(self):
        self.client.force_authenticate(make_user(verified=False))
        response = self.client.get(reverse('account'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['username'], 'alice')
        self.assertEqual(response.data['email'], 'alice@example.com')
        self.assertFalse(response.data['email_verified'])

    def test_account_requires_authentication(self):
        self.assertEqual(self.client.get(reverse('account')).status_code, 401)