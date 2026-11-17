from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from .services import stream_ai_response

User = get_user_model()


class FakeApiError(Exception):
    def __init__(self, code):
        super().__init__(f'error {code}')
        self.code = code


class FakeChunk:
    def __init__(self, text):
        self.text = text


def streaming_client(behaviour):
    client = MagicMock()

    def create(model, **kwargs):
        chat = MagicMock()
        outcome = behaviour[model]
        if isinstance(outcome, Exception):
            chat.send_message_stream.side_effect = outcome
        elif callable(outcome):
            chat.send_message_stream.side_effect = lambda message: outcome()
        else:
            chat.send_message_stream.return_value = iter([FakeChunk(text) for text in outcome])
        return chat

    client.chats.create.side_effect = create
    return client


def models_used(client):
    return [call.kwargs['model'] for call in client.chats.create.call_args_list]


@override_settings(GEMINI_MODEL='m1', GEMINI_FALLBACK_MODELS=['m2'])
class StreamServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('u', password='Str0ng-pass-111')

    def collect(self, client):
        with patch('apps.chat.services._get_client', return_value=client):
            return list(stream_ai_response([], 'hello', self.user))

    def test_yields_chunks_in_order_and_skips_empty_ones(self):
        client = streaming_client({'m1': ['Hel', None, '', 'lo'], 'm2': ['x']})
        self.assertEqual(self.collect(client), ['Hel', 'lo'])
        self.assertEqual(models_used(client), ['m1'])

    def test_error_before_first_text_moves_to_next_model(self):
        client = streaming_client({'m1': FakeApiError(429), 'm2': ['from m2']})
        self.assertEqual(self.collect(client), ['from m2'])
        self.assertEqual(models_used(client), ['m1', 'm2'])

    def test_error_after_first_text_is_not_retried(self):
        def breaks():
            yield FakeChunk('Hel')
            raise FakeApiError(503)

        client = streaming_client({'m1': breaks, 'm2': ['other']})
        collected = []
        with patch('apps.chat.services._get_client', return_value=client):
            with self.assertRaises(FakeApiError):
                for text in stream_ai_response([], 'hello', self.user):
                    collected.append(text)
        self.assertEqual(collected, ['Hel'])
        self.assertEqual(models_used(client), ['m1'])

    def test_other_errors_are_not_retried(self):
        client = streaming_client({'m1': FakeApiError(400), 'm2': ['x']})
        with patch('apps.chat.services._get_client', return_value=client):
            with self.assertRaises(FakeApiError):
                list(stream_ai_response([], 'hello', self.user))
        self.assertEqual(models_used(client), ['m1'])

    def test_all_models_failing_raises_the_last_error(self):
        client = streaming_client({'m1': FakeApiError(429), 'm2': FakeApiError(503)})
        with patch('apps.chat.services._get_client', return_value=client):
            with self.assertRaises(FakeApiError) as raised:
                list(stream_ai_response([], 'hello', self.user))
        self.assertEqual(raised.exception.code, 503)

    def test_empty_stream_yields_nothing(self):
        client = streaming_client({'m1': [], 'm2': ['x']})
        self.assertEqual(self.collect(client), [])