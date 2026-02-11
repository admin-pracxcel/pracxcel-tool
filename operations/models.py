"""
Operations models for actionable tasks.

Raw data becomes actionable tasks - this is the operations layer.
"""

from django.db import models
from django.conf import settings

from core.models import Clinic, Patient


class Task(models.Model):
    """
    Actionable task for staff to complete.

    Tasks are generated automatically by rules or created manually.
    """
    TASK_TYPE_CHOICES = [
        ('callback', 'Callback - Missed Call'),
        ('review_request', 'Request Review'),
        ('treatment_followup', 'Treatment Plan Follow-up'),
        ('recall', 'Recall Campaign'),
        ('custom', 'Custom Task'),
    ]

    TASK_PRIORITY_CHOICES = [
        (1, 'Urgent'),
        (2, 'High'),
        (3, 'Normal'),
        (4, 'Low'),
    ]

    TASK_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
        ('snoozed', 'Snoozed'),
    ]

    clinic = models.ForeignKey(Clinic, on_delete=models.CASCADE, related_name='tasks')
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='tasks')

    # Task details
    task_type = models.CharField(max_length=50, choices=TASK_TYPE_CHOICES)
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    priority = models.PositiveSmallIntegerField(choices=TASK_PRIORITY_CHOICES, default=3)
    status = models.CharField(max_length=20, choices=TASK_STATUS_CHOICES, default='pending')

    # Assignment
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='assigned_tasks'
    )

    # Timing
    due_at = models.DateTimeField(null=True, blank=True)
    snoozed_until = models.DateTimeField(null=True, blank=True)

    # Completion
    completed_at = models.DateTimeField(null=True, blank=True)
    completed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='completed_tasks'
    )
    completion_notes = models.TextField(blank=True)

    # Source tracking (what triggered this task)
    source_type = models.CharField(max_length=50, blank=True)  # e.g., 'call_event', 'appointment'
    source_id = models.PositiveIntegerField(null=True, blank=True)

    # Idempotency key to prevent duplicate tasks
    idempotency_key = models.CharField(max_length=255, unique=True, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['priority', '-created_at']
        indexes = [
            models.Index(fields=['clinic', 'status', 'priority']),
            models.Index(fields=['assigned_to', 'status']),
        ]

    def __str__(self):
        return f"{self.title} - {self.patient}"


class ReviewRequest(models.Model):
    """
    Request for a patient review after appointment.

    Sent 24 hours after appointment completion if patient consented.
    """
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('sent', 'Sent'),
        ('completed', 'Completed'),
        ('declined', 'Declined'),
        ('expired', 'Expired'),
    ]

    CHANNEL_CHOICES = [
        ('sms', 'SMS'),
        ('email', 'Email'),
    ]

    clinic = models.ForeignKey(Clinic, on_delete=models.CASCADE, related_name='review_requests')
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='review_requests')
    appointment = models.ForeignKey(
        'core.Appointment',
        on_delete=models.CASCADE,
        related_name='review_requests'
    )

    # Request details
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    channel = models.CharField(max_length=20, choices=CHANNEL_CHOICES, default='sms')

    # Timing
    scheduled_at = models.DateTimeField()
    sent_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    # Response tracking
    review_platform = models.CharField(max_length=50, blank=True)  # e.g., 'google', 'facebook'
    review_rating = models.PositiveSmallIntegerField(null=True, blank=True)

    # Idempotency
    idempotency_key = models.CharField(max_length=255, unique=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-scheduled_at']

    def __str__(self):
        return f"Review request for {self.patient} - {self.status}"


class TreatmentPlan(models.Model):
    """
    Treatment plan sent to patient for approval/scheduling.

    Follow-up tasks are generated if no response after 7 days.
    """
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('sent', 'Sent'),
        ('viewed', 'Viewed'),
        ('accepted', 'Accepted'),
        ('declined', 'Declined'),
        ('expired', 'Expired'),
    ]

    clinic = models.ForeignKey(Clinic, on_delete=models.CASCADE, related_name='treatment_plans')
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='treatment_plans')

    # Plan details
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    estimated_cost = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')

    # Timing
    sent_at = models.DateTimeField(null=True, blank=True)
    viewed_at = models.DateTimeField(null=True, blank=True)
    responded_at = models.DateTimeField(null=True, blank=True)
    followup_due_at = models.DateTimeField(null=True, blank=True)

    # Response
    response_notes = models.TextField(blank=True)

    # Created by practitioner
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_treatment_plans'
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Treatment plan: {self.title} for {self.patient}"
