"""
URL configuration for integrations app.
"""

from django.urls import path
from . import views

app_name = 'integrations'

urlpatterns = [
    path('', views.integration_list, name='integration_list'),
    path('connect/<str:integration_type>/', views.connect_integration, name='connect'),
    path('disconnect/<int:pk>/', views.disconnect_integration, name='disconnect'),
    path('sync/<int:pk>/', views.trigger_sync, name='trigger_sync'),

    # Cliniko-specific (credentials on Clinic model, not Integration)
    path('cliniko/sync/', views.cliniko_sync, name='cliniko_sync'),
    path('cliniko/disconnect/', views.cliniko_disconnect, name='cliniko_disconnect'),

    # GA4 OAuth flow
    path('ga4/connect/', views.ga4_start_oauth, name='ga4_start_oauth'),
    path('ga4/callback/', views.ga4_oauth_callback, name='ga4_oauth_callback'),
    path('ga4/select-property/', views.ga4_select_property, name='ga4_select_property'),

    # GA4 data dashboard
    path('ga4/data/<int:pk>/', views.ga4_dashboard, name='ga4_dashboard'),

    # GA4-specific (sync runs synchronously without Celery)
    path('ga4/sync/<int:pk>/', views.ga4_sync, name='ga4_sync'),
]
