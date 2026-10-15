from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.db import transaction
from rest_framework import serializers

from .models import Country, Language, UserProfile

User = get_user_model()


class RegisterSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    password = serializers.CharField(
        write_only=True,
        min_length=8,
        style={'input_type': 'password'},
    )
    country = serializers.CharField(max_length=2)
    language = serializers.CharField(max_length=5)

    def validate_username(self, value):
        if User.objects.filter(username__iexact=value).exists():
            raise serializers.ValidationError('This username is already taken.')
        return value

    def validate_country(self, value):
        try:
            return Country.objects.get(code=value.upper(), is_active=True)
        except Country.DoesNotExist:
            raise serializers.ValidationError('Unknown or unsupported country code.')

    def validate_language(self, value):
        try:
            return Language.objects.get(code=value.lower(), is_active=True)
        except Language.DoesNotExist:
            raise serializers.ValidationError('Unknown or unsupported language code.')

    def validate(self, attrs):
        validate_password(attrs['password'], user=User(username=attrs['username']))
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
            )
        return user