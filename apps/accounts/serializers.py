from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import check_password, make_password
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode
from rest_framework import serializers
from rest_framework.exceptions import ErrorDetail

from .models import Country, Language, UserProfile
from .tokens import reset_token_generator

User = get_user_model()

_DUMMY_HASH = make_password('not-a-real-password')


def validate_new_password(password, user=None):
    try:
        validate_password(password, user=user)
    except DjangoValidationError as exc:
        raise serializers.ValidationError({
            'password': [
                ErrorDetail(message, code=error.code)
                for message, error in zip(exc.messages, exc.error_list)
            ]
        })


def find_user_for_login(login):
    login = (login or '').strip()
    if '@' in login:
        profile = (
            UserProfile.objects.select_related('user')
            .filter(email=login.lower(), email_verified=True)
            .first()
        )
        if profile:
            return profile.user
    return User.objects.filter(username__iexact=login).first()


class RegisterSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    email = serializers.EmailField(max_length=254)
    password = serializers.CharField(
        write_only=True,
        min_length=8,
        style={'input_type': 'password'},
    )
    country = serializers.CharField(max_length=2)
    language = serializers.CharField(max_length=5)

    def validate_username(self, value):
        if '@' in value:
            raise serializers.ValidationError(
                'The username cannot contain the @ character.', code='username_no_at'
            )
        if User.objects.filter(username__iexact=value).exists():
            raise serializers.ValidationError(
                'This username is already taken.', code='username_taken'
            )
        return value

    def validate_email(self, value):
        email = value.strip().lower()
        if UserProfile.objects.filter(email=email, email_verified=True).exists():
            raise serializers.ValidationError(
                'This email is already used by another account.', code='email_taken'
            )
        return email

    def validate_country(self, value):
        try:
            return Country.objects.get(code=value.upper(), is_active=True)
        except Country.DoesNotExist:
            raise serializers.ValidationError(
                'Unknown or unsupported country code.', code='unknown_country'
            )

    def validate_language(self, value):
        try:
            return Language.objects.get(code=value.lower(), is_active=True)
        except Language.DoesNotExist:
            raise serializers.ValidationError(
                'Unknown or unsupported language code.', code='unknown_language'
            )

    def validate(self, attrs):
        validate_new_password(attrs['password'], user=User(username=attrs['username']))
        return attrs

    def create(self, validated_data):
        with transaction.atomic():
            user = User.objects.create_user(
                username=validated_data['username'],
                password=validated_data['password'],
            )
            UserProfile.objects.create(
                user=user,
                country=validated_data['country'],
                language=validated_data['language'],
                email=validated_data['email'],
            )
        return user


class LoginSerializer(serializers.Serializer):
    login = serializers.CharField(max_length=254)
    password = serializers.CharField(write_only=True, style={'input_type': 'password'})

    def validate(self, attrs):
        user = find_user_for_login(attrs['login'])
        if user is None:
            check_password(attrs['password'], _DUMMY_HASH)
        elif user.is_active and user.check_password(attrs['password']):
            attrs['user'] = user
            return attrs
        raise serializers.ValidationError(
            'Incorrect login details.', code='authorization'
        )


class ForgotPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField(max_length=254)

    def validate_email(self, value):
        return value.strip().lower()


class ResetPasswordSerializer(serializers.Serializer):
    uid = serializers.CharField(max_length=64)
    token = serializers.CharField(max_length=128)
    password = serializers.CharField(
        write_only=True,
        min_length=8,
        style={'input_type': 'password'},
    )

    @staticmethod
    def _user_from_uid(uid):
        try:
            pk = force_str(urlsafe_base64_decode(uid))
            return User.objects.filter(pk=pk, is_active=True).first()
        except (TypeError, ValueError, OverflowError, UnicodeDecodeError):
            return None

    def validate(self, attrs):
        user = self._user_from_uid(attrs['uid'])
        if user is None or not reset_token_generator.check_token(user, attrs['token']):
            raise serializers.ValidationError({
                'token': [ErrorDetail('This link is invalid or has expired.', code='invalid_token')]
            })
        validate_new_password(attrs['password'], user=user)
        attrs['user'] = user
        return attrs