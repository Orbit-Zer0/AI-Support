from rest_framework.authtoken.models import Token
from rest_framework.authtoken.views import ObtainAuthToken
from rest_framework.permissions import AllowAny
from rest_framework.renderers import BrowsableAPIRenderer, JSONRenderer
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from .models import Country, Language, UserSettings
from .throttles import AuthThrottle, SettingsThrottle
from .user_settings import apply_patch, effective_settings
from .serializers import RegisterSerializer


class RegisterView(APIView):
    authentication_classes = []
    throttle_classes = [AuthThrottle]
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        token, _ = Token.objects.get_or_create(user=user)
        return Response(
            {
                'token': token.key,
                'username': user.username,
                'country': user.profile.country_id,
                'language': user.profile.language_id,
            },
            status=201,
        )


class LoginView(ObtainAuthToken):
    authentication_classes = []
    throttle_classes = [AuthThrottle]
    renderer_classes = [JSONRenderer, BrowsableAPIRenderer]

    def post(self, request, *args, **kwargs):
        serializer = self.serializer_class(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']
        token, _ = Token.objects.get_or_create(user=user)
        profile = getattr(user, 'profile', None)
        return Response(
            {
                'token': token.key,
                'username': user.username,
                'country': profile.country_id if profile else None,
                'language': profile.language_id if profile else None,
            }
        )


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