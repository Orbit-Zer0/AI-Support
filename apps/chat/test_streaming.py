import json
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APITestCase

from apps.accounts.models import Country, Language, UserProfile
from apps.crisis.models import CrisisResource, CrisisResourceText

from .models import Conversation, Message

User = get_user_model()


class FakeApiError(Exception):
    def __init__(self, code):
        super().__init__(f'error {code}')
        self.code = code


def fake_stream(*texts):
    def factory(history, message, user):
        return (text for text in texts)
    return factory


def failing_stream(error):
    def factory(history, message, user):
        raise error
        yield
    return factory


def breaking_stream(first, error):
    def factory(history, message, user):
        yield first
        raise error
    return factory


def read_events(response):
    raw = b''.join(response.streaming_content).decode('utf-8')
    return [json.loads(line) for line in raw.splitlines() if line.strip()]


class StreamBase(APITestCase):
    def setUp(self):
        self.alice = User.objects.create_user('alice', password='Str0ng-pass-111')
        self.client.force_authenticate(self.alice)
        self.url = reverse('chat-stream')

    def post(self, message='hello', **extra):
        return self.client.post(self.url, {'message': message, **extra}, format='json')


class StreamBasicsTests(StreamBase):
    @patch('apps.chat.views.stream_ai_response', side_effect=fake_stream('Hello', ' world'))
    def test_events_and_saved_messages(self, _):
        before = timezone.now()
        response = self.post()
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response['Content-Type'].startswith('application/x-ndjson'))
        self.assertEqual(response['X-Accel-Buffering'], 'no')

        events = read_events(response)
        self.assertEqual([e['type'] for e in events], ['start', 'delta', 'delta', 'done'])
        done = events[-1]
        self.assertEqual(done['response'], 'Hello world')
        self.assertFalse(done['crisis'])
        self.assertEqual(events[0]['conversation_id'], done['conversation_id'])

        messages = list(Message.objects.filter(conversation_id=done['conversation_id']))
        self.assertEqual([(m.role, m.content) for m in messages],
                            [('user', 'hello'), ('model', 'Hello world')])
        user_msg, bot_msg = messages
        self.assertGreaterEqual(user_msg.created_at, before)
        self.assertLessEqual(user_msg.created_at, bot_msg.created_at)
        self.assertFalse(bot_msg.interrupted)
        self.assertIsNotNone(bot_msg.first_token_ms)
        self.assertGreaterEqual(bot_msg.duration_ms, bot_msg.first_token_ms)
        self.assertEqual(done['bot_message']['duration_ms'], bot_msg.duration_ms)

    def test_requires_authentication(self):
        self.client.force_authenticate(None)
        self.assertEqual(self.post().status_code, 401)

    def test_validation_errors_are_plain_json(self):
        self.assertEqual(self.post(message='   ').data['code'], 'message_required')
        self.assertEqual(self.post(message='a' * 4001).data['code'], 'message_too_long')
        self.assertEqual(self.post(conversation_id='abc').data['code'], 'invalid_conversation_id')

    def test_other_users_conversation_is_not_found(self):
        bob = User.objects.create_user('bob', password='Str0ng-pass-222')
        conversation = Conversation.objects.create(user=bob)
        self.assertEqual(self.post(conversation_id=conversation.id).status_code, 404)

    @patch('apps.chat.views.stream_ai_response')
    def test_existing_conversation_is_continued_with_its_history(self, mock_stream):
        mock_stream.side_effect = fake_stream('Second answer')
        conversation = Conversation.objects.create(user=self.alice)
        Message.objects.create(conversation=conversation, role='user', content='first')
        Message.objects.create(conversation=conversation, role='model', content='first answer')

        events = read_events(self.post('second', conversation_id=conversation.id))
        self.assertEqual(events[-1]['conversation_id'], conversation.id)
        history = mock_stream.call_args.args[0]
        self.assertEqual([item['role'] for item in history], ['user', 'model'])
        self.assertEqual(conversation.messages.count(), 4)

    @patch('apps.chat.views.maybe_summarize')
    @patch('apps.chat.views.stream_ai_response', side_effect=fake_stream('ok'))
    def test_summarization_runs_after_the_stream(self, _stream, mock_summarize):
        read_events(self.post())
        mock_summarize.assert_called_once()

    @patch('apps.chat.views.stream_ai_response', side_effect=fake_stream('ok'))
    def test_detail_endpoint_returns_times_and_durations(self, _):
        done = read_events(self.post())[-1]
        detail = self.client.get(reverse('conversation-detail', args=[done['conversation_id']]))
        user_row, bot_row = detail.data['messages']
        self.assertIsNone(user_row['duration_ms'])
        self.assertIsNotNone(bot_row['first_token_ms'])
        self.assertIsNotNone(bot_row['duration_ms'])
        self.assertFalse(bot_row['interrupted'])
        self.assertTrue(user_row['created_at'])


class StreamFailureTests(StreamBase):
    @patch('apps.chat.views.stream_ai_response', side_effect=failing_stream(RuntimeError('boom')))
    def test_failure_before_first_text_is_a_json_error(self, _):
        response = self.post()
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.data['code'], 'ai_unavailable')
        self.assertEqual(Conversation.objects.count(), 0)

    @patch('apps.chat.views.stream_ai_response', side_effect=failing_stream(FakeApiError(429)))
    def test_quota_error_is_reported(self, _):
        response = self.post()
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.data['code'], 'ai_quota')

    @patch('apps.chat.views.stream_ai_response', side_effect=fake_stream())
    def test_empty_stream_is_an_error(self, _):
        response = self.post()
        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.data['code'], 'ai_empty')

    @patch('apps.chat.views.stream_ai_response', side_effect=breaking_stream('Partial', RuntimeError('boom')))
    def test_error_in_the_middle_keeps_the_shown_part(self, _):
        events = read_events(self.post())
        self.assertEqual([e['type'] for e in events], ['start', 'delta', 'error'])
        self.assertTrue(events[-1]['partial'])

        bot = Message.objects.get(role='model')
        self.assertEqual(bot.content, 'Partial')
        self.assertTrue(bot.interrupted)
        self.assertEqual(Message.objects.get(role='user').content, 'hello')

    @patch('apps.chat.views.stream_ai_response', side_effect=fake_stream('First ', 'second'))
    def test_client_disconnect_saves_the_shown_part_as_interrupted(self, _):
        response = self.post()
        iterator = iter(response.streaming_content)
        start = json.loads(next(iterator))
        first_delta = json.loads(next(iterator))
        self.assertEqual((start['type'], first_delta['type']), ('start', 'delta'))
        response.close()

        bot = Message.objects.get(role='model')
        self.assertEqual(bot.content, 'First')
        self.assertTrue(bot.interrupted)
        self.assertEqual(Message.objects.filter(role='user').count(), 1)

    @patch('apps.chat.views.stream_ai_response', side_effect=fake_stream('text'))
    def test_disconnect_before_any_text_leaves_nothing_behind(self, _):
        response = self.post()
        iterator = iter(response.streaming_content)
        self.assertEqual(json.loads(next(iterator))['type'], 'start')
        response.close()

        self.assertEqual(Conversation.objects.count(), 0)
        self.assertEqual(Message.objects.count(), 0)

    @patch('apps.chat.views.maybe_summarize')
    @patch('apps.chat.views.stream_ai_response', side_effect=fake_stream('a', 'b'))
    def test_summarization_also_runs_after_an_interrupted_reply(self, _stream, mock_summarize):
        response = self.post()
        iterator = iter(response.streaming_content)
        next(iterator)
        next(iterator)
        response.close()
        mock_summarize.assert_called_once()


class StreamCrisisTests(StreamBase):
    def setUp(self):
        super().setUp()
        country, _ = Country.objects.get_or_create(code='UZ', defaults={'name': 'Uzbekistan'})
        english, _ = Language.objects.get_or_create(code='en', defaults={'name': 'English'})
        resource = CrisisResource.objects.create(country=country, phone='911', kind='hotline')
        CrisisResourceText.objects.create(resource=resource, language=english, title='Test line')
        UserProfile.objects.create(user=self.alice, country=country, language=english)

    @patch('apps.chat.views.stream_ai_response', side_effect=fake_stream('I am here 😊', ' for you ❤️'))
    def test_emoji_removed_and_contacts_appended(self, _):
        events = read_events(self.post('I want to die'))
        deltas = ''.join(e['text'] for e in events if e['type'] == 'delta')
        done = events[-1]

        self.assertTrue(done['crisis'])
        self.assertNotIn('😊', deltas)
        self.assertNotIn('❤', deltas)
        self.assertIn('911', deltas)
        self.assertIn('911', done['response'])
        self.assertIn('911', Message.objects.get(role='model').content)

    @patch('apps.chat.views.stream_ai_response', side_effect=fake_stream('Please call 911 now.'))
    def test_contacts_are_not_duplicated_when_the_model_included_them(self, _):
        done = read_events(self.post('I want to die'))[-1]
        self.assertEqual(done['response'], 'Please call 911 now.')

    @patch('apps.chat.views.stream_ai_response', side_effect=fake_stream('Hi 😊'))
    def test_normal_messages_keep_their_emoji(self, _):
        done = read_events(self.post('Hello'))[-1]
        self.assertFalse(done['crisis'])
        self.assertEqual(done['response'], 'Hi 😊')

    @patch('apps.chat.views.stream_ai_response', side_effect=failing_stream(RuntimeError('boom')))
    def test_crisis_message_gets_emergency_reply_when_the_model_is_down(self, _):
        response = self.post('I want to die')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['crisis'])
        self.assertIn('911', response.data['response'])
        self.assertIn('911', Message.objects.get(role='model').content)

    @patch('apps.chat.views.stream_ai_response', side_effect=fake_stream('I am here', ' with you'))
    def test_stopped_crisis_reply_still_gets_contacts_saved(self, _):
        response = self.post('I want to die')
        iterator = iter(response.streaming_content)
        next(iterator)
        next(iterator)
        response.close()

        bot = Message.objects.get(role='model')
        self.assertTrue(bot.interrupted)
        self.assertIn('911', bot.content)


class NonStreamingEndpointTests(StreamBase):
    @patch('apps.chat.views.get_ai_response', return_value='hello there')
    def test_regular_endpoint_reports_times_too(self, _):
        response = self.client.post(reverse('chat'), {'message': 'hi'}, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['response'], 'hello there')
        self.assertTrue(response.data['user_message']['created_at'])
        self.assertIsNone(response.data['bot_message']['first_token_ms'])
        self.assertIsNotNone(response.data['bot_message']['duration_ms'])