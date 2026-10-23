from django.core.mail.backends.base import BaseEmailBackend


class ReadableConsoleEmailBackend(BaseEmailBackend):

    def send_messages(self, email_messages):
        count = 0
        for message in email_messages:
            lines = [
                '=' * 72,
                'ПИСЬМО (режим разработки: наружу не отправлено)',
                f'Кому: {", ".join(message.to)}',
                f'Тема: {message.subject}',
                '-' * 72,
                message.body,
                '=' * 72,
            ]
            print('\n'.join(lines), flush=True)
            count += 1
        return count