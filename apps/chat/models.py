from django.conf import settings
from django.db import models
from django.utils import timezone


class Conversation(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='conversations',
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(default=timezone.now)
    title = models.CharField(max_length=80, blank=True, default='')
    summary = models.TextField(blank=True, default='')
    summarized_until = models.PositiveBigIntegerField(default=0)

    def __str__(self):
        return f"Conversation {self.id}"


class Message(models.Model):
    ROLE_CHOICES = [
        ('user', 'User'),
        ('model', 'Model'),
    ]
    conversation = models.ForeignKey(
        Conversation, on_delete=models.CASCADE, related_name='messages'
    )
    role = models.CharField(max_length=10, choices=ROLE_CHOICES)
    content = models.TextField()
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['id']