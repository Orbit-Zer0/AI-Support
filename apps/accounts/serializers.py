from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.db import transaction
from rest_framework import serializers

from .models import UserProfile

User = get_user_model()

ALLOWED_COUNTRIES = {
    'KG', 'KZ', 'RU', 'UZ', 'TJ', 'TM',
    'AZ', 'AM', 'GE', 'BY', 'MD', 'UA',
}


class RegisterSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    password = serializers.CharField(
        write_only=True,
        min_length=8,
        style={'input_type': 'password'},
    )
    country = serializers.CharField(max_length=2)

    def validate_username(self, value):
        if User.objects.filter(username__iexact=value).exists():
            raise serializers.ValidationError('Это имя уже занято.')
        return value

    def validate_country(self, value):
        code = value.upper()
        if code not in ALLOWED_COUNTRIES:
            raise serializers.ValidationError('Неизвестный код страны.')
        return code

    def validate(self, attrs):
        validate_password(attrs['password'], user=User(username=attrs['username']))
        return attrs

    def create(self, validated_data):
        with transaction.atomic():
            user = User.objects.create_user(
                username=validated_data['username'],
                password=validated_data['password'],
            )
            UserProfile.objects.create(user=user, country=validated_data['country'])
        return user