"""
Celery tasks for integration syncing.

Scheduled via Celery Beat (see config/celery.py).
"""

import logging
from datetime import timedelta

from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=300)
def sync_integration(self, integration_id):
    """
    Sync a single integration.
    Called manually or by periodic tasks.
    """
    from .models import Integration

    try:
        integration = Integration.objects.get(id=integration_id)

        if integration.integration_type == 'google_ads':
            sync_google_ads_for_integration(integration)
        elif integration.integration_type == 'google_analytics':
            sync_ga4_for_integration(integration)
        elif integration.integration_type == 'meta_ads':
            sync_meta_ads_for_integration(integration)

        integration.last_sync_at = timezone.now()
        integration.last_error = ''
        integration.save()

    except Integration.DoesNotExist:
        logger.error(f"Integration {integration_id} not found")
    except Exception as e:
        logger.exception(f"Error syncing integration {integration_id}")
        if integration:
            integration.last_error = str(e)
            integration.save()
        raise self.retry(exc=e)


@shared_task
def sync_cliniko():
    """
    Sync patient, appointment, and invoice data from Cliniko.
    Runs every 15 minutes via Celery Beat.
    """
    from core.models import Clinic

    clinics = Clinic.objects.filter(is_active=True).exclude(cliniko_api_key='')

    for clinic in clinics:
        try:
            sync_cliniko_for_clinic(clinic)
        except Exception as e:
            logger.exception(f"Error syncing Cliniko for {clinic.name}")


@shared_task
def sync_google_ads_spend():
    """
    Sync daily spend data from Google Ads.
    Runs daily via Celery Beat.
    """
    from .models import Integration

    integrations = Integration.objects.filter(
        integration_type='google_ads',
        is_active=True
    )

    for integration in integrations:
        try:
            sync_google_ads_for_integration(integration)
        except Exception as e:
            logger.exception(f"Error syncing Google Ads for {integration.clinic.name}")


@shared_task
def sync_meta_ads_spend():
    """
    Sync daily spend data from Meta Ads.
    Runs daily via Celery Beat.
    """
    from .models import Integration

    integrations = Integration.objects.filter(
        integration_type='meta_ads',
        is_active=True
    )

    for integration in integrations:
        try:
            sync_meta_ads_for_integration(integration)
        except Exception as e:
            logger.exception(f"Error syncing Meta Ads for {integration.clinic.name}")


def sync_cliniko_for_clinic(clinic):
    """
    Sync patients, appointments, and invoices from Cliniko API.

    Uses cursor-based pagination and incremental sync.
    """
    from .services.cliniko import ClinikoClient
    from core.models import Patient, Appointment, Invoice

    client = ClinikoClient(clinic.cliniko_api_key, clinic.cliniko_shard)

    # Sync patients
    cursor = clinic.last_sync_cursor
    patients_data = client.get_patients(since_cursor=cursor)

    for patient_data in patients_data['patients']:
        Patient.objects.update_or_create(
            clinic=clinic,
            cliniko_id=patient_data['id'],
            defaults={
                'first_name': patient_data.get('first_name', ''),
                'last_name': patient_data.get('last_name', ''),
                'email': patient_data.get('email', ''),
                'phone': patient_data.get('phone_numbers', [{}])[0].get('number', ''),
                'date_of_birth': patient_data.get('date_of_birth'),
                'cliniko_created_at': patient_data.get('created_at'),
                'cliniko_updated_at': patient_data.get('updated_at'),
            }
        )

    # Update sync cursor
    if patients_data.get('next_cursor'):
        clinic.last_sync_cursor = patients_data['next_cursor']
        clinic.last_cliniko_sync = timezone.now()
        clinic.save()

    logger.info(f"Synced {len(patients_data['patients'])} patients for {clinic.name}")


def sync_google_ads_for_integration(integration):
    """
    Sync campaign spend data from Google Ads API.
    """
    from .services.google_ads import GoogleAdsClient
    from .models import Campaign, CampaignDailyStats
    from datetime import date, timedelta

    client = GoogleAdsClient(
        access_token=integration.access_token,
        refresh_token=integration.refresh_token,
        customer_id=integration.config_json.get('customer_id'),
    )

    # Get last 7 days of data
    end_date = date.today()
    start_date = end_date - timedelta(days=7)

    campaigns_data = client.get_campaign_metrics(start_date, end_date)

    for campaign_data in campaigns_data:
        campaign, _ = Campaign.objects.update_or_create(
            clinic=integration.clinic,
            source='google_ads',
            external_id=campaign_data['id'],
            defaults={
                'name': campaign_data['name'],
                'is_active': campaign_data['status'] == 'ENABLED',
            }
        )

        # Update daily stats
        for day_data in campaign_data.get('daily_metrics', []):
            CampaignDailyStats.objects.update_or_create(
                campaign=campaign,
                date=day_data['date'],
                defaults={
                    'spend': day_data['cost_micros'] / 1_000_000,
                    'impressions': day_data['impressions'],
                    'clicks': day_data['clicks'],
                    'conversions': day_data['conversions'],
                }
            )

    logger.info(f"Synced Google Ads for {integration.clinic.name}")


