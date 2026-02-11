"""
Django admin configuration for webhook models.
"""

from django.contrib import admin
from .models import WebhookLog


@admin.register(WebhookLog)
class WebhookLogAdmin(admin.ModelAdmin):
    list_display = ['source', 'clinic', 'endpoint', 'status', 'created_at', 'processed_at']
    list_filter = ['source', 'status', 'clinic']
    search_fields = ['endpoint', 'error_message']
    readonly_fields = ['created_at', 'processed_at', 'headers_json', 'body_json']
    date_hierarchy = 'created_at'

    def has_add_permission(self, request):
        return False  # Webhooks are created by external services

    def has_change_permission(self, request, obj=None):
        return False  # Webhook logs are immutable
