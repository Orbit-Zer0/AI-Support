from django.test import TestCase, override_settings


class IndexPageTests(TestCase):
    @override_settings(CONTACT_EMAIL='help@example.com')
    def test_contact_email_comes_from_settings(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-contact-email="help@example.com"')

    @override_settings(CONTACT_EMAIL='')
    def test_page_works_without_contact_email(self):
        response = self.client.get('/')
        self.assertContains(response, 'data-contact-email=""')

    @override_settings(CONTACT_EMAIL='"><script>alert(1)</script>')
    def test_contact_email_is_escaped(self):
        response = self.client.get('/')
        self.assertNotContains(response, '<script>alert(1)')