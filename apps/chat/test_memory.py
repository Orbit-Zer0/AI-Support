from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APITestCase

from .memory import (
    KEEP_RECENT_MESSAGES,
    SUMMARIZE_AFTER_MESSAGES,
    get_history,
    maybe_summarize,
)
from .models import Conversation, Message

User = get_user_model()


def fill(conversation, pairs, text=''):
    for i in range(pairs):
        Message.objects.create(conversation=conversation, role='user', content=f'q{i}{text}')
        Message.objects.create(conversation=conversation, role='model', content=f'a{i}{text}')


class MemoryTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('u', password='Str0ng-pass-111')
        self.conversation = Conversation.objects.create(user=self.user)

    def test_history_without_summary_is_all_messages(self):
        fill(self.conversation, 2)
        contents = [m['content'] for m in get_history(self.conversation)]
        self.assertEqual(contents, ['q0', 'a0', 'q1', 'a1'])

    @patch('apps.chat.memory.summarize_conversation')
    def test_no_summary_below_threshold(self, mock_summarize):
        fill(self.conversation, SUMMARIZE_AFTER_MESSAGES // 2)
        maybe_summarize(self.conversation)
        mock_summarize.assert_not_called()

    @patch('apps.chat.memory.summarize_conversation', return_value='SUMMARY')
    def test_old_part_is_folded_and_recent_kept(self, mock_summarize):
        fill(self.conversation, SUMMARIZE_AFTER_MESSAGES // 2 + 1)
        maybe_summarize(self.conversation)

        self.conversation.refresh_from_db()
        self.assertEqual(self.conversation.summary, 'SUMMARY')

        history = get_history(self.conversation)
        self.assertEqual(len(history), 2 + KEEP_RECENT_MESSAGES)
        self.assertEqual([history[0]['role'], history[1]['role']], ['user', 'model'])
        self.assertIn('SUMMARY', history[0]['content'])
        self.assertEqual(history[2]['role'], 'user')
        self.assertEqual(history[-1]['content'], 'a12')

    @patch('apps.chat.memory.summarize_conversation', return_value='S')
    def test_long_messages_trigger_summary_by_size(self, mock_summarize):
        fill(self.conversation, 5, text='x' * 5000)
        maybe_summarize(self.conversation)
        mock_summarize.assert_called_once()
        self.assertEqual(len(get_history(self.conversation)), 2 + KEEP_RECENT_MESSAGES)

    @patch('apps.chat.memory.summarize_conversation', side_effect=['S1', 'S2'])
    def test_second_fold_receives_previous_summary(self, mock_summarize):
        fill(self.conversation, 13)
        maybe_summarize(self.conversation)
        fill(self.conversation, 9)
        maybe_summarize(self.conversation)

        self.assertEqual(mock_summarize.call_args_list[1].args[0], 'S1')
        self.conversation.refresh_from_db()
        self.assertEqual(self.conversation.summary, 'S2')

    @patch('apps.chat.memory.summarize_conversation', side_effect=RuntimeError('boom'))
    def test_failure_changes_nothing_and_does_not_raise(self, _):
        fill(self.conversation, 14)
        maybe_summarize(self.conversation)
        self.conversation.refresh_from_db()
        self.assertEqual(self.conversation.summary, '')
        self.assertEqual(self.conversation.summarized_until, 0)

    @patch('apps.chat.memory.summarize_conversation', return_value='   ')
    def test_empty_summary_is_ignored(self, _):
        fill(self.conversation, 14)
        maybe_summarize(self.conversation)
        self.conversation.refresh_from_db()
        self.assertEqual(self.conversation.summary, '')


class ViewMemoryIntegrationTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user('alice', password='Str0ng-pass-111')
        self.client.force_authenticate(self.user)
        self.url = reverse('chat')

    @patch('apps.chat.views.maybe_summarize')
    @patch('apps.chat.views.get_ai_response', return_value='hi')
    def test_summarization_runs_after_successful_reply(self, _ai, mock_summarize):
        response = self.client.post(self.url, {'message': 'hello'}, format='json')
        self.assertEqual(response.status_code, 200)
        mock_summarize.assert_called_once()

    @patch('apps.chat.views.maybe_summarize')
    @patch('apps.chat.views.get_ai_response', side_effect=RuntimeError('boom'))
    def test_no_summarization_when_reply_failed(self, _ai, mock_summarize):
        response = self.client.post(self.url, {'message': 'hello'}, format='json')
        self.assertEqual(response.status_code, 503)
        mock_summarize.assert_not_called()