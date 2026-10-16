from django.test import SimpleTestCase

from .detection import detect_crisis


class DetectCrisisTests(SimpleTestCase):
    def test_detects_russian(self):
        for text in [
            'Я хочу умереть',
            'не хочу больше жить',
            'думаю о суициде',
            'Хочу покончить с собой...',
            'ХОЧУ УМЕРЕТЬ!!!',
            'иногда кажется, что лучше бы меня не было',
        ]:
            with self.subTest(text=text):
                self.assertTrue(detect_crisis(text))

    def test_detects_english(self):
        for text in [
            'I want to die',
            "I don't want to live anymore",
            'thinking about suicide',
            'i wanna kill myself',
        ]:
            with self.subTest(text=text):
                self.assertTrue(detect_crisis(text))

    def test_detects_kyrgyz_draft_patterns(self):
        for text in ['өлгүм келет', 'жашагым келбейт']:
            with self.subTest(text=text):
                self.assertTrue(detect_crisis(text))

    def test_ignores_normal_messages(self):
        for text in [
            'Привет, как дела?',
            'Я устал после экзамена',
            'Нужно убить время до поезда',
            'Я хочу жить в другом городе',
            'How do I kill a Python process?',
            'I love my life',
            '',
            None,
        ]:
            with self.subTest(text=text):
                self.assertFalse(detect_crisis(text))