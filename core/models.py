"""
Core models for Pracxcel Tool.

Patient, Appointment, and Invoice are synced from Cliniko (PMS is source of truth).
Attribution and AuditLog are our intelligence layer.
"""

from django.db import models
from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType


class Clinic(models.Model):
    """
    A clinic that uses Pracxcel Tool.
    Multi-clinic support is post-MVP but we design for it now.
    """
    name = models.CharField(max_length=255)
    cliniko_api_key = models.CharField(max_length=255, blank=True)
    cliniko_shard = models.CharField(max_length=50, default='api')

    # Sync tracking
    last_cliniko_sync = models.DateTimeField(null=True, blank=True)
    last_sync_cursor = models.CharField(max_length=255, blank=True)

    # Settings
    timezone = models.CharField(max_length=50, default='UTC')
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class Patient(models.Model):
    """
    Patient record synced from Cliniko.
    Never duplicate - Cliniko is source of truth.
    """
    clinic = models.ForeignKey(Clinic, on_delete=models.CASCADE, related_name='patients')
    cliniko_id = models.CharField(max_length=100, db_index=True)

    # Basic info
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=50, blank=True, db_index=True)
    date_of_birth = models.DateField(null=True, blank=True)

    # Consent flags - HIPAA compliance
    sms_consent = models.BooleanField(default=False)
    email_consent = models.BooleanField(default=False)
    call_recording_consent = models.BooleanField(default=False)

    # Tracking
    first_appointment_date = models.DateField(null=True, blank=True)
    last_appointment_date = models.DateField(null=True, blank=True)
    first_paid_invoice_date = models.DateField(null=True, blank=True)

    # Sync metadata
    cliniko_created_at = models.DateTimeField(null=True, blank=True)
    cliniko_updated_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['clinic', 'cliniko_id']
        ordering = ['last_name', 'first_name']

    def __str__(self):
        return f"{self.first_name} {self.last_name}"

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"


class Appointment(models.Model):
    """
    Appointment record synced from Cliniko.
    """
    APPOINTMENT_STATUS_CHOICES = [
        ('scheduled', 'Scheduled'),
        ('confirmed', 'Confirmed'),
        ('arrived', 'Arrived'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
        ('no_show', 'No Show'),
    ]

    clinic = models.ForeignKey(Clinic, on_delete=models.CASCADE, related_name='appointments')
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='appointments')
    cliniko_id = models.CharField(max_length=100, db_index=True)

    # Appointment details
    scheduled_at = models.DateTimeField(db_index=True)
    duration_minutes = models.PositiveIntegerField(default=30)
    status = models.CharField(max_length=20, choices=APPOINTMENT_STATUS_CHOICES, default='scheduled')
    appointment_type = models.CharField(max_length=100, blank=True)
    practitioner_name = models.CharField(max_length=100, blank=True)

    # Notes (be careful with PHI)
    notes = models.TextField(blank=True)

    # Sync metadata
    cliniko_created_at = models.DateTimeField(null=True, blank=True)
    cliniko_updated_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['clinic', 'cliniko_id']
        ordering = ['-scheduled_at']

    def __str__(self):
        return f"{self.patient} - {self.scheduled_at.strftime('%Y-%m-%d %H:%M')}"


class Invoice(models.Model):
    """
    Invoice record synced from Cliniko.
    Used for revenue attribution and calculating cost-per-new-patient.
    """
    INVOICE_STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('issued', 'Issued'),
        ('paid', 'Paid'),
        ('partially_paid', 'Partially Paid'),
        ('voided', 'Voided'),
    ]

    clinic = models.ForeignKey(Clinic, on_delete=models.CASCADE, related_name='invoices')
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='invoices')
    cliniko_id = models.CharField(max_length=100, db_index=True)

    # Invoice details
    invoice_number = models.CharField(max_length=50, blank=True)
    status = models.CharField(max_length=20, choices=INVOICE_STATUS_CHOICES, default='draft')
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    paid_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    # Dates
    issued_at = models.DateTimeField(null=True, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True, db_index=True)

    # Sync metadata
    cliniko_created_at = models.DateTimeField(null=True, blank=True)
    cliniko_updated_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['clinic', 'cliniko_id']
        ordering = ['-issued_at']

    def __str__(self):
        return f"Invoice {self.invoice_number} - {self.patient}"

    @property
    def is_paid(self):
        return self.status == 'paid'


class Attribution(models.Model):
    """
    Attribution linking a patient's first paid invoice to marketing source.

    Attribution is one-to-one with Patient.
    Uses polymorphic relationship to CallEvent or MarketingTouch.
    """
    ATTRIBUTION_TYPE_CHOICES = [
        ('call', 'Phone Call'),
        ('marketing_touch', 'Marketing Touch'),
        ('manual', 'Manual Entry'),
        ('unknown', 'Unknown'),
    ]

    ATTRIBUTION_STATUS_CHOICES = [
        ('auto', 'Auto-attributed'),
        ('manual', 'Manually Overridden'),
        ('pending', 'Pending Review'),
    ]

    patient = models.OneToOneField(Patient, on_delete=models.CASCADE, related_name='attribution')
    clinic = models.ForeignKey(Clinic, on_delete=models.CASCADE, related_name='attributions')

    # Attribution type and status
    attribution_type = models.CharField(max_length=20, choices=ATTRIBUTION_TYPE_CHOICES)
    status = models.CharField(max_length=20, choices=ATTRIBUTION_STATUS_CHOICES, default='auto')

    # Polymorphic FK to the attributed source (CallEvent or MarketingTouch)
    content_type = models.ForeignKey(ContentType, on_delete=models.SET_NULL, null=True, blank=True)
    object_id = models.PositiveIntegerField(null=True, blank=True)
    attributed_source = GenericForeignKey('content_type', 'object_id')

    # Campaign info (denormalized for easier queries)
    campaign_name = models.CharField(max_length=255, blank=True)
    campaign_source = models.CharField(max_length=100, blank=True)  # google, meta, organic
    campaign_medium = models.CharField(max_length=100, blank=True)  # cpc, social, referral

    # Evidence for audit trail
    evidence_json = models.JSONField(default=dict)

    # Revenue from first invoice
    first_invoice_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    first_invoice_date = models.DateField(null=True, blank=True)

    # Manual override tracking
    overridden_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='attribution_overrides'
    )
    override_reason = models.TextField(blank=True)
    overridden_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Attribution: {self.patient} -> {self.attribution_type}"


class AuditLog(models.Model):
    """
    Immutable audit trail for all patient data access.
    HIPAA compliance requirement.
    """
    ACTION_CHOICES = [
        ('read', 'Read'),
        ('create', 'Create'),
        ('update', 'Update'),
        ('delete', 'Delete'),
        ('export', 'Export'),
    ]

    # Who
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='audit_logs'
    )
    clinic = models.ForeignKey(Clinic, on_delete=models.CASCADE, related_name='audit_logs')

    # What
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    object_repr = models.CharField(max_length=255)

    # Details
    changes_json = models.JSONField(default=dict)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)

    # When
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-timestamp']
        # Make it append-only in application code (no update/delete methods)

    def __str__(self):
        return f"{self.user} {self.action} {self.object_repr} at {self.timestamp}"

    def save(self, *args, **kwargs):
        # Append-only: prevent updates
        if self.pk:
            raise ValueError("AuditLog entries cannot be modified")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError("AuditLog entries cannot be deleted")
