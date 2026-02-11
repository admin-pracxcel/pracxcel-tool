"""
Views for managing integrations.
"""

import json
import logging
from datetime import date, datetime, timedelta

from django.db.models import Count
from django.db.models.functions import TruncDate
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone

from core.models import Clinic, Patient
from .models import Integration, MarketingTouch

logger = logging.getLogger(__name__)


def get_clinic():
    """
    Get the active clinic for the current user.
    MVP: returns the first active clinic. Upgrade to user-clinic FK later.
    """
    return Clinic.objects.filter(is_active=True).first()


@login_required
def integration_list(request):
    """List all available integrations and their status."""
    clinic = get_clinic()

    # Build context for each integration's status
    cliniko_connected = bool(clinic and clinic.cliniko_api_key)
    cliniko_patient_count = 0
    if cliniko_connected:
        cliniko_patient_count = Patient.objects.filter(clinic=clinic).count()

    # Other integrations from the Integration model
    other_integrations = {}
    if clinic:
        for integration in Integration.objects.filter(clinic=clinic):
            other_integrations[integration.integration_type] = integration

    context = {
        'page_title': 'Integrations',
        'clinic': clinic,
        'cliniko_connected': cliniko_connected,
        'cliniko_patient_count': cliniko_patient_count,
        'other_integrations': other_integrations,
    }
    return render(request, 'integrations/integration_list.html', context)


@login_required
def connect_integration(request, integration_type):
    """Initiate OAuth flow or API key setup for an integration."""
    clinic = get_clinic()

    if not clinic:
        messages.error(request, 'No clinic found. Please create a clinic first in the admin panel.')
        return redirect('integrations:integration_list')

    if integration_type == 'cliniko':
        return _connect_cliniko(request, clinic)

    if integration_type == 'google_analytics':
        return redirect('integrations:ga4_start_oauth')

    # Stub for other integration types
    context = {
        'page_title': f'Connect {integration_type.replace("_", " ").title()}',
        'integration_type': integration_type,
        'clinic': clinic,
    }
    return render(request, 'integrations/connect.html', context)


def _connect_cliniko(request, clinic):
    """Handle Cliniko connection — API key based."""
    error = None
    detected_shard = None

    if request.method == 'POST':
        api_key = request.POST.get('api_key', '').strip()

        if not api_key:
            error = 'API key is required.'
        else:
            # Auto-detect shard from API key suffix
            from .services.cliniko import ClinikoClient, extract_shard_from_key
            detected_shard = extract_shard_from_key(api_key)
            try:
                client = ClinikoClient(api_key=api_key)
                result = client.get_patients(per_page=1)
                # If we get here without exception, the key is valid
                clinic.cliniko_api_key = api_key
                clinic.cliniko_shard = client.shard
                clinic.save()
                messages.success(
                    request,
                    f'Cliniko connected successfully (shard: {client.shard}). '
                    f'{result.get("total_entries", 0)} patients found in your account.'
                )
                return redirect('integrations:integration_list')
            except Exception as e:
                logger.warning(f'Cliniko connection test failed: {e}')
                error = (
                    f'Connection failed. Detected shard "{detected_shard}" from your key. '
                    f'Please check that your API key is correct. '
                    f'Error: {e}'
                )

    context = {
        'page_title': 'Connect Cliniko',
        'integration_type': 'cliniko',
        'clinic': clinic,
        'error': error,
        'detected_shard': detected_shard,
        # Pre-populate if already connected
        'current_api_key': clinic.cliniko_api_key,
        'current_shard': clinic.cliniko_shard,
    }
    return render(request, 'integrations/connect.html', context)


@login_required
def cliniko_sync(request):
    """Manually trigger a Cliniko sync."""
    if request.method != 'POST':
        return redirect('integrations:integration_list')

    clinic = get_clinic()
    if not clinic or not clinic.cliniko_api_key:
        messages.error(request, 'Cliniko is not connected.')
        return redirect('integrations:integration_list')

    from .tasks import sync_cliniko_for_clinic

    patient_count_before = Patient.objects.filter(clinic=clinic).count()

    try:
        sync_cliniko_for_clinic(clinic)
        patient_count_after = Patient.objects.filter(clinic=clinic).count()
        new_patients = patient_count_after - patient_count_before
        messages.success(
            request,
            f'Cliniko sync completed. '
            f'{patient_count_after} total patients ({new_patients} new).'
        )
    except Exception as e:
        logger.exception(f'Cliniko sync failed for {clinic.name}')
        messages.error(request, f'Sync failed: {e}')

    return redirect('integrations:integration_list')


@login_required
def cliniko_disconnect(request):
    """Disconnect Cliniko integration."""
    if request.method != 'POST':
        return redirect('integrations:integration_list')

    clinic = get_clinic()
    if not clinic:
        messages.error(request, 'No clinic found.')
        return redirect('integrations:integration_list')

    clinic.cliniko_api_key = ''
    clinic.cliniko_shard = 'api'
    clinic.last_cliniko_sync = None
    clinic.last_sync_cursor = ''
    clinic.save()

    messages.success(request, 'Cliniko disconnected.')
    return redirect('integrations:integration_list')


@login_required
def ga4_start_oauth(request):
    """Start the Google OAuth flow for GA4 — redirect user to Google consent screen."""
    from .services.google_analytics import build_oauth_url

    clinic = get_clinic()
    if not clinic:
        messages.error(request, 'No clinic found. Please create a clinic first in the admin panel.')
        return redirect('integrations:integration_list')

    redirect_uri = request.build_absolute_uri('/integrations/ga4/callback/')
    # Use Django's CSRF token as the OAuth state parameter
    state = request.META.get('CSRF_COOKIE', '')
    oauth_url = build_oauth_url(redirect_uri, state=state)
    return redirect(oauth_url)


@login_required
def ga4_oauth_callback(request):
    """Handle Google's OAuth callback — exchange code for tokens."""
    from .services.google_analytics import exchange_code

    error_param = request.GET.get('error')
    if error_param:
        messages.error(request, f'Google sign-in was cancelled or failed: {error_param}')
        return redirect('integrations:integration_list')

    code = request.GET.get('code', '')
    if not code:
        messages.error(request, 'No authorization code received from Google.')
        return redirect('integrations:integration_list')

    redirect_uri = request.build_absolute_uri('/integrations/ga4/callback/')

    try:
        tokens = exchange_code(code, redirect_uri)
    except ValueError as e:
        logger.warning(f'GA4 OAuth token exchange failed: {e}')
        messages.error(request, f'Could not complete Google sign-in: {e}')
        return redirect('integrations:integration_list')

    # Store tokens temporarily in session so the property picker can use them
    request.session['ga4_access_token'] = tokens['access_token']
    request.session['ga4_refresh_token'] = tokens['refresh_token']
    request.session['ga4_token_expires_in'] = tokens['expires_in']

    return redirect('integrations:ga4_select_property')


@login_required
def ga4_select_property(request):
    """GET: show GA4 property picker. POST: save selected property + tokens."""
    from .services.google_analytics import list_ga4_properties

    clinic = get_clinic()
    if not clinic:
        messages.error(request, 'No clinic found.')
        return redirect('integrations:integration_list')

    access_token = request.session.get('ga4_access_token')
    refresh_token = request.session.get('ga4_refresh_token')
    expires_in = request.session.get('ga4_token_expires_in', 3600)

    if not access_token:
        messages.error(request, 'Google sign-in expired. Please try again.')
        return redirect('integrations:integration_list')

    if request.method == 'POST':
        property_id = request.POST.get('property_id', '').strip()
        if not property_id:
            messages.error(request, 'Please select a property.')
            return redirect('integrations:ga4_select_property')

        # Find the property name from the submitted form
        property_name = request.POST.get('property_name', property_id)

        # Save to Integration model
        Integration.objects.update_or_create(
            clinic=clinic,
            integration_type='google_analytics',
            defaults={
                'is_active': True,
                'access_token': access_token,
                'refresh_token': refresh_token,
                'token_expires_at': timezone.now() + timedelta(seconds=expires_in),
                'config_json': {
                    'property_id': property_id,
                    'property_name': property_name,
                },
            },
        )

        # Clean up session
        for key in ('ga4_access_token', 'ga4_refresh_token', 'ga4_token_expires_in'):
            request.session.pop(key, None)

        messages.success(request, f'Google Analytics 4 connected — {property_name}.')
        return redirect('integrations:integration_list')

    # GET — list properties for the user to choose
    try:
        properties = list_ga4_properties(access_token)
    except Exception as e:
        logger.warning(f'GA4 property listing failed: {e}')
        messages.error(request, f'Could not list your GA4 properties: {e}')
        return redirect('integrations:integration_list')

    if not properties:
        messages.warning(
            request,
            'No GA4 properties found on your Google account. '
            'Make sure you have access to at least one GA4 property.'
        )
        return redirect('integrations:integration_list')

    context = {
        'page_title': 'Select GA4 Property',
        'properties': properties,
        'clinic': clinic,
    }
    return render(request, 'integrations/ga4_select_property.html', context)