def sync_meta_ads_for_integration(integration):
    """
    Sync campaign spend data from Meta Ads API.
    """
    from .services.meta_ads import MetaAdsClient
    from .models import Campaign, CampaignDailyStats
    from datetime import date, timedelta

    client = MetaAdsClient(
        access_token=integration.access_token,
        ad_account_id=integration.config_json.get('ad_account_id'),
    )

    # Get last 7 days of data
    end_date = date.today()
    start_date = end_date - timedelta(days=7)

    campaigns_data = client.get_campaign_insights(start_date, end_date)

    for campaign_data in campaigns_data:
        campaign, _ = Campaign.objects.update_or_create(
            clinic=integration.clinic,
            source='meta_ads',
            external_id=campaign_data['id'],
            defaults={
                'name': campaign_data['name'],
                'is_active': campaign_data['status'] == 'ACTIVE',
            }
        )

        # Update daily stats
        for day_data in campaign_data.get('daily_metrics', []):
            CampaignDailyStats.objects.update_or_create(
                campaign=campaign,
                date=day_data['date'],
                defaults={
                    'spend': day_data['spend'],
                    'impressions': day_data['impressions'],
                    'clicks': day_data['clicks'],
                    'conversions': day_data.get('conversions', 0),
                }
            )

    logger.info(f"Synced Meta Ads for {integration.clinic.name}")


def _ensure_ga4_token_fresh(integration):
    """Refresh the GA4 access token if it's expired or about to expire."""
    from .services.google_analytics import refresh_access_token

    if not integration.refresh_token:
        raise ValueError("GA4 integration missing refresh token — please reconnect.")

    # Refresh if token expires within the next 5 minutes (or already expired)
    if integration.token_expires_at and integration.token_expires_at > timezone.now() + timedelta(minutes=5):
        return  # Still valid

    tokens = refresh_access_token(integration.refresh_token)
    integration.access_token = tokens['access_token']
    integration.token_expires_at = timezone.now() + timedelta(seconds=tokens['expires_in'])
    integration.save(update_fields=['access_token', 'token_expires_at'])
    logger.info(f"Refreshed GA4 access token for {integration.clinic.name}")


def sync_ga4_for_integration(integration):
    """
    Sync session data from Google Analytics 4 Data API.

    Pulls aggregated session data grouped by source/medium/campaign/date
    and creates MarketingTouch records.
    """
    from .services.google_analytics import GA4Client
    from .models import MarketingTouch
    from datetime import date, timedelta, datetime

    property_id = integration.config_json.get('property_id')
    if not property_id:
        raise ValueError("GA4 integration missing property_id")

    # Refresh token if needed
    _ensure_ga4_token_fresh(integration)

    client = GA4Client(
        access_token=integration.access_token,
        property_id=property_id,
    )

    # Get last 7 days of data
    end_date = date.today()
    start_date = end_date - timedelta(days=7)

    rows = client.get_session_report(start_date, end_date)

    created_count = 0
    for row in rows:
        # Use get_or_create to avoid duplicates
        # Unique on: clinic + source + date + utm_source + utm_medium + utm_campaign + landing_page
        _, created = MarketingTouch.objects.get_or_create(
            clinic=integration.clinic,
            source='ga4',
            utm_source=row['utm_source'],
            utm_medium=row['utm_medium'],
            utm_campaign=row['utm_campaign'],
            landing_page=row['landing_page'],
            timestamp=timezone.make_aware(datetime.combine(row['date'], datetime.min.time())),
            defaults={
                'utm_content': row['utm_content'],
            },
        )
        if created:
            created_count += 1

    integration.last_sync_at = timezone.now()
    integration.last_error = ''
    integration.save()

    logger.info(
        f"GA4 sync for {integration.clinic.name}: "
        f"{len(rows)} rows, {created_count} new touches"
    )
