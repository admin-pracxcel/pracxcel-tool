"""
URL configuration for Pracxcel Tool.
"""

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),

    # App URLs
    path('', include('core.urls')),
    path('operations/', include('operations.urls')),
    path('analytics/', include('analytics.urls')),
    path('integrations/', include('integrations.urls')),

    # Webhook endpoints
    path('webhooks/', include('webhooks.urls')),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