@login_required
def ga4_sync(request, pk):
    """Manually trigger a GA4 sync."""
    if request.method != 'POST':
        return redirect('integrations:integration_list')

    integration = get_object_or_404(
        Integration, pk=pk, integration_type='google_analytics'
    )

    from .tasks import sync_ga4_for_integration

    touch_count_before = MarketingTouch.objects.filter(
        clinic=integration.clinic, source='ga4'
    ).count()

    try:
        sync_ga4_for_integration(integration)
        touch_count_after = MarketingTouch.objects.filter(
            clinic=integration.clinic, source='ga4'
        ).count()
        new_touches = touch_count_after - touch_count_before
        messages.success(
            request,
            f'GA4 sync completed. '
            f'{touch_count_after} total marketing touches ({new_touches} new).'
        )
    except Exception as e:
        logger.exception(f'GA4 sync failed for {integration.clinic.name}')
        messages.error(request, f'Sync failed: {e}')

    return redirect('integrations:integration_list')


@login_required
def ga4_dashboard(request, pk):
    """Display GA4 marketing touch data with charts and tables."""
    integration = get_object_or_404(
        Integration, pk=pk, integration_type='google_analytics', is_active=True,
    )

    # Date range — default last 30 days
    end = date.today()
    start = end - timedelta(days=30)
    if request.GET.get('start'):
        try:
            start = date.fromisoformat(request.GET['start'])
        except ValueError:
            pass
    if request.GET.get('end'):
        try:
            end = date.fromisoformat(request.GET['end'])
        except ValueError:
            pass

    # Build timezone-aware boundaries for the filter
    start_dt = timezone.make_aware(datetime.combine(start, datetime.min.time()))
    end_dt = timezone.make_aware(datetime.combine(end, datetime.max.time()))

    touches = MarketingTouch.objects.filter(
        clinic=integration.clinic,
        source='ga4',
        timestamp__gte=start_dt,
        timestamp__lte=end_dt,
    )

    total_touches = touches.count()

    # --- Sessions by day (for chart) ---
    daily_qs = (
        touches
        .annotate(day=TruncDate('timestamp'))
        .values('day')
        .annotate(count=Count('id'))
        .order_by('day')
    )
    chart_labels = [row['day'].isoformat() for row in daily_qs]
    chart_data = [row['count'] for row in daily_qs]

    # --- Top sources (source / medium) ---
    sources = (
        touches
        .values('utm_source', 'utm_medium')
        .annotate(count=Count('id'))
        .order_by('-count')[:10]
    )

    # --- Top campaigns ---
    campaigns = (
        touches
        .exclude(utm_campaign='')
        .values('utm_campaign')
        .annotate(count=Count('id'))
        .order_by('-count')[:10]
    )

    # --- Top landing pages ---
    landing_pages = (
        touches
        .exclude(landing_page='')
        .values('landing_page')
        .annotate(count=Count('id'))
        .order_by('-count')[:10]
    )

    property_name = integration.config_json.get('property_name', integration.config_json.get('property_id', ''))

    context = {
        'page_title': f'GA4 — {property_name}',
        'integration': integration,
        'property_name': property_name,
        'start_date': start,
        'end_date': end,
        'total_touches': total_touches,
        'sources': sources,
        'campaigns': campaigns,
        'landing_pages': landing_pages,
        'chart_labels_json': json.dumps(chart_labels),
        'chart_data_json': json.dumps(chart_data),
    }
    return render(request, 'integrations/ga4_dashboard.html', context)


@login_required
def disconnect_integration(request, pk):
    """Disconnect an OAuth-based integration."""
    integration = get_object_or_404(Integration, pk=pk)

    if request.method == 'POST':
        integration.is_active = False
        integration.access_token = ''
        integration.refresh_token = ''
        integration.save()
        messages.success(request, f'{integration.get_integration_type_display()} disconnected.')
        return redirect('integrations:integration_list')

    context = {
        'page_title': 'Disconnect Integration',
        'integration': integration,
    }
    return render(request, 'integrations/disconnect_confirm.html', context)


@login_required
def trigger_sync(request, pk):
    """Manually trigger a sync for an OAuth-based integration."""
    integration = get_object_or_404(Integration, pk=pk)

    if request.method == 'POST':
        try:
            from .tasks import sync_integration
            sync_integration.delay(integration.id)
            messages.info(request, f'Sync started for {integration.get_integration_type_display()}.')
        except Exception:
            messages.error(request, 'Could not start sync. Is Celery running?')

    return redirect('integrations:integration_list')
