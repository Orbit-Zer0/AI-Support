import logging

from django.db import transaction
from django.http import HttpResponse
from rest_framework.authtoken.models import Token
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .account_serializers import (
    AccountUpdateSerializer,
    ChangeEmailSerializer,
    ChangePasswordSerializer,
    DeleteAccountSerializer,
)
from .data_transfer import (
    MAX_IMPORT_BYTES,
    ImportDataError,
    build_export,
    import_conversations,
    render_readable_export,
)
from .emails import send_verification_email
from .models import UserProfile
from .throttles import ExportThrottle, ImportThrottle, SensitiveActionThrottle
from .views import account_data

logger = logging.getLogger(__name__)


def get_or_create_profile(user):
    try:
        return user.profile
    except UserProfile.DoesNotExist:
        return UserProfile.objects.create(user=user)


def _content_length(request):
    try:
        return int(request.META.get('CONTENT_LENGTH') or 0)
    except (TypeError, ValueError):
        return 0


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


class ExportReadableView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [ExportThrottle]

    def get(self, request):
        response = HttpResponse(
            render_readable_export(request.user),
            content_type='text/html; charset=utf-8',
        )
        response['Content-Disposition'] = 'attachment; filename="ai-support-chats.html"'
        response['X-Content-Type-Options'] = 'nosniff'
        return response


class ImportDataView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [ImportThrottle]

    def post(self, request):
        if _content_length(request) > MAX_IMPORT_BYTES:
            return Response(
                {'error': 'The file is too large.', 'code': 'import_too_large'}, status=413
            )

        try:
            payload = request.data
        except RecursionError:
            return Response(
                {'error': 'Invalid import file.', 'code': 'import_invalid'}, status=400
            )

        try:
            result = import_conversations(request.user, payload)
        except ImportDataError as exc:
            return Response({'error': 'Invalid import file.', 'code': exc.code}, status=400)
        return Response(result)


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