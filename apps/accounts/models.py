from django.conf import settings
from django.db import models

from .countries import COUNTRY_CHOICES


class UserProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='profile',
    )
    # Код страны по ISO 3166-1. Допустимые значения задаёт countries.py.
    country = models.CharField(
        max_length=2,
        choices=COUNTRY_CHOICES,
        blank=True,
        default='',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.user.username} ({self.country or "страна не указана"})'