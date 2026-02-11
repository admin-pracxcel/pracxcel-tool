"""
Twilio webhook handler.

Validates incoming webhooks and creates CallEvent records.
"""

import logging
from typing import Optional
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)


class TwilioWebhookHandler:
    """
    Handler for Twilio webhook events.

    Usage:
        handler = TwilioWebhookHandler()
        if handler.validate_signature(request):
            call_event = handler.process_webhook(request.POST, clinic)
    """

    def validate_signature(self, request) -> bool:
        """
        Validate Twilio webhook signature.

        Args:
            request: Django HTTP request

        Returns:
            True if signature is valid
        """
        from twilio.request_validator import RequestValidator

        auth_token = settings.TWILIO_AUTH_TOKEN
        if not auth_token:
            logger.warning("TWILIO_AUTH_TOKEN not configured")
            return False

        validator = RequestValidator(auth_token)

        # Get the full URL (Twilio signs the full URL)
        url = request.build_absolute_uri()

        # Get signature from header
        signature = request.META.get('HTTP_X_TWILIO_SIGNATURE', '')

        # Validate
        return validator.validate(
            url,
            request.POST.dict(),
            signature
        )

    def process_webhook(self, data: dict, clinic) -> Optional['CallEvent']:
        """
        Process a Twilio webhook and create/update CallEvent.

        Args:
            data: POST data from Twilio webhook
            clinic: Clinic model instance

        Returns:
            CallEvent instance or None
        """
        from integrations.models import CallEvent

        call_sid = data.get('CallSid')
        if not call_sid:
            logger.warning("No CallSid in webhook data")
            return None

        # Map Twilio status to our choices
        status_map = {
            'ringing': 'ringing',
            'in-progress': 'in-progress',
            'completed': 'completed',
            'busy': 'busy',
            'no-answer': 'no-answer',
            'failed': 'failed',
            'canceled': 'canceled',
        }

        call_status = status_map.get(data.get('CallStatus', '').lower(), 'ringing')

        # Determine direction
        direction = 'inbound'
        if data.get('Direction') == 'outbound-api':
            direction = 'outbound'

        # Parse timestamps
        timestamp = timezone.now()

        # Create or update CallEvent
        call_event, created = CallEvent.objects.update_or_create(
            call_sid=call_sid,
            defaults={
                'clinic': clinic,
                'parent_call_sid': data.get('ParentCallSid', ''),
                'caller_phone': data.get('From', ''),
                'called_phone': data.get('To', ''),
                'direction': direction,
                'status': call_status,
                'duration_seconds': int(data.get('CallDuration', 0)),
                'timestamp': timestamp,
                'recording_url': data.get('RecordingUrl', ''),
                'tracking_number': data.get('To', ''),
            }
        )

        # Look up campaign from tracking number
        self._assign_campaign(call_event)

        if created:
            logger.info(f"Created CallEvent {call_sid}")
        else:
            logger.info(f"Updated CallEvent {call_sid}")

        return call_event

    def _assign_campaign(self, call_event):
        """
        Look up campaign based on tracking phone number.
        """
        from integrations.models import Campaign

        if call_event.tracking_number:
            campaign = Campaign.objects.filter(
                clinic=call_event.clinic,
                tracking_phone=call_event.tracking_number,
                is_active=True
            ).first()

            if campaign:
                call_event.campaign_id = campaign.external_id
                call_event.campaign_name = campaign.name
                call_event.save(update_fields=['campaign_id', 'campaign_name'])
