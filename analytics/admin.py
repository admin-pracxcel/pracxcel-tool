"""
Django admin configuration for analytics models.
"""

from django.contrib import admin
from .models import DailyMetrics


@admin.register(DailyMetrics)
class DailyMetricsAdmin(admin.ModelAdmin):
    list_display = [
        'clinic', 'date', 'new_patients', 'appointments_completed',
        'revenue_total', 'total_ad_spend', 'cost_per_new_patient'
    ]
    list_filter = ['clinic']
    date_hierarchy = 'date'
    readonly_fields = ['created_at', 'updated_at']
