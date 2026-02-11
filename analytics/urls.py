"""
URL configuration for analytics app.
"""

from django.urls import path
from . import views

app_name = 'analytics'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('reports/campaigns/', views.campaign_report, name='campaign_report'),
    path('reports/attribution/', views.attribution_report, name='attribution_report'),
    path('api/metrics/', views.metrics_api, name='metrics_api'),
]
