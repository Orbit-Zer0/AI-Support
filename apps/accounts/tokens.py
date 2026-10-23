from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.core import signing

VERIFY_SALT = 'accounts.verify-email'
VERIFY_MAX_AGE = 24 * 60 * 60


def make_verification_token(user, email):
    return signing.dumps({'u': user.pk, 'e': email}, salt=VERIFY_SALT)


def read_verification_token(token):
    try:
        data = signing.loads(token, salt=VERIFY_SALT, max_age=VERIFY_MAX_AGE)
    except (signing.BadSignature, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    if not isinstance(data.get('u'), int) or not isinstance(data.get('e'), str):
        return None
    return data


class ResetTokenGenerator(PasswordResetTokenGenerator):

    def _make_hash_value(self, user, timestamp):
        profile = getattr(user, 'profile', None)
        email = profile.email if profile else ''
        return f'{super()._make_hash_value(user, timestamp)}{email}'


reset_token_generator = ResetTokenGenerator()