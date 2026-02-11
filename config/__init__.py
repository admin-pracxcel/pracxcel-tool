"""
Pracxcel Tool - Clinic Practice Intelligence SaaS

This module makes Celery app available for Django.
"""

try:
    from .celery import app as celery_app
    __all__ = ('celery_app',)
except ImportError:
    # Celery not installed - skip for migrations/basic usage
    celery_app = None
    __all__ = ()
