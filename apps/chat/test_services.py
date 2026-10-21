from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase, override_settings

from .services import clean_title, get_ai_response

User = get_user_model()


class FakeApiError(Exception):
    def __init__(self, code):
        super().__init__(f'error {code}')
        self.code = code


def fake_client(behaviour):
    client = MagicMock()

    def create(model, **kwargs):
        chat = MagicMock()
        outcome = behaviour[model]
        if isinstance(outcome, Exception):
            chat.send_message.side_effect = outcome
        else:
            chat.send_message.return_value.text = outcome
        return chat

    client.chats.create.side_effect = create
    return client


def models_used(client):
    return [call.kwargs['model'] for call in client.chats.create.call_args_list]


class ModelFallbackTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('u', password='Str0ng-pass-111')

    def ask(self, client):
        with patch('apps.chat.services._get_client', return_value=client):
            return get_ai_response([], 'hello', self.user)

    @override_settings(GEMINI_MODEL='m1', GEMINI_FALLBACK_MODELS=['m2'])
    def test_primary_model_is_used_when_it_works(self):
        client = fake_client({'m1': 'from m1', 'm2': 'from m2'})
        self.assertEqual(self.ask(client), 'from m1')
        self.assertEqual(models_used(client), ['m1'])

    @override_settings(GEMINI_MODEL='m1', GEMINI_FALLBACK_MODELS=['m2'])
    def test_quota_error_moves_to_next_model(self):
        client = fake_client({'m1': FakeApiError(429), 'm2': 'from m2'})
        self.assertEqual(self.ask(client), 'from m2')
        self.assertEqual(models_used(client), ['m1', 'm2'])

    @override_settings(GEMINI_MODEL='m1', GEMINI_FALLBACK_MODELS=['m2'])
    def test_model_not_found_moves_to_next_model(self):
        client = fake_client({'m1': FakeApiError(404), 'm2': 'from m2'})
        self.assertEqual(self.ask(client), 'from m2')

    @override_settings(GEMINI_MODEL='m1', GEMINI_FALLBACK_MODELS=['m2'])
    def test_other_errors_are_not_retried(self):
        client = fake_client({'m1': FakeApiError(400), 'm2': 'from m2'})
        with self.assertRaises(FakeApiError):
            self.ask(client)
        self.assertEqual(models_used(client), ['m1'])

    @override_settings(GEMINI_MODEL='m1', GEMINI_FALLBACK_MODELS=['m2'])
    def test_all_models_failing_raises_last_error(self):
        client = fake_client({'m1': FakeApiError(429), 'm2': FakeApiError(503)})
        with self.assertRaises(FakeApiError) as raised:
            self.ask(client)
        self.assertEqual(raised.exception.code, 503)

    @override_settings(GEMINI_MODEL='m1', GEMINI_FALLBACK_MODELS=['m1', 'm1'])
    def test_duplicate_models_are_tried_once(self):
        client = fake_client({'m1': FakeApiError(429)})
        with self.assertRaises(FakeApiError):
            self.ask(client)
        self.assertEqual(models_used(client), ['m1'])

    @override_settings(GEMINI_MODEL='', GEMINI_FALLBACK_MODELS=[])
    def test_no_model_configured_raises_clear_error(self):
        with self.assertRaises(RuntimeError):
            self.ask(fake_client({}))


class CleanTitleTests(SimpleTestCase):
    def test_removes_quotes_markdown_and_trailing_dot(self):
        self.assertEqual(clean_title('**«Проблемы со сном».**'), 'Проблемы со сном')

    def test_takes_only_first_line(self):
        self.assertEqual(clean_title('Title\nSome explanation'), 'Title')

    def test_truncates_long_titles(self):
        self.assertLessEqual(len(clean_title('word ' * 50)), 60)

    def test_empty_input(self):
        self.assertEqual(clean_title(None), '')
        self.assertEqual(clean_title('   '), '')