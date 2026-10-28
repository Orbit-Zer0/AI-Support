import json
from datetime import datetime, timedelta
from datetime import timezone as dt_timezone
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APITestCase

from apps.chat.memory import get_history
from apps.chat.models import Conversation, Message

from .data_transfer import EXPORT_FORMAT, EXPORT_VERSION
from .models import Country, Language, UserProfile

User = get_user_model()
PASSWORD = 'Str0ng-pass-111'


def make_user(username='alice', language='en'):
    country, _ = Country.objects.get_or_create(code='KG', defaults={'name': 'Kyrgyzstan'})
    lang, _ = Language.objects.get_or_create(code=language, defaults={'name': language})
    user = User.objects.create_user(username, password=PASSWORD)
    UserProfile.objects.create(user=user, country=country, language=lang)
    return user


def pair(question='hello', answer='hi', when=None):
    first = {'role': 'user', 'content': question}
    second = {'role': 'model', 'content': answer}
    if when:
        first['created_at'] = when
        second['created_at'] = when
    return [first, second]


def package(conversations, **extra):
    data = {'format': EXPORT_FORMAT, 'version': EXPORT_VERSION, 'conversations': conversations}
    data.update(extra)
    return data


class ImportTests(APITestCase):
    def setUp(self):
        self.alice = make_user('alice')
        self.bob = make_user('bob')
        self.client.force_authenticate(self.alice)
        self.url = reverse('account-import')

    def upload(self, data):
        return self.client.post(self.url, data, format='json')

    def test_requires_authentication(self):
        self.client.force_authenticate(None)
        self.assertEqual(self.upload(package([])).status_code, 401)

    def test_imports_conversations_titles_and_messages(self):
        response = self.upload(package([
            {'title': 'First topic', 'messages': pair('q1', 'a1') + pair('q2', 'a2')},
            {'title': 'Second topic', 'messages': pair('q3', 'a3')},
        ]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['imported'], 2)
        self.assertEqual(response.data['skipped'], {'invalid': 0, 'duplicates': 0})

        first = Conversation.objects.get(user=self.alice, title='First topic')
        rows = list(first.messages.order_by('id').values_list('role', 'content'))
        self.assertEqual(
            rows, [('user', 'q1'), ('model', 'a1'), ('user', 'q2'), ('model', 'a2')]
        )

    def test_conversations_always_belong_to_the_importing_user(self):
        data = package([{
            'id': 999, 'user': self.bob.pk, 'title': 'Mine', 'messages': pair(),
        }])
        self.upload(data)
        self.assertEqual(Conversation.objects.filter(user=self.alice).count(), 1)
        self.assertEqual(Conversation.objects.filter(user=self.bob).count(), 0)
        self.assertFalse(Conversation.objects.filter(id=999).exists())

    def test_timestamps_are_preserved(self):
        self.upload(package([{
            'title': 't', 'messages': pair(when='2024-05-01T10:00:00Z'),
        }]))
        expected = datetime(2024, 5, 1, 10, 0, tzinfo=dt_timezone.utc)
        conversation = Conversation.objects.get(user=self.alice)
        self.assertEqual(conversation.created_at, expected)
        for message in conversation.messages.all():
            self.assertEqual(message.created_at, expected)

    def test_naive_timestamps_are_read_as_utc(self):
        self.upload(package([{'title': 't', 'messages': pair(when='2024-05-01T10:00:00')}]))
        message = Message.objects.filter(conversation__user=self.alice).first()
        self.assertEqual(message.created_at, datetime(2024, 5, 1, 10, 0, tzinfo=dt_timezone.utc))

    def test_future_and_invalid_timestamps_become_now(self):
        before = timezone.now() - timedelta(seconds=1)
        self.upload(package([{'title': 't', 'messages': [
            {'role': 'user', 'content': 'q', 'created_at': '2999-01-01T00:00:00Z'},
            {'role': 'model', 'content': 'a', 'created_at': 'not-a-date'},
        ]}]))
        for message in Message.objects.filter(conversation__user=self.alice):
            self.assertGreaterEqual(message.created_at, before)
            self.assertLessEqual(message.created_at, timezone.now())

    def test_duplicates_are_skipped_even_inside_one_file(self):
        data = package([
            {'title': 'a', 'messages': pair('same', 'same answer')},
            {'title': 'b', 'messages': pair('same', 'same answer')},
        ])
        first = self.upload(data)
        self.assertEqual((first.data['imported'], first.data['skipped']['duplicates']), (1, 1))

        second = self.upload(data)
        self.assertEqual((second.data['imported'], second.data['skipped']['duplicates']), (0, 2))
        self.assertEqual(Conversation.objects.filter(user=self.alice).count(), 1)

    def test_conversations_that_cannot_be_continued_are_skipped(self):
        valid = {'title': 'ok', 'messages': pair('q', 'a')}
        broken = [
            {'title': 'x', 'messages': [{'role': 'model', 'content': 'x'}, {'role': 'user', 'content': 'y'}]},
            {'title': 'x', 'messages': pair() + [{'role': 'user', 'content': 'dangling'}]},
            {'title': 'x', 'messages': [{'role': 'user', 'content': 'a'}, {'role': 'user', 'content': 'b'}]},
            {'title': 'x', 'messages': [{'role': 'system', 'content': 'x'}, {'role': 'model', 'content': 'y'}]},
            {'title': 'x', 'messages': [{'role': 'user', 'content': '   '}, {'role': 'model', 'content': 'y'}]},
            {'title': 'x', 'messages': [{'role': 'user', 'content': 123}, {'role': 'model', 'content': 'y'}]},
            {'title': 'x', 'messages': 'nope'},
            {'title': 'x', 'messages': []},
            'not a dict',
        ]
        response = self.upload(package([valid, *broken]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['imported'], 1)
        self.assertEqual(response.data['skipped']['invalid'], len(broken))

    def test_too_long_message_makes_the_conversation_invalid(self):
        response = self.upload(package([
            {'title': 't', 'messages': pair('q' * 20001, 'a')},
        ]))
        self.assertEqual(response.data['skipped']['invalid'], 1)

    def test_title_with_crisis_words_is_not_stored(self):
        self.upload(package([
            {'title': 'I want to die', 'messages': pair('I want to die', 'Please call 111')},
        ]))
        self.assertEqual(Conversation.objects.get(user=self.alice).title, '')
        titles = [c['title'] for c in self.client.get(reverse('conversation-list')).data]
        self.assertEqual(titles, ['Support'])

    def test_title_is_cleaned(self):
        self.upload(package([
            {'title': '  Many   spaces ', 'messages': pair('a', 'b')},
            {'title': 'x' * 200, 'messages': pair('c', 'd')},
        ]))
        titles = set(Conversation.objects.filter(user=self.alice).values_list('title', flat=True))
        self.assertIn('Many spaces', titles)
        self.assertTrue(all(len(title) <= 80 for title in titles))

    def test_null_characters_are_removed(self):
        self.upload(package([{'title': 't', 'messages': pair('a\x00b', 'c\x00d')}]))
        contents = set(Message.objects.filter(conversation__user=self.alice).values_list('content', flat=True))
        self.assertEqual(contents, {'ab', 'cd'})

    def test_old_exports_without_format_and_version_are_accepted(self):
        response = self.upload({'conversations': [{'title': 't', 'messages': pair()}]})
        self.assertEqual(response.data['imported'], 1)

    def test_foreign_format_or_future_version_is_rejected(self):
        for extra in ({'format': 'something-else'}, {'version': 99}, {'version': 'x'}, {'version': True}):
            with self.subTest(extra=extra):
                data = package([{'title': 't', 'messages': pair()}], **extra)
                response = self.upload(data)
                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.data['code'], 'import_unsupported')
        self.assertEqual(Conversation.objects.filter(user=self.alice).count(), 0)

    def test_malformed_files_are_rejected(self):
        for body in ([1, 2, 3], {}, {'conversations': 'x'}, {'conversations': None}):
            with self.subTest(body=body):
                response = self.upload(body)
                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.data['code'], 'import_invalid')

    def test_too_many_conversations_are_rejected(self):
        response = self.upload(package([{}] * 201))
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['code'], 'import_too_many')

    @patch('apps.accounts.data_transfer.MAX_IMPORT_MESSAGES', 3)
    def test_too_many_messages_are_rejected(self):
        response = self.upload(package([
            {'title': 'a', 'messages': pair('q1', 'a1')},
            {'title': 'b', 'messages': pair('q2', 'a2')},
        ]))
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['code'], 'import_too_large')
        self.assertEqual(Conversation.objects.filter(user=self.alice).count(), 0)

    @patch('apps.accounts.account_views.MAX_IMPORT_BYTES', 10)
    def test_oversized_body_is_refused(self):
        response = self.upload(package([{'title': 't', 'messages': pair()}]))
        self.assertEqual(response.status_code, 413)
        self.assertEqual(response.data['code'], 'import_too_large')

    def test_deeply_nested_json_is_rejected_without_a_crash(self):
        response = self.client.post(
            self.url, '[' * 5000 + ']' * 5000, content_type='application/json'
        )
        self.assertEqual(response.status_code, 400)

    def test_roundtrip_through_export(self):
        for title, question, answer in (('One', 'q1', 'a1'), ('Two', 'q2', 'a2')):
            conversation = Conversation.objects.create(user=self.alice, title=title)
            Message.objects.create(conversation=conversation, role='user', content=question)
            Message.objects.create(conversation=conversation, role='model', content=answer)

        def snapshot():
            return [
                (m.conversation.title, m.role, m.content, m.created_at)
                for m in Message.objects.filter(conversation__user=self.alice)
                .select_related('conversation').order_by('conversation__title', 'id')
            ]

        before = snapshot()
        exported = json.loads(json.dumps(self.client.get(reverse('account-export')).data))
        Conversation.objects.filter(user=self.alice).delete()

        response = self.upload(exported)
        self.assertEqual(response.data['imported'], 2)
        self.assertEqual(snapshot(), before)

    def test_imported_conversation_can_be_continued(self):
        self.upload(package([{'title': 't', 'messages': pair('q1', 'a1') + pair('q2', 'a2')}]))
        conversation = Conversation.objects.get(user=self.alice)
        roles = [item['role'] for item in get_history(conversation)]
        self.assertEqual(roles, ['user', 'model', 'user', 'model'])
        self.assertEqual(len(self.client.get(reverse('conversation-list')).data), 1)