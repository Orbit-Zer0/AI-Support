from django.core.validators import RegexValidator
from django.db import models

from apps.accounts.models import Country, Language


class CrisisResource(models.Model):
    """Один номер помощи в конкретной стране. Номер хранится один раз,
    переводятся только описания (CrisisResourceText), чтобы цифры
    не могли разойтись между языками."""

    class Kind(models.TextChoices):
        HOTLINE = 'hotline', 'Crisis / helpline'
        EMERGENCY = 'emergency', 'Emergency services'
        AMBULANCE = 'ambulance', 'Ambulance'

    country = models.ForeignKey(
        Country, on_delete=models.PROTECT, related_name='crisis_resources'
    )
    phone = models.CharField(
        max_length=32,
        validators=[
            RegexValidator(
                r'^[+\d][\d\s\-()]{1,30}$',
                'Only digits, spaces, dashes, parentheses; may start with +.',
            )
        ],
    )
    kind = models.CharField(max_length=20, choices=Kind.choices)
    priority = models.PositiveSmallIntegerField(
        default=100, help_text='Lower number is shown first.'
    )
    is_active = models.BooleanField(default=True)
    source_url = models.URLField(
        blank=True, help_text='Official source where this number was checked.'
    )
    verified_at = models.DateField(
        null=True, blank=True, help_text='Date the number was last checked.'
    )

    class Meta:
        ordering = ['country', 'priority']

    def __str__(self):
        return f'{self.country_id} {self.phone} ({self.get_kind_display()})'


class CrisisResourceText(models.Model):
    resource = models.ForeignKey(
        CrisisResource, on_delete=models.CASCADE, related_name='texts'
    )
    language = models.ForeignKey(Language, on_delete=models.PROTECT)
    title = models.CharField(max_length=120)
    description = models.CharField(max_length=300, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['resource', 'language'], name='uniq_resource_language'
            )
        ]

    def __str__(self):
        return f'{self.resource.phone} [{self.language_id}] {self.title}'