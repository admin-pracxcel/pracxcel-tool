"""
Analytics views - Dashboard and reports.
"""

from datetime import date, timedelta
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.db.models import Sum, Count, Avg

from .services import get_dashboard_metrics, get_campaign_performance


@login_required
def dashboard(request):
    """
    Main analytics dashboard.
    Shows key metrics with date range selector.
    """
    # Default to last 30 days
    end_date = date.today()
    start_date = end_date - timedelta(days=30)

    # Parse date range from request
    if request.GET.get('start'):
        try:
            start_date = date.fromisoformat(request.GET['start'])
        except ValueError:
            pass
    if request.GET.get('end'):
        try:
            end_date = date.fromisoformat(request.GET['end'])
        except ValueError:
            pass

    metrics = get_dashboard_metrics(start_date, end_date)

    context = {
        'page_title': 'Analytics Dashboard',
        'start_date': start_date,
        'end_date': end_date,
        'metrics': metrics,
    }
    return render(request, 'analytics/dashboard.html', context)


@login_required
def campaign_report(request):
    """
    Campaign performance report.
    Shows spend, conversions, and cost-per-patient by campaign.
    """
    end_date = date.today()
    start_date = end_date - timedelta(days=30)

    if request.GET.get('start'):
        try:
            start_date = date.fromisoformat(request.GET['start'])
        except ValueError:
            pass
    if request.GET.get('end'):
        try:
            end_date = date.fromisoformat(request.GET['end'])
        except ValueError:
            pass

    campaigns = get_campaign_performance(start_date, end_date)

    context = {
        'page_title': 'Campaign Performance',
        'start_date': start_date,
        'end_date': end_date,
        'campaigns': campaigns,
    }
    return render(request, 'analytics/campaign_report.html', context)


@login_required
def attribution_report(request):
    """
    Attribution breakdown report.
    Shows how patients are being attributed to marketing sources.
    """
    from core.models import Attribution

    end_date = date.today()
    start_date = end_date - timedelta(days=30)

    attributions = Attribution.objects.filter(
        created_at__date__gte=start_date,
        created_at__date__lte=end_date,
    ).values('attribution_type', 'campaign_source').annotate(
        count=Count('id'),
        total_revenue=Sum('first_invoice_amount'),
    ).order_by('-count')

    context = {
        'page_title': 'Attribution Report',
        'start_date': start_date,
        'end_date': end_date,
        'attributions': attributions,
    }
    return render(request, 'analytics/attribution_report.html', context)


@login_required
def metrics_api(request):
    """
    API endpoint for dashboard chart data.
    Returns JSON for Chart.js.
    """
    from .models import DailyMetrics

    end_date = date.today()
    start_date = end_date - timedelta(days=30)

    if request.GET.get('start'):
        try:
            start_date = date.fromisoformat(request.GET['start'])
        except ValueError:
            pass
    if request.GET.get('end'):
        try:
            end_date = date.fromisoformat(request.GET['end'])
        except ValueError:
            pass

    metrics = DailyMetrics.objects.filter(
        date__gte=start_date,
        date__lte=end_date,
    ).order_by('date')

    data = {
        'labels': [m.date.isoformat() for m in metrics],
        'datasets': {
            'new_patients': [m.new_patients for m in metrics],
            'revenue': [float(m.revenue_total) for m in metrics],
            'ad_spend': [float(m.total_ad_spend) for m in metrics],
            'appointments': [m.appointments_completed for m in metrics],
        }
    }

    return JsonResponse(data)
