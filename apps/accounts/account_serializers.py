from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers
from rest_framework.exceptions import ErrorDetail

from .models import Country, Language, UserProfile


def new_password_errors(password, user, field):
    try:
        validate_password(password, user=user)
    except DjangoValidationError as exc:
        raise serializers.ValidationError({
            field: [
                ErrorDetail(message, code=error.code)
                for message, error in zip(exc.messages, exc.error_list)
            ]
        })


class CurrentPasswordMixin:
    def validate_current_password(self, value):
        if not self.context['request'].user.check_password(value):
            raise serializers.ValidationError(
                'The current password is incorrect.', code='wrong_password'
            )
        return value


class ChangePasswordSerializer(CurrentPasswordMixin, serializers.Serializer):
    current_password = serializers.CharField(write_only=True, style={'input_type': 'password'})
    new_password = serializers.CharField(
        write_only=True, min_length=8, style={'input_type': 'password'}
    )

    def validate(self, attrs):
        user = self.context['request'].user
        if user.check_password(attrs['new_password']):
            raise serializers.ValidationError({
                'new_password': [
                    ErrorDetail('The new password must be different.', code='same_password')
                ]
            })
        new_password_errors(attrs['new_password'], user, 'new_password')
        return attrs


class ChangeEmailSerializer(CurrentPasswordMixin, serializers.Serializer):
    email = serializers.EmailField(max_length=254)
    current_password = serializers.CharField(write_only=True, style={'input_type': 'password'})

    def validate_email(self, value):
        email = value.strip().lower()
        user = self.context['request'].user

        taken = (
            UserProfile.objects.filter(email=email, email_verified=True).exclude(user=user)
        )
        if taken.exists():
            raise serializers.ValidationError(
                'This email is already used by another account.', code='email_taken'
            )
        if UserProfile.objects.filter(user=user, email=email, email_verified=True).exists():
            raise serializers.ValidationError(
                'This email is already confirmed in your account.', code='same_email'
            )
        return email


class AccountUpdateSerializer(serializers.Serializer):
    country = serializers.CharField(max_length=2, required=False)
    language = serializers.CharField(max_length=5, required=False)

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


class DeleteAccountSerializer(serializers.Serializer):
    password = serializers.CharField(write_only=True, style={'input_type': 'password'})

    def validate_password(self, value):
        if not self.context['request'].user.check_password(value):
            raise serializers.ValidationError(
                'The password is incorrect.', code='wrong_password'
            )
        return value