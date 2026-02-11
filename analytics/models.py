"""
Analytics models for caching computed metrics.

Most analytics are computed on-the-fly, but some are cached here.
"""

from django.db import models
from core.models import Clinic


class DailyMetrics(models.Model):
    """
    Cached daily metrics for dashboard performance.
    Computed nightly via Celery task.
    """
    clinic = models.ForeignKey(Clinic, on_delete=models.CASCADE, related_name='daily_metrics')
    date = models.DateField(db_index=True)

    # Patient metrics
    new_patients = models.PositiveIntegerField(default=0)
    total_patients = models.PositiveIntegerField(default=0)

    # Appointment metrics
    appointments_scheduled = models.PositiveIntegerField(default=0)
    appointments_completed = models.PositiveIntegerField(default=0)
    appointments_cancelled = models.PositiveIntegerField(default=0)
    appointments_no_show = models.PositiveIntegerField(default=0)

    # Revenue metrics
    revenue_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    revenue_from_new_patients = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    # Marketing metrics
    total_ad_spend = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    cost_per_new_patient = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    # Call metrics
    total_calls = models.PositiveIntegerField(default=0)
    missed_calls = models.PositiveIntegerField(default=0)
    calls_converted = models.PositiveIntegerField(default=0)

    # Task metrics
    tasks_created = models.PositiveIntegerField(default=0)
    tasks_completed = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['clinic', 'date']
        ordering = ['-date']
        verbose_name_plural = 'Daily metrics'

    def __str__(self):
        return f"{self.clinic} - {self.date}"
