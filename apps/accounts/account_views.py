import logging

from django.db import transaction
from django.utils import timezone
from rest_framework.authtoken.models import Token
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.chat.models import Conversation

from .account_serializers import (
    AccountUpdateSerializer,
    ChangeEmailSerializer,
    ChangePasswordSerializer,
    DeleteAccountSerializer,
)
from .emails import send_verification_email
from .models import UserProfile, UserSettings
from .throttles import ExportThrottle, SensitiveActionThrottle
from .user_settings import effective_settings
from .views import account_data

logger = logging.getLogger(__name__)


def get_or_create_profile(user):
    try:
        return user.profile
    except UserProfile.DoesNotExist:
        return UserProfile.objects.create(user=user)


def build_export(user):
    profile = getattr(user, 'profile', None)
    record = UserSettings.objects.filter(user=user).first()

    conversations = []
    queryset = Conversation.objects.filter(user=user).order_by('id').prefetch_related('messages')
    for conversation in queryset:
        messages = sorted(conversation.messages.all(), key=lambda message: message.id)
        conversations.append({
            'id': conversation.id,
            'title': conversation.title,
            'created_at': conversation.created_at.isoformat(),
            'summary': conversation.summary,
            'messages': [
                {
                    'role': message.role,
                    'content': message.content,
                    'created_at': message.created_at.isoformat(),
                }
                for message in messages
            ],
        })

    return {
        'exported_at': timezone.now().isoformat(),
        'account': {
            **account_data(user),
            'created_at': profile.created_at.isoformat() if profile else None,
        },
        'settings': effective_settings(record.data if record else {}),
        'conversations': conversations,
    }


class AccountView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(account_data(request.user))

    def patch(self, request):
        serializer = AccountUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        profile = get_or_create_profile(request.user)
        changed = []
        for field in ('country', 'language'):
            if field in serializer.validated_data:
                setattr(profile, field, serializer.validated_data[field])
                changed.append(field)
        if changed:
            profile.save(update_fields=changed)
        return Response(account_data(request.user))


class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [SensitiveActionThrottle]

    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)

        user = request.user
        user.set_password(serializer.validated_data['new_password'])
        user.save(update_fields=['password'])

        Token.objects.filter(user=user).delete()
        token = Token.objects.create(user=user)
        return Response({'token': token.key})


class ChangeEmailView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [SensitiveActionThrottle]

    def post(self, request):
        serializer = ChangeEmailSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data['email']

        profile = get_or_create_profile(request.user)
        profile.email = email
        profile.email_verified = False
        profile.save(update_fields=['email', 'email_verified'])

        email_sent = True
        try:
            send_verification_email(request.user)
        except Exception:
            logger.exception('Failed to send verification email')
            email_sent = False

        return Response({
            'email': profile.email,
            'email_verified': False,
            'email_sent': email_sent,
        })


class ExportDataView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [ExportThrottle]

    def get(self, request):
        response = Response(build_export(request.user))
        response['Content-Disposition'] = 'attachment; filename="ai-support-export.json"'
        return response


class LogoutAllView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        Token.objects.filter(user=request.user).delete()
        return Response(status=204)


class DeleteAccountView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [SensitiveActionThrottle]

    def post(self, request):
        serializer = DeleteAccountSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)

        user = request.user
        if user.is_staff or user.is_superuser:
            return Response(
                {'error': 'Administrator accounts cannot be deleted here.', 'code': 'staff_account'},
                status=403,
            )

        with transaction.atomic():
            user.delete()
        return Response(status=204)