"""
URL configuration for operations app.
"""

from django.urls import path
from . import views

app_name = 'operations'

urlpatterns = [
    # Task inbox
    path('tasks/', views.task_inbox, name='task_inbox'),
    path('tasks/<int:pk>/', views.task_detail, name='task_detail'),
    path('tasks/<int:pk>/complete/', views.task_complete, name='task_complete'),
    path('tasks/<int:pk>/snooze/', views.task_snooze, name='task_snooze'),

    # Review requests
    path('reviews/', views.review_list, name='review_list'),
    path('reviews/<int:pk>/', views.review_detail, name='review_detail'),

    # Treatment plans
    path('treatment-plans/', views.treatment_plan_list, name='treatment_plan_list'),
    path('treatment-plans/<int:pk>/', views.treatment_plan_detail, name='treatment_plan_detail'),
]
