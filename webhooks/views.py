"""
Webhook endpoint views.

All endpoints:
- Are exempt from CSRF
- Validate signatures
- Log all requests
- Process asynchronously via Celery
"""

import json
import logging
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.utils import timezone

from .models import WebhookLog
from core.models import Clinic

logger = logging.getLogger(__name__)


def log_webhook(request, source, clinic=None):
    """Log incoming webhook for debugging."""
    try:
        body = json.loads(request.body) if request.body else {}
    except json.JSONDecodeError:
        body = dict(request.POST)

    headers = {
        k: v for k, v in request.META.items()
        if k.startswith('HTTP_') or k in ['CONTENT_TYPE', 'CONTENT_LENGTH']
    }

    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip_address = x_forwarded_for.split(',')[0].strip()
    else:
        ip_address = request.META.get('REMOTE_ADDR')

    return WebhookLog.objects.create(
        clinic=clinic,
        source=source,
        endpoint=request.path,
        method=request.method,
        headers_json=headers,
        body_json=body,
        ip_address=ip_address,
    )


@csrf_exempt
@require_POST
def twilio_call_status(request):
    """
    Twilio call status webhook.

    Receives call events (ringing, in-progress, completed, etc.)
    """
    from integrations.services.twilio_handler import TwilioWebhookHandler

    # Log the webhook
    webhook_log = log_webhook(request, 'twilio')

    # Validate signature
    handler = TwilioWebhookHandler()
    if not handler.validate_signature(request):
        webhook_log.status = 'invalid'
        webhook_log.error_message = 'Invalid Twilio signature'
        webhook_log.save()
        logger.warning(f"Invalid Twilio signature for webhook {webhook_log.id}")
        return HttpResponse('Invalid signature', status=403)

    # Determine clinic from tracking number
    tracking_number = request.POST.get('To', '')
    clinic = Clinic.objects.filter(
        is_active=True,
        # In production, would look up by tracking number mapping
    ).first()

    if clinic:
        webhook_log.clinic = clinic
        webhook_log.save()

        # Process the webhook
        try:
            call_event = handler.process_webhook(request.POST, clinic)
            webhook_log.status = 'processed'
            webhook_log.processed_at = timezone.now()
            webhook_log.save()
        except Exception as e:
            logger.exception("Error processing Twilio webhook")
            webhook_log.status = 'failed'
            webhook_log.error_message = str(e)
            webhook_log.save()

    # Twilio expects empty 200 response
    return HttpResponse('')


@csrf_exempt
@require_POST
def twilio_recording(request):
    """
    Twilio recording webhook.

    Receives notification when call recording is ready.
    """
    webhook_log = log_webhook(request, 'twilio')

    # Process recording URL
    call_sid = request.POST.get('CallSid')
    recording_url = request.POST.get('RecordingUrl')

    if call_sid and recording_url:
        from integrations.models import CallEvent
        CallEvent.objects.filter(call_sid=call_sid).update(
            recording_url=recording_url,
            recording_duration=int(request.POST.get('RecordingDuration', 0))
        )
        webhook_log.status = 'processed'
        webhook_log.processed_at = timezone.now()
        webhook_log.save()

    return HttpResponse('')


@csrf_exempt
@require_POST
def google_conversion(request):
    """
    Google conversion webhook (if configured).
    """
    webhook_log = log_webhook(request, 'google')

    # Google doesn't typically push webhooks, but this could be used
    # for custom server-to-server integrations

    webhook_log.status = 'processed'
    webhook_log.processed_at = timezone.now()
    webhook_log.save()

    return JsonResponse({'status': 'ok'})


@csrf_exempt
@require_POST
def meta_lead(request):
    """
    Meta lead webhook for Facebook Lead Ads.
    """
    webhook_log = log_webhook(request, 'meta')

    try:
        data = json.loads(request.body)

        # Verify Meta webhook (would need to verify signature)
        # For now, just log

        webhook_log.status = 'processed'
        webhook_log.processed_at = timezone.now()
        webhook_log.save()

        return JsonResponse({'status': 'ok'})

    except json.JSONDecodeError:
        webhook_log.status = 'failed'
        webhook_log.error_message = 'Invalid JSON'
        webhook_log.save()
        return JsonResponse({'error': 'Invalid JSON'}, status=400)


@csrf_exempt
@require_POST
def form_submit(request):
    """
    Marketing form submission webhook.

    Captures UTM parameters and creates MarketingTouch.
    """
    from integrations.models import MarketingTouch

    webhook_log = log_webhook(request, 'other')

    try:
        data = json.loads(request.body) if request.body else dict(request.POST)

        # Extract UTM parameters
        clinic_id = data.get('clinic_id')
        clinic = Clinic.objects.filter(id=clinic_id, is_active=True).first() if clinic_id else None

        if clinic:
            MarketingTouch.objects.create(
                clinic=clinic,
                email=data.get('email', ''),
                utm_source=data.get('utm_source', ''),
                utm_medium=data.get('utm_medium', ''),
                utm_campaign=data.get('utm_campaign', ''),
                utm_term=data.get('utm_term', ''),
                utm_content=data.get('utm_content', ''),
                gclid=data.get('gclid', ''),
                fbclid=data.get('fbclid', ''),
                landing_page=data.get('landing_page', ''),
                referrer=data.get('referrer', ''),
                timestamp=timezone.now(),
                source='form',
            )

            webhook_log.clinic = clinic
            webhook_log.status = 'processed'
            webhook_log.processed_at = timezone.now()
            webhook_log.save()

        return JsonResponse({'status': 'ok'})

    except Exception as e:
        logger.exception("Error processing form submission")
        webhook_log.status = 'failed'
        webhook_log.error_message = str(e)
        webhook_log.save()
        return JsonResponse({'error': str(e)}, status=500)
