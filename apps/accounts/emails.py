from urllib.parse import quote

from django.conf import settings
from django.core.mail import send_mail
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from .tokens import make_verification_token, reset_token_generator

TEXTS = {
    'ru': {
        'verify_subject': 'Подтверди почту в AI Support',
        'verify_body': (
            'Привет, {username}!\n\n'
            'Чтобы подтвердить почту, открой ссылку:\n{link}\n\n'
            'Ссылка действует 24 часа. Если ты не регистрировался в AI Support, '
            'просто проигнорируй это письмо.'
        ),
        'reset_subject': 'Сброс пароля в AI Support',
        'reset_body': (
            'Привет, {username}!\n\n'
            'Мы получили запрос на сброс пароля. Чтобы задать новый пароль, открой ссылку:\n{link}\n\n'
            'Ссылка действует 1 час и работает один раз. Если запрос отправил не ты, '
            'проигнорируй письмо: пароль не изменится.'
        ),
    },
    'en': {
        'verify_subject': 'Confirm your email for AI Support',
        'verify_body': (
            'Hi {username}!\n\n'
            'To confirm your email, open this link:\n{link}\n\n'
            'The link is valid for 24 hours. If you did not sign up for AI Support, '
            'just ignore this message.'
        ),
        'reset_subject': 'Reset your AI Support password',
        'reset_body': (
            'Hi {username}!\n\n'
            'We received a request to reset your password. To choose a new password, open this link:\n{link}\n\n'
            'The link is valid for 1 hour and works only once. If you did not make this request, '
            'ignore this message: your password will not change.'
        ),
    },
    'ky': {
        'verify_subject': 'AI Support үчүн почтаңды тастыкта',
        'verify_body': (
            'Салам, {username}!\n\n'
            'Почтаңды тастыктоо үчүн шилтемени ач:\n{link}\n\n'
            'Шилтеме 24 саат иштейт. Эгер AI Support сайтына катталбасаң, '
            'бул катты эске албай кой.'
        ),
        'reset_subject': 'AI Support сыр сөзүн калыбына келтирүү',
        'reset_body': (
            'Салам, {username}!\n\n'
            'Сыр сөздү калыбына келтирүү өтүнүчү келди. Жаңы сыр сөз коюу үчүн шилтемени ач:\n{link}\n\n'
            'Шилтеме 1 саат иштейт жана бир жолу гана колдонулат. Өтүнүчтү сен жөнөтпөсөң, '
            'катты эске албай кой: сыр сөз өзгөрбөйт.'
        ),
    },
}


def _send(profile, subject_key, body_key, link):
    texts = TEXTS.get(profile.language_id) or TEXTS['en']
    send_mail(
        subject=texts[subject_key],
        message=texts[body_key].format(username=profile.user.username, link=link),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[profile.email],
        fail_silently=False,
    )


def send_verification_email(user):
    profile = user.profile
    token = make_verification_token(user, profile.email)
    link = f'{settings.SITE_URL}/?verify={quote(token, safe="")}'
    _send(profile, 'verify_subject', 'verify_body', link)


def send_reset_email(user):
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = reset_token_generator.make_token(user)
    link = f'{settings.SITE_URL}/?reset={uid}.{token}'
    _send(user.profile, 'reset_subject', 'reset_body', link)