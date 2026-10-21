import logging

from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .fallback import get_fallback_text
from .services import get_crisis_contacts

logger = logging.getLogger(__name__)


class CrisisContactsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        profile = getattr(request.user, 'profile', None)
        country = profile.country_id if profile else None
        language = profile.language_id if profile else None
        try:
            contacts = get_crisis_contacts(country, language)
        except Exception:
            logger.exception('Failed to load crisis contacts')
            contacts = []
        return Response({'contacts': contacts, 'fallback': get_fallback_text(language)})