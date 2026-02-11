"""
Django admin configuration for operations models.
"""

from django.contrib import admin
from .models import Task, ReviewRequest, TreatmentPlan


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ['title', 'patient', 'clinic', 'task_type', 'priority', 'status', 'due_at', 'assigned_to']
    list_filter = ['clinic', 'task_type', 'priority', 'status']
    search_fields = ['title', 'patient__first_name', 'patient__last_name', 'description']
    readonly_fields = ['created_at', 'updated_at', 'completed_at']
    raw_id_fields = ['patient', 'assigned_to', 'completed_by']
    date_hierarchy = 'created_at'


@admin.register(ReviewRequest)
class ReviewRequestAdmin(admin.ModelAdmin):
    list_display = ['patient', 'clinic', 'channel', 'status', 'scheduled_at', 'sent_at']
    list_filter = ['clinic', 'channel', 'status', 'review_platform']
    search_fields = ['patient__first_name', 'patient__last_name']
    readonly_fields = ['created_at', 'updated_at']
    raw_id_fields = ['patient', 'appointment']
    date_hierarchy = 'scheduled_at'


@admin.register(TreatmentPlan)
class TreatmentPlanAdmin(admin.ModelAdmin):
    list_display = ['title', 'patient', 'clinic', 'status', 'estimated_cost', 'sent_at']
    list_filter = ['clinic', 'status']
    search_fields = ['title', 'patient__first_name', 'patient__last_name', 'description']
    readonly_fields = ['created_at', 'updated_at']
    raw_id_fields = ['patient', 'created_by']
    date_hierarchy = 'created_at'
