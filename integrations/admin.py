"""
Django admin configuration for integration models.
"""

from django.contrib import admin
from .models import Integration, CallEvent, MarketingTouch, Campaign, CampaignDailyStats


@admin.register(Integration)
class IntegrationAdmin(admin.ModelAdmin):
    list_display = ['clinic', 'integration_type', 'is_active', 'last_sync_at']
    list_filter = ['integration_type', 'is_active']
    search_fields = ['clinic__name']
    readonly_fields = ['created_at', 'updated_at', 'last_sync_at']


@admin.register(CallEvent)
class CallEventAdmin(admin.ModelAdmin):
    list_display = ['call_sid', 'clinic', 'caller_phone', 'direction', 'status',
                    'duration_seconds', 'timestamp', 'is_processed']
    list_filter = ['clinic', 'direction', 'status', 'is_processed', 'resulted_in_appointment']
    search_fields = ['call_sid', 'caller_phone', 'called_phone', 'campaign_name']
    readonly_fields = ['call_sid', 'created_at', 'updated_at']
    date_hierarchy = 'timestamp'


@admin.register(MarketingTouch)
class MarketingTouchAdmin(admin.ModelAdmin):
    list_display = ['clinic', 'utm_source', 'utm_medium', 'utm_campaign', 'email', 'timestamp']
    list_filter = ['clinic', 'utm_source', 'utm_medium', 'source']
    search_fields = ['email', 'session_id', 'utm_campaign', 'gclid', 'fbclid']
    readonly_fields = ['created_at']
    date_hierarchy = 'timestamp'


@admin.register(Campaign)
class CampaignAdmin(admin.ModelAdmin):
    list_display = ['name', 'clinic', 'source', 'total_spend', 'total_clicks',
                    'total_conversions', 'is_active', 'last_sync_at']
    list_filter = ['clinic', 'source', 'is_active']
    search_fields = ['name', 'external_id']
    readonly_fields = ['created_at', 'updated_at', 'last_sync_at']


@admin.register(CampaignDailyStats)
class CampaignDailyStatsAdmin(admin.ModelAdmin):
    list_display = ['campaign', 'date', 'spend', 'impressions', 'clicks', 'conversions']
    list_filter = ['campaign__clinic', 'campaign__source']
    search_fields = ['campaign__name']
    date_hierarchy = 'date'
    readonly_fields = ['created_at', 'updated_at']
