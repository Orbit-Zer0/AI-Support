import logging

from django.contrib.auth.models import update_last_login
from django.core.cache import cache
from django.db import IntegrityError, transaction
from rest_framework import serializers
from rest_framework.authtoken.models import Token
from rest_framework.exceptions import ErrorDetail
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .emails import send_reset_email, send_verification_email
from .models import Country, Language, UserProfile, UserSettings
from .serializers import (
    ForgotPasswordSerializer,
    LoginSerializer,
    RegisterSerializer,
    ResetPasswordSerializer,
)
from .throttles import AuthThrottle, EmailResendThrottle, SettingsThrottle
from .tokens import read_verification_token
from .user_settings import apply_patch, effective_settings

logger = logging.getLogger(__name__)

FORGOT_COOLDOWN_SECONDS = 60


def account_data(user):
    profile = getattr(user, 'profile', None)
    avatar_url = profile.avatar.url if profile and profile.avatar else None
    return {
        'username': user.username,
        'email': profile.email if profile else '',
        'email_verified': bool(profile and profile.email_verified),
        'country': profile.country_id if profile else None,
        'language': profile.language_id if profile else None,
        'avatar_url': avatar_url,
    }


def _invalid_token_error():
    return serializers.ValidationError({
        'token': [ErrorDetail('This link is invalid or has expired.', code='invalid_token')]
    })


def _email_taken_error():
    return serializers.ValidationError({
        'email': [ErrorDetail('This email is already used by another account.', code='email_taken')]
    })


class RegisterView(APIView):
    authentication_classes = []
    throttle_classes = [AuthThrottle]
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        try:
            send_verification_email(user)
        except Exception:
            logger.exception('Failed to send verification email')

        token, _ = Token.objects.get_or_create(user=user)
        return Response({'token': token.key, **account_data(user)}, status=201)


class LoginView(APIView):
    authentication_classes = []
    throttle_classes = [AuthThrottle]
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']
        update_last_login(None, user)
        token, _ = Token.objects.get_or_create(user=user)
        return Response({'token': token.key, **account_data(user)})

class VerifyEmailView(APIView):
    authentication_classes = []
    throttle_classes = [AuthThrottle]
    permission_classes = [AllowAny]

    def post(self, request):
        token = request.data.get('token')
        data = read_verification_token(token) if isinstance(token, str) else None
        profile = UserProfile.objects.filter(user_id=data['u']).first() if data else None
        if profile is None or not profile.email or profile.email != data['e']:
            raise _invalid_token_error()

        if profile.email_verified:
            return Response({'email_verified': True, 'email': profile.email})

        try:
            with transaction.atomic():
                taken = (
                    UserProfile.objects
                    .filter(email=profile.email, email_verified=True)
                    .exclude(pk=profile.pk)
                    .exists()
                )
                if taken:
                    raise _email_taken_error()
                (
                    UserProfile.objects
                    .filter(email=profile.email, email_verified=False)
                    .exclude(pk=profile.pk)
                    .update(email='')
                )
                profile.email_verified = True
                profile.save(update_fields=['email_verified'])
        except IntegrityError:
            raise _email_taken_error()

        return Response({'email_verified': True, 'email': profile.email})


class ResendVerificationView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [EmailResendThrottle]

    def post(self, request):
        profile = getattr(request.user, 'profile', None)
        if profile is None or not profile.email:
            return Response(
                {'error': 'No email is linked to this account.', 'code': 'no_email'},
                status=400,
            )
        if profile.email_verified:
            return Response({'email_verified': True})

        try:
            send_verification_email(request.user)
        except Exception:
            logger.exception('Failed to send verification email')
            return Response(
                {'error': 'Could not send the email.', 'code': 'email_failed'},
                status=503,
            )
        return Response({'detail': 'sent'})


class ForgotPasswordView(APIView):
    authentication_classes = []
    throttle_classes = [AuthThrottle]
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = ForgotPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data['email']

        profile = (
            UserProfile.objects.select_related('user')
            .filter(email=email, email_verified=True, user__is_active=True)
            .first()
        )
        if profile and cache.add(f'forgot:{email}', 1, FORGOT_COOLDOWN_SECONDS):
            try:
                send_reset_email(profile.user)
            except Exception:
                logger.exception('Failed to send password reset email')

        return Response({'detail': 'sent'})


class ResetPasswordView(APIView):
    authentication_classes = []
    throttle_classes = [AuthThrottle]
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = ResetPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']

        user.set_password(serializer.validated_data['password'])
        user.save(update_fields=['password'])
        Token.objects.filter(user=user).delete()
        return Response({'detail': 'ok'})


class CountryListView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request):
        countries = Country.objects.filter(is_active=True).values('code', 'name')
        return Response(list(countries))


class LanguageListView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request):
        languages = Language.objects.filter(is_active=True).order_by('code').values('code', 'name')
        return Response(list(languages))


class UserSettingsView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [SettingsThrottle]

    def get(self, request):
        record = UserSettings.objects.filter(user=request.user).first()
        return Response(effective_settings(record.data if record else {}))

    def patch(self, request):
        record, _ = UserSettings.objects.get_or_create(user=request.user)
        record.data = apply_patch(record.data, request.data)
        record.save(update_fields=['data', 'updated_at'])
        return Response(effective_settings(record.data))