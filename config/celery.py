"""
Celery configuration for Pracxcel Tool.

Usage:
    # Run worker (dev)
    celery -A config worker -l info

    # Run beat scheduler (dev)
    celery -A config beat -l info
"""

import os

from celery import Celery

# Set the default Django settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.dev')

app = Celery('pracxcel')

# Read config from Django settings, using CELERY_ prefix
app.config_from_object('django.conf:settings', namespace='CELERY')

# Auto-discover tasks in all installed apps
app.autodiscover_tasks()


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    """Debug task that prints request info."""
    print(f'Request: {self.request!r}')


# Celery Beat schedule - task generation runs hourly
app.conf.beat_schedule = {
    'generate-missed-call-tasks': {
        'task': 'operations.tasks.generate_missed_call_tasks',
        'schedule': 3600.0,  # Every hour
    },
    'generate-review-request-tasks': {
        'task': 'operations.tasks.generate_review_request_tasks',
        'schedule': 3600.0,  # Every hour
    },
    'generate-treatment-followup-tasks': {
        'task': 'operations.tasks.generate_treatment_followup_tasks',
        'schedule': 3600.0,  # Every hour
    },
    'sync-cliniko-data': {
        'task': 'integrations.tasks.sync_cliniko',
        'schedule': 900.0,  # Every 15 minutes
    },
    'sync-google-ads-spend': {
        'task': 'integrations.tasks.sync_google_ads_spend',
        'schedule': 86400.0,  # Daily
    },
    'sync-meta-ads-spend': {
        'task': 'integrations.tasks.sync_meta_ads_spend',
        'schedule': 86400.0,  # Daily
    },
}
