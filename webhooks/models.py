"""
Webhook models for logging incoming webhooks.
"""

from django.db import models
from core.models import Clinic


class WebhookLog(models.Model):
    """
    Log of all incoming webhooks for debugging and audit.
    """
    SOURCE_CHOICES = [
        ('twilio', 'Twilio'),
        ('google', 'Google'),
        ('meta', 'Meta'),
        ('cliniko', 'Cliniko'),
        ('other', 'Other'),
    ]

    STATUS_CHOICES = [
        ('received', 'Received'),
        ('processed', 'Processed'),
        ('failed', 'Failed'),
        ('invalid', 'Invalid Signature'),
    ]

    clinic = models.ForeignKey(
        Clinic,
        on_delete=models.CASCADE,
        related_name='webhook_logs',
        null=True, blank=True
    )

    source = models.CharField(max_length=50, choices=SOURCE_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='received')

    # Request data
    endpoint = models.CharField(max_length=255)
    method = models.CharField(max_length=10, default='POST')
    headers_json = models.JSONField(default=dict)
    body_json = models.JSONField(default=dict)

    # Processing
    processed_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True)

    # Tracking
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['source', 'status', 'created_at']),
        ]

    def __str__(self):
        return f"{self.source} webhook at {self.created_at}"
