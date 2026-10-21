from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APITestCase

from apps.accounts.models import Country, Language, UserProfile

from .models import Conversation, Message

User = get_user_model()


def make_conversation(user, first, reply='ok', title=''):
    conversation = Conversation.objects.create(user=user, title=title)
    when = timezone.now() - timedelta(hours=1)
    Message.objects.create(conversation=conversation, role='user', content=first)
    Message.objects.create(conversation=conversation, role='model', content=reply)
    Message.objects.filter(conversation=conversation).update(created_at=when)
    return conversation


class TitleTests(APITestCase):
    def setUp(self):
        self.alice = User.objects.create_user('alice', password='Str0ng-pass-111')
        self.bob = User.objects.create_user('bob', password='Str0ng-pass-222')
        self.client.force_authenticate(self.alice)

    def title_url(self, conversation):
        return reverse('conversation-title', args=[conversation.id])

    def detail_url(self, conversation):
        return reverse('conversation-detail', args=[conversation.id])

    @patch('apps.chat.conversations.generate_title', return_value='Sleep problems')
    def test_generates_and_stores_title_once(self, mock_generate):
        conversation = make_conversation(self.alice, 'I cannot sleep at night')
        first = self.client.post(self.title_url(conversation))
        second = self.client.post(self.title_url(conversation))

        self.assertEqual(first.data['title'], 'Sleep problems')
        self.assertEqual(second.data['title'], 'Sleep problems')
        mock_generate.assert_called_once()
        conversation.refresh_from_db()
        self.assertEqual(conversation.title, 'Sleep problems')

    @patch('apps.chat.conversations.generate_title', side_effect=RuntimeError('boom'))
    def test_failure_falls_back_to_first_message(self, _):
        conversation = make_conversation(self.alice, 'Exam preparation tips')
        response = self.client.post(self.title_url(conversation))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['title'], 'Exam preparation tips')
        conversation.refresh_from_db()
        self.assertEqual(conversation.title, '')

    @patch('apps.chat.conversations.generate_title')
    def test_crisis_conversation_gets_neutral_title_without_model(self, mock_generate):
        country, _ = Country.objects.get_or_create(code='KG', defaults={'name': 'Kyrgyzstan'})
        russian, _ = Language.objects.get_or_create(code='ru', defaults={'name': 'Русский'})
        UserProfile.objects.create(user=self.alice, country=country, language=russian)

        conversation = make_conversation(self.alice, 'Я хочу умереть')
        response = self.client.post(self.title_url(conversation))
        self.assertEqual(response.data['title'], 'Поддержка')
        mock_generate.assert_not_called()

    def test_list_hides_crisis_text_even_without_stored_title(self):
        make_conversation(self.alice, 'I want to die')
        titles = [c['title'] for c in self.client.get(reverse('conversation-list')).data]
        self.assertEqual(titles, ['Support'])

    def test_list_prefers_stored_title(self):
        make_conversation(self.alice, 'hello there', title='My topic')
        titles = [c['title'] for c in self.client.get(reverse('conversation-list')).data]
        self.assertEqual(titles, ['My topic'])

    @patch('apps.chat.conversations.generate_title')
    def test_cannot_generate_title_for_someone_elses_conversation(self, mock_generate):
        conversation = make_conversation(self.bob, 'private')
        self.assertEqual(self.client.post(self.title_url(conversation)).status_code, 404)
        mock_generate.assert_not_called()

    def test_rename(self):
        conversation = make_conversation(self.alice, 'hello')
        response = self.client.patch(self.detail_url(conversation), {'title': '  New   name '}, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['title'], 'New name')

    def test_rename_validation(self):
        conversation = make_conversation(self.alice, 'hello')
        empty = self.client.patch(self.detail_url(conversation), {'title': '   '}, format='json')
        long = self.client.patch(self.detail_url(conversation), {'title': 'x' * 81}, format='json')
        self.assertEqual((empty.status_code, empty.data['code']), (400, 'title_required'))
        self.assertEqual((long.status_code, long.data['code']), (400, 'title_too_long'))

    def test_cannot_rename_someone_elses_conversation(self):
        conversation = make_conversation(self.bob, 'private')
        response = self.client.patch(self.detail_url(conversation), {'title': 'mine now'}, format='json')
        self.assertEqual(response.status_code, 404)

    @patch('apps.chat.conversations.generate_title')
    def test_manual_title_is_not_overwritten(self, mock_generate):
        conversation = make_conversation(self.alice, 'hello', title='Manual')
        response = self.client.post(self.title_url(conversation))
        self.assertEqual(response.data['title'], 'Manual')
        mock_generate.assert_not_called()