from django.conf import settings
from django.db import models

class Language(models.Model):
    code = models.CharField(max_length=5, primary_key=True)
    name = models.CharField(max_length=50)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f'{self.name} ({self.code})'


class Country(models.Model):
    code = models.CharField(max_length=2, primary_key=True)
    name = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name_plural = 'countries'
        ordering = ['name']

    def __str__(self):
        return f'{self.name} ({self.code})'


class UserProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='profile',
    )
    country = models.ForeignKey(
        Country, null=True, blank=True,
        on_delete=models.PROTECT, related_name='profiles',
    )
    language = models.ForeignKey(
        Language, null=True, blank=True,
        on_delete=models.PROTECT, related_name='profiles',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.user.username}'