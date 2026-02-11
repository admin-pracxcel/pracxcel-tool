"""
URL configuration for webhooks.

All webhook endpoints are exempt from CSRF protection.
"""

from django.urls import path
from . import views

app_name = 'webhooks'

urlpatterns = [
    # Twilio webhooks
    path('twilio/call-status/', views.twilio_call_status, name='twilio_call_status'),
    path('twilio/recording/', views.twilio_recording, name='twilio_recording'),

    # Google webhooks (for real-time conversion updates)
    path('google/conversion/', views.google_conversion, name='google_conversion'),

    # Meta webhooks
    path('meta/lead/', views.meta_lead, name='meta_lead'),

    # Marketing form submissions
    path('form-submit/', views.form_submit, name='form_submit'),
]
