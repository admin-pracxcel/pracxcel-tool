"""
Django admin configuration for core models.
"""

from django.contrib import admin
from .models import Clinic, Patient, Appointment, Invoice, Attribution, AuditLog


@admin.register(Clinic)
class ClinicAdmin(admin.ModelAdmin):
    list_display = ['name', 'is_active', 'last_cliniko_sync', 'created_at']
    list_filter = ['is_active']
    search_fields = ['name']
    readonly_fields = ['created_at', 'updated_at', 'last_cliniko_sync']


@admin.register(Patient)
class PatientAdmin(admin.ModelAdmin):
    list_display = ['full_name', 'clinic', 'phone', 'email', 'first_paid_invoice_date']
    list_filter = ['clinic', 'sms_consent', 'email_consent']
    search_fields = ['first_name', 'last_name', 'email', 'phone', 'cliniko_id']
    readonly_fields = ['cliniko_id', 'created_at', 'updated_at']
    date_hierarchy = 'created_at'


@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = ['patient', 'clinic', 'scheduled_at', 'status', 'appointment_type']
    list_filter = ['clinic', 'status', 'appointment_type']
    search_fields = ['patient__first_name', 'patient__last_name', 'cliniko_id']
    readonly_fields = ['cliniko_id', 'created_at', 'updated_at']
    date_hierarchy = 'scheduled_at'
    raw_id_fields = ['patient']


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ['invoice_number', 'patient', 'clinic', 'status', 'total_amount', 'paid_at']
    list_filter = ['clinic', 'status']
    search_fields = ['invoice_number', 'patient__first_name', 'patient__last_name', 'cliniko_id']
    readonly_fields = ['cliniko_id', 'created_at', 'updated_at']
    date_hierarchy = 'issued_at'
    raw_id_fields = ['patient']


@admin.register(Attribution)
class AttributionAdmin(admin.ModelAdmin):
    list_display = ['patient', 'clinic', 'attribution_type', 'status', 'campaign_name', 'first_invoice_amount']
    list_filter = ['clinic', 'attribution_type', 'status', 'campaign_source']
    search_fields = ['patient__first_name', 'patient__last_name', 'campaign_name']
    readonly_fields = ['created_at', 'updated_at', 'overridden_at']
    raw_id_fields = ['patient', 'overridden_by']


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ['timestamp', 'user', 'clinic', 'action', 'object_repr', 'ip_address']
    list_filter = ['clinic', 'action', 'content_type']
    search_fields = ['object_repr', 'user__username']
    readonly_fields = ['user', 'clinic', 'action', 'content_type', 'object_id',
                       'object_repr', 'changes_json', 'ip_address', 'user_agent', 'timestamp']
    date_hierarchy = 'timestamp'

    def has_add_permission(self, request):
        return False  # Audit logs are created programmatically

    def has_change_permission(self, request, obj=None):
        return False  # Audit logs are immutable

    def has_delete_permission(self, request, obj=None):
        return False  # Audit logs cannot be deleted
