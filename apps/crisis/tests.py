from django.test import TestCase

from apps.accounts.models import Country, Language

from .fallback import FALLBACK_URL
from .models import CrisisResource, CrisisResourceText
from .services import build_crisis_block, get_crisis_contacts


class CrisisServicesTests(TestCase):
    def setUp(self):
        self.country, _ = Country.objects.get_or_create(
            code='UZ', defaults={'name': 'Uzbekistan'}
        )
        self.ru, _ = Language.objects.get_or_create(code='ru', defaults={'name': 'Русский'})
        self.en, _ = Language.objects.get_or_create(code='en', defaults={'name': 'English'})
        self.ky, _ = Language.objects.get_or_create(code='ky', defaults={'name': 'Кыргызча'})

    def make_resource(self, phone, texts, **kwargs):
        resource = CrisisResource.objects.create(
            country=self.country, phone=phone,
            kind=kwargs.pop('kind', 'hotline'), **kwargs,
        )
        for language, title in texts.items():
            CrisisResourceText.objects.create(
                resource=resource, language=language, title=title
            )
        return resource

    def test_uses_user_language_when_available(self):
        self.make_resource('111', {self.ru: 'Телефон доверия', self.en: 'Helpline'})
        contacts = get_crisis_contacts('UZ', 'ru')
        self.assertEqual(contacts[0]['title'], 'Телефон доверия')
        self.assertEqual(contacts[0]['phone'], '111')

    def test_falls_back_to_english_when_language_missing(self):
        self.make_resource('111', {self.ru: 'Телефон доверия', self.en: 'Helpline'})
        contacts = get_crisis_contacts('UZ', 'ky')
        self.assertEqual(contacts[0]['title'], 'Helpline')

    def test_falls_back_to_any_text_when_chain_is_empty(self):
        self.make_resource('111', {self.ky: 'Ишеним телефону'})
        contacts = get_crisis_contacts('UZ', 'ru')
        self.assertEqual(contacts[0]['title'], 'Ишеним телефону')

    def test_phone_is_shown_even_without_any_text(self):
        self.make_resource('112', {}, kind='emergency')
        contacts = get_crisis_contacts('UZ', 'ru')
        self.assertEqual(contacts[0]['phone'], '112')
        self.assertTrue(contacts[0]['title'])

    def test_inactive_resource_is_hidden(self):
        self.make_resource('111', {self.en: 'Helpline'}, is_active=False)
        self.assertEqual(get_crisis_contacts('UZ', 'en'), [])

    def test_sorted_by_priority(self):
        self.make_resource('103', {self.en: 'Ambulance'}, priority=30)
        self.make_resource('111', {self.en: 'Helpline'}, priority=10)
        phones = [c['phone'] for c in get_crisis_contacts('UZ', 'en')]
        self.assertEqual(phones, ['111', '103'])

    def test_country_without_data_returns_fallback_text(self):
        block = build_crisis_block('TJ', 'ru')
        self.assertIn(FALLBACK_URL, block)

    def test_missing_country_returns_fallback_text(self):
        block = build_crisis_block(None, 'en')
        self.assertIn(FALLBACK_URL, block)

    def test_block_contains_phone_numbers(self):
        self.make_resource('111', {self.en: 'Helpline'})
        block = build_crisis_block('UZ', 'en')
        self.assertIn('111', block)
        self.assertIn('Helpline', block)