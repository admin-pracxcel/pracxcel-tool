"""
Business logic services for core app.
Keep views thin, put logic here.
"""

from datetime import timedelta
from django.utils import timezone
from django.contrib.contenttypes.models import ContentType

from .models import Attribution, AuditLog


def create_attribution(patient, invoice):
    """
    Create attribution for a patient's first paid invoice.

    Attribution Rules (30-day lookback):
    1. Find all CallEvents with matching phone (30 days prior)
    2. Find all MarketingTouches with matching session/email (30 days prior)
    3. Rank by: paid campaign > organic call > organic touch
    4. Persist Attribution with evidence_json
    """
    from integrations.models import CallEvent, MarketingTouch

    lookback_date = invoice.paid_at - timedelta(days=30)
    evidence = {
        'invoice_id': invoice.id,
        'invoice_amount': str(invoice.total_amount),
        'paid_at': invoice.paid_at.isoformat(),
        'lookback_start': lookback_date.isoformat(),
        'evaluated_at': timezone.now().isoformat(),
    }

    # Find call events matching patient's phone
    call_events = []
    if patient.phone:
        call_events = list(
            CallEvent.objects.filter(
                clinic=patient.clinic,
                caller_phone=patient.phone,
                timestamp__gte=lookback_date,
                timestamp__lte=invoice.paid_at,
            ).order_by('-timestamp')
        )
        evidence['call_events_found'] = len(call_events)

    # Find marketing touches
    marketing_touches = list(
        MarketingTouch.objects.filter(
            clinic=patient.clinic,
            timestamp__gte=lookback_date,
            timestamp__lte=invoice.paid_at,
        ).filter(
            # Match by email or session
            email=patient.email
        ).order_by('-timestamp')
    ) if patient.email else []
    evidence['marketing_touches_found'] = len(marketing_touches)

    # Attribution priority:
    # 1. Paid call (from campaign tracking number)
    # 2. Paid marketing touch (utm_medium=cpc)
    # 3. Organic call
    # 4. Organic marketing touch
    # 5. Unknown

    attributed_source = None
    attribution_type = 'unknown'
    campaign_name = ''
    campaign_source = ''
    campaign_medium = ''

    # Check for paid calls first
    for call in call_events:
        if call.campaign_id:
            attributed_source = call
            attribution_type = 'call'
            campaign_name = call.campaign_name or ''
            campaign_source = 'phone'
            campaign_medium = 'call'
            evidence['attribution_reason'] = 'Matched paid campaign call'
            break

    # If no paid call, check for paid marketing touch
    if not attributed_source:
        for touch in marketing_touches:
            if touch.utm_medium in ['cpc', 'ppc', 'paid']:
                attributed_source = touch
                attribution_type = 'marketing_touch'
                campaign_name = touch.utm_campaign or ''
                campaign_source = touch.utm_source or ''
                campaign_medium = touch.utm_medium or ''
                evidence['attribution_reason'] = 'Matched paid marketing touch'
                break

    # If no paid source, check for organic call
    if not attributed_source and call_events:
        attributed_source = call_events[0]
        attribution_type = 'call'
        campaign_source = 'organic'
        campaign_medium = 'call'
        evidence['attribution_reason'] = 'Matched organic call'

    # If no call, check for organic marketing touch
    if not attributed_source and marketing_touches:
        attributed_source = marketing_touches[0]
        attribution_type = 'marketing_touch'
        campaign_source = marketing_touches[0].utm_source or 'organic'
        campaign_medium = marketing_touches[0].utm_medium or 'web'
        evidence['attribution_reason'] = 'Matched organic marketing touch'

    # Create the attribution
    content_type = None
    object_id = None
    if attributed_source:
        content_type = ContentType.objects.get_for_model(attributed_source)
        object_id = attributed_source.pk

    attribution, created = Attribution.objects.update_or_create(
        patient=patient,
        defaults={
            'clinic': patient.clinic,
            'attribution_type': attribution_type,
            'content_type': content_type,
            'object_id': object_id,
            'campaign_name': campaign_name,
            'campaign_source': campaign_source,
            'campaign_medium': campaign_medium,
            'evidence_json': evidence,
            'first_invoice_amount': invoice.total_amount,
            'first_invoice_date': invoice.paid_at.date() if invoice.paid_at else None,
        }
    )

    return attribution


def override_attribution(attribution, user, new_source, reason):
    """
    Manually override patient attribution.
    Logs the override for audit trail.
    """
    from django.contrib.contenttypes.models import ContentType

    old_evidence = attribution.evidence_json.copy()
    old_evidence['previous_attribution'] = {
        'type': attribution.attribution_type,
        'source': str(attribution.attributed_source) if attribution.attributed_source else None,
        'campaign': attribution.campaign_name,
    }

    # Update attribution
    if new_source:
        attribution.content_type = ContentType.objects.get_for_model(new_source)
        attribution.object_id = new_source.pk
        if hasattr(new_source, 'campaign_name'):
            attribution.campaign_name = new_source.campaign_name or ''

    attribution.status = 'manual'
    attribution.overridden_by = user
    attribution.override_reason = reason
    attribution.overridden_at = timezone.now()
    attribution.evidence_json = old_evidence
    attribution.save()

    return attribution


def log_audit(user, clinic, action, obj, changes=None, request=None):
    """
    Create an audit log entry for data access.

    Args:
        user: The user performing the action
        clinic: The clinic context
        action: One of 'read', 'create', 'update', 'delete', 'export'
        obj: The object being accessed
        changes: Dict of field changes (for updates)
        request: HTTP request (for IP and user agent)
    """
    from django.contrib.contenttypes.models import ContentType

    ip_address = None
    user_agent = ''

    if request:
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip_address = x_forwarded_for.split(',')[0].strip()
        else:
            ip_address = request.META.get('REMOTE_ADDR')
        user_agent = request.META.get('HTTP_USER_AGENT', '')[:500]

    AuditLog.objects.create(
        user=user,
        clinic=clinic,
        action=action,
        content_type=ContentType.objects.get_for_model(obj),
        object_id=obj.pk,
        object_repr=str(obj)[:255],
        changes_json=changes or {},
        ip_address=ip_address,
        user_agent=user_agent,
    )
