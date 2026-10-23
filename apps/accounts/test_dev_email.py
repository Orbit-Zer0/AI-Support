import io
from contextlib import redirect_stdout

from django.core.mail import EmailMessage
from django.test import SimpleTestCase, override_settings


class ReadableConsoleEmailBackendTests(SimpleTestCase):
    @override_settings(EMAIL_BACKEND='apps.accounts.dev_email.ReadableConsoleEmailBackend')
    def test_prints_readable_text_with_link(self):
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            sent = EmailMessage(
                'Тема', 'Привет!\nhttp://127.0.0.1:8000/?verify=abc', 'a@b.co', ['x@y.zz']
            ).send()

        output = buffer.getvalue()
        self.assertEqual(sent, 1)
        self.assertIn('http://127.0.0.1:8000/?verify=abc', output)
        self.assertIn('Привет!', output)
        self.assertIn('x@y.zz', output)