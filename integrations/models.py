"""
Integration models for external services.

CallEvent and MarketingTouch are the source data for Attribution.
Campaign aggregates spend data from Google Ads and Meta.
"""

from django.db import models
from django.conf import settings

from core.models import Clinic


class Integration(models.Model):
    """
    OAuth tokens and API credentials for third-party integrations.
    """
    INTEGRATION_TYPE_CHOICES = [
        ('google_ads', 'Google Ads'),
        ('google_analytics', 'Google Analytics 4'),
        ('meta_ads', 'Meta Ads'),
        ('twilio', 'Twilio'),
    ]

    clinic = models.ForeignKey(Clinic, on_delete=models.CASCADE, related_name='integrations')
    integration_type = models.CharField(max_length=50, choices=INTEGRATION_TYPE_CHOICES)

    # OAuth tokens (encrypted in production)
    access_token = models.TextField(blank=True)
    refresh_token = models.TextField(blank=True)
    token_expires_at = models.DateTimeField(null=True, blank=True)

    # Additional config (account IDs, etc.)
    config_json = models.JSONField(default=dict)

    # Status
    is_active = models.BooleanField(default=True)
    last_sync_at = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['clinic', 'integration_type']

    def __str__(self):
        return f"{self.clinic} - {self.get_integration_type_display()}"


class CallEvent(models.Model):
    """
    Call event from Twilio webhook.
    Used for attribution - matches caller phone to Patient.
    """
    CALL_STATUS_CHOICES = [
        ('ringing', 'Ringing'),
        ('in-progress', 'In Progress'),
        ('completed', 'Completed'),
        ('busy', 'Busy'),
        ('no-answer', 'No Answer'),
        ('failed', 'Failed'),
        ('canceled', 'Canceled'),
    ]

    CALL_DIRECTION_CHOICES = [
        ('inbound', 'Inbound'),
        ('outbound', 'Outbound'),
    ]

    clinic = models.ForeignKey(Clinic, on_delete=models.CASCADE, related_name='call_events')

    # Twilio identifiers
    call_sid = models.CharField(max_length=100, unique=True, db_index=True)
    parent_call_sid = models.CharField(max_length=100, blank=True)

    # Call details
    caller_phone = models.CharField(max_length=50, db_index=True)
    called_phone = models.CharField(max_length=50, db_index=True)
    direction = models.CharField(max_length=20, choices=CALL_DIRECTION_CHOICES, default='inbound')
    status = models.CharField(max_length=20, choices=CALL_STATUS_CHOICES, default='ringing')
    duration_seconds = models.PositiveIntegerField(default=0)

    # Timestamp
    timestamp = models.DateTimeField(db_index=True)
    answered_at = models.DateTimeField(null=True, blank=True)
    ended_at = models.DateTimeField(null=True, blank=True)

    # Campaign tracking (from tracking number mapping)
    campaign_id = models.CharField(max_length=100, blank=True, db_index=True)
    campaign_name = models.CharField(max_length=255, blank=True)
    tracking_number = models.CharField(max_length=50, blank=True)

    # Recording (requires consent)
    recording_url = models.URLField(blank=True)
    recording_duration = models.PositiveIntegerField(default=0)

    # Processing flags
    is_processed = models.BooleanField(default=False)
    resulted_in_appointment = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"Call {self.call_sid} from {self.caller_phone}"

    @property
    def is_missed(self):
        """A call is considered missed if duration < 30s and no appointment booked."""
        return self.duration_seconds < 30 and not self.resulted_in_appointment


class MarketingTouch(models.Model):
    """
    Marketing touch point from GA4 or direct UTM tracking.
    Represents a user interaction that can be attributed to a patient.
    """
    clinic = models.ForeignKey(Clinic, on_delete=models.CASCADE, related_name='marketing_touches')

    # Session/visitor identification
    session_id = models.CharField(max_length=255, blank=True, db_index=True)
    client_id = models.CharField(max_length=255, blank=True, db_index=True)
    email = models.EmailField(blank=True, db_index=True)

    # UTM parameters
    utm_source = models.CharField(max_length=100, blank=True, db_index=True)
    utm_medium = models.CharField(max_length=100, blank=True, db_index=True)
    utm_campaign = models.CharField(max_length=255, blank=True, db_index=True)
    utm_term = models.CharField(max_length=255, blank=True)
    utm_content = models.CharField(max_length=255, blank=True)

    # Click IDs
    gclid = models.CharField(max_length=255, blank=True, db_index=True)  # Google
    fbclid = models.CharField(max_length=255, blank=True, db_index=True)  # Meta/Facebook

    # Page interaction
    landing_page = models.URLField(blank=True)
    referrer = models.URLField(blank=True)

    # Timestamp
    timestamp = models.DateTimeField(db_index=True)

    # Source of this data
    source = models.CharField(max_length=50, default='ga4')  # ga4, form, manual

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"Touch: {self.utm_source}/{self.utm_medium} at {self.timestamp}"


class Campaign(models.Model):
    """
    Marketing campaign aggregating spend from Google Ads and Meta.
    Used for cost-per-new-patient calculations.
    """
    CAMPAIGN_SOURCE_CHOICES = [
        ('google_ads', 'Google Ads'),
        ('meta_ads', 'Meta Ads'),
        ('manual', 'Manual Entry'),
    ]

    clinic = models.ForeignKey(Clinic, on_delete=models.CASCADE, related_name='campaigns')

    # Campaign identification
    external_id = models.CharField(max_length=100, db_index=True)
    name = models.CharField(max_length=255)
    source = models.CharField(max_length=50, choices=CAMPAIGN_SOURCE_CHOICES)

    # Spend tracking (aggregated daily)
    total_spend = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_impressions = models.PositiveIntegerField(default=0)
    total_clicks = models.PositiveIntegerField(default=0)
    total_conversions = models.PositiveIntegerField(default=0)

    # Date range
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)

    # Status
    is_active = models.BooleanField(default=True)

    # Tracking phone number (for call attribution)
    tracking_phone = models.CharField(max_length=50, blank=True)

    last_sync_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['clinic', 'source', 'external_id']
        ordering = ['-start_date', 'name']

    def __str__(self):
        return f"{self.name} ({self.get_source_display()})"


class CampaignDailyStats(models.Model):
    """
    Daily spend and performance stats for a campaign.
    Enables time-series analysis and accurate cost attribution.
    """
    campaign = models.ForeignKey(Campaign, on_delete=models.CASCADE, related_name='daily_stats')
    date = models.DateField(db_index=True)

    spend = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    impressions = models.PositiveIntegerField(default=0)
    clicks = models.PositiveIntegerField(default=0)
    conversions = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['campaign', 'date']
        ordering = ['-date']

    def __str__(self):
        return f"{self.campaign.name} - {self.date}"
