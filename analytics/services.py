"""
Analytics calculation services.

These compute metrics on-the-fly or from cached DailyMetrics.
"""

from datetime import date
from decimal import Decimal
from django.db.models import Sum, Count, Avg, Q

from core.models import Patient, Appointment, Invoice, Attribution
from integrations.models import Campaign, CampaignDailyStats, CallEvent
from operations.models import Task


def get_dashboard_metrics(start_date: date, end_date: date, clinic=None) -> dict:
    """
    Get key dashboard metrics for a date range.

    Returns dict with:
    - new_patients: Count of new patients
    - total_revenue: Sum of paid invoices
    - total_ad_spend: Sum of campaign spend
    - cost_per_new_patient: Spend / new patients
    - appointments_completed: Count of completed appointments
    - call_conversion_rate: Calls that resulted in appointments / total calls
    """
    filters = Q(created_at__date__gte=start_date, created_at__date__lte=end_date)
    if clinic:
        filters &= Q(clinic=clinic)

    # New patients (first paid invoice in date range)
    new_patients = Patient.objects.filter(
        first_paid_invoice_date__gte=start_date,
        first_paid_invoice_date__lte=end_date,
    )
    if clinic:
        new_patients = new_patients.filter(clinic=clinic)
    new_patient_count = new_patients.count()

    # Revenue from paid invoices
    invoice_filters = Q(paid_at__date__gte=start_date, paid_at__date__lte=end_date, status='paid')
    if clinic:
        invoice_filters &= Q(clinic=clinic)
    revenue = Invoice.objects.filter(invoice_filters).aggregate(
        total=Sum('total_amount')
    )['total'] or Decimal('0')

    # Ad spend
    spend_filters = Q(date__gte=start_date, date__lte=end_date)
    if clinic:
        spend_filters &= Q(campaign__clinic=clinic)
    ad_spend = CampaignDailyStats.objects.filter(spend_filters).aggregate(
        total=Sum('spend')
    )['total'] or Decimal('0')

    # Cost per new patient
    cost_per_new_patient = None
    if new_patient_count > 0 and ad_spend > 0:
        cost_per_new_patient = ad_spend / new_patient_count

    # Appointments
    appt_filters = Q(
        scheduled_at__date__gte=start_date,
        scheduled_at__date__lte=end_date,
        status='completed'
    )
    if clinic:
        appt_filters &= Q(clinic=clinic)
    appointments_completed = Appointment.objects.filter(appt_filters).count()

    # Call metrics
    call_filters = Q(timestamp__date__gte=start_date, timestamp__date__lte=end_date)
    if clinic:
        call_filters &= Q(clinic=clinic)
    calls = CallEvent.objects.filter(call_filters)
    total_calls = calls.count()
    calls_converted = calls.filter(resulted_in_appointment=True).count()
    call_conversion_rate = (calls_converted / total_calls * 100) if total_calls > 0 else 0

    # Attributed new patients breakdown
    attribution_breakdown = Attribution.objects.filter(
        created_at__date__gte=start_date,
        created_at__date__lte=end_date,
    )
    if clinic:
        attribution_breakdown = attribution_breakdown.filter(clinic=clinic)
    attribution_breakdown = attribution_breakdown.values('attribution_type').annotate(
        count=Count('id')
    )

    return {
        'new_patients': new_patient_count,
        'total_revenue': revenue,
        'total_ad_spend': ad_spend,
        'cost_per_new_patient': cost_per_new_patient,
        'appointments_completed': appointments_completed,
        'total_calls': total_calls,
        'calls_converted': calls_converted,
        'call_conversion_rate': round(call_conversion_rate, 1),
        'attribution_breakdown': list(attribution_breakdown),
    }


def get_campaign_performance(start_date: date, end_date: date, clinic=None) -> list:
    """
    Get campaign performance metrics.

    Returns list of dicts with:
    - campaign_name, source
    - spend, impressions, clicks, conversions
    - new_patients (attributed)
    - cost_per_patient
    """
    # Get spend by campaign
    filters = Q(date__gte=start_date, date__lte=end_date)
    if clinic:
        filters &= Q(campaign__clinic=clinic)

    campaign_stats = CampaignDailyStats.objects.filter(filters).values(
        'campaign__id',
        'campaign__name',
        'campaign__source',
    ).annotate(
        total_spend=Sum('spend'),
        total_impressions=Sum('impressions'),
        total_clicks=Sum('clicks'),
        total_conversions=Sum('conversions'),
    ).order_by('-total_spend')

    # Get attributed patients per campaign
    attr_filters = Q(
        created_at__date__gte=start_date,
        created_at__date__lte=end_date,
    )
    if clinic:
        attr_filters &= Q(clinic=clinic)

    attributions_by_campaign = {}
    for attr in Attribution.objects.filter(attr_filters).values('campaign_name').annotate(
        count=Count('id'),
        revenue=Sum('first_invoice_amount'),
    ):
        attributions_by_campaign[attr['campaign_name']] = {
            'patients': attr['count'],
            'revenue': attr['revenue'] or Decimal('0'),
        }

    # Combine data
    results = []
    for stat in campaign_stats:
        campaign_name = stat['campaign__name']
        spend = stat['total_spend'] or Decimal('0')
        attr_data = attributions_by_campaign.get(campaign_name, {'patients': 0, 'revenue': Decimal('0')})

        cost_per_patient = None
        if attr_data['patients'] > 0 and spend > 0:
            cost_per_patient = spend / attr_data['patients']

        results.append({
            'id': stat['campaign__id'],
            'name': campaign_name,
            'source': stat['campaign__source'],
            'spend': spend,
            'impressions': stat['total_impressions'] or 0,
            'clicks': stat['total_clicks'] or 0,
            'conversions': stat['total_conversions'] or 0,
            'new_patients': attr_data['patients'],
            'revenue': attr_data['revenue'],
            'cost_per_patient': cost_per_patient,
            'roas': (attr_data['revenue'] / spend) if spend > 0 else None,
        })

    return results


def calculate_cost_per_new_patient(start_date: date, end_date: date, clinic=None) -> Decimal:
    """
    Calculate cost per new patient for a date range.

    Formula:
    total_campaign_spend (Google + Meta APIs)
    ÷
    count(patients with first_paid_invoice in date range AND attribution.campaign_id)
    """
    # Get total ad spend
    spend_filters = Q(date__gte=start_date, date__lte=end_date)
    if clinic:
        spend_filters &= Q(campaign__clinic=clinic)

    total_spend = CampaignDailyStats.objects.filter(spend_filters).aggregate(
        total=Sum('spend')
    )['total'] or Decimal('0')

    # Get new patients with campaign attribution
    patient_filters = Q(
        first_paid_invoice_date__gte=start_date,
        first_paid_invoice_date__lte=end_date,
        attribution__campaign_name__isnull=False,
    ) & ~Q(attribution__campaign_name='')

    if clinic:
        patient_filters &= Q(clinic=clinic)

    attributed_patients = Patient.objects.filter(patient_filters).count()

    if attributed_patients == 0:
        return None

    return total_spend / attributed_patients
