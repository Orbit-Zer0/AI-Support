from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase

from .layer import apply_crisis_layer, strip_emoji

User = get_user_model()


class StripEmojiTests(SimpleTestCase):
    def test_removes_emoji_but_keeps_text(self):
        self.assertEqual(strip_emoji('Я рядом 😊 и слушаю ❤️'), 'Я рядом и слушаю ')

    def test_plain_text_is_unchanged(self):
        self.assertEqual(strip_emoji('Позвони по номеру 111.'), 'Позвони по номеру 111.')


class CrisisLayerEmojiTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('u', password='Str0ng-pass-111')

    def test_emoji_are_removed_from_crisis_replies(self):
        reply, crisis = apply_crisis_layer('I want to die', "I'm here 😊 for you ❤️", self.user)
        self.assertTrue(crisis)
        self.assertNotIn('😊', reply)
        self.assertNotIn('❤', reply)

    def test_normal_replies_keep_their_emoji(self):
        reply, crisis = apply_crisis_layer('Hello', 'Hi there 😊', self.user)
        self.assertFalse(crisis)
        self.assertEqual(reply, 'Hi there 😊')