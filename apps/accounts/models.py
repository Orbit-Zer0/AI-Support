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
    email = models.EmailField(blank=True, default='')
    email_verified = models.BooleanField(default=False)
    avatar = models.ImageField(upload_to='avatars/', blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['email'],
                condition=models.Q(email_verified=True),
                name='unique_verified_email',
            ),
        ]

    def save(self, *args, **kwargs):
        self.email = (self.email or '').strip().lower()
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.user.username}'


class UserSettings(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='ui_settings',
    )
    data = models.JSONField(default=dict, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'Settings of {self.user.username}'