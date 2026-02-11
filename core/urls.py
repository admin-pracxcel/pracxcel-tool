"""
URL configuration for core app.
"""

from django.urls import path
from . import views

app_name = 'core'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('patients/', views.patient_list, name='patient_list'),
    path('patients/<int:pk>/', views.patient_detail, name='patient_detail'),
    path('patients/<int:pk>/timeline/', views.patient_timeline, name='patient_timeline'),
    path('patients/<int:pk>/attribution/', views.patient_attribution, name='patient_attribution'),
]
