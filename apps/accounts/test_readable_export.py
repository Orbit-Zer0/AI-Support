from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APITestCase

from apps.chat.models import Conversation, Message

from .models import Country, Language, UserProfile

User = get_user_model()
PASSWORD = 'Str0ng-pass-111'


def make_user(username='alice', language='en'):
    country, _ = Country.objects.get_or_create(code='KG', defaults={'name': 'Kyrgyzstan'})
    lang, _ = Language.objects.get_or_create(code=language, defaults={'name': language})
    user = User.objects.create_user(username, password=PASSWORD)
    UserProfile.objects.create(user=user, country=country, language=lang)
    return user


def add_conversation(user, title, question, answer):
    conversation = Conversation.objects.create(user=user, title=title)
    Message.objects.create(conversation=conversation, role='user', content=question)
    Message.objects.create(conversation=conversation, role='model', content=answer)
    return conversation


class ReadableExportTests(APITestCase):
    def setUp(self):
        self.alice = make_user('alice')
        self.url = reverse('account-export-readable')

    def body(self):
        self.client.force_authenticate(self.alice)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        return response, response.content.decode()

    def test_requires_authentication(self):
        self.assertEqual(self.client.get(self.url).status_code, 401)

    def test_returns_downloadable_html_with_conversations(self):
        add_conversation(self.alice, 'Exam plan', 'How do I study?', 'Make a plan.')
        response, body = self.body()
        self.assertTrue(response['Content-Type'].startswith('text/html'))
        self.assertIn('attachment', response['Content-Disposition'])
        self.assertIn('Exam plan', body)
        self.assertIn('How do I study?', body)
        self.assertIn('Make a plan.', body)

    def test_html_inside_messages_and_titles_is_escaped(self):
        add_conversation(
            self.alice, '<img src=x onerror=alert(1)>',
            '<script>alert(1)</script>', '<b>bold</b>',
        )
        _, body = self.body()
        self.assertNotIn('<script>alert(1)', body)
        self.assertNotIn('<img src=x', body)
        self.assertNotIn('<b>bold</b>', body)
        self.assertIn('&lt;script&gt;alert(1)', body)

    def test_only_own_conversations_are_included(self):
        bob = make_user('bob')
        add_conversation(bob, 'Bobs secret', 'bob question', 'bob answer')
        add_conversation(self.alice, 'Mine', 'my question', 'my answer')
        _, body = self.body()
        self.assertIn('my question', body)
        self.assertNotIn('bob question', body)
        self.assertNotIn('Bobs secret', body)

    def test_labels_follow_the_users_language(self):
        ruser = make_user('ruser', language='ru')
        add_conversation(ruser, 'Тема', 'вопрос', 'ответ')
        self.client.force_authenticate(ruser)
        body = self.client.get(self.url).content.decode()
        self.assertIn('Мои диалоги', body)
        self.assertIn('lang="ru"', body)

    def test_empty_account_says_so(self):
        _, body = self.body()
        self.assertIn('No conversations yet.', body)

    def test_help_numbers_for_the_users_country_are_included(self):
        _, body = self.body()
        self.assertIn('111', body)

    def test_crisis_text_is_not_used_as_a_title(self):
        add_conversation(self.alice, '', 'I want to die', 'Please call 111')
        _, body = self.body()
        self.assertIn('<h2>Support</h2>', body)