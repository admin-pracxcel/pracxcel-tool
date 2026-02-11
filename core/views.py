"""
Views for core app - Dashboard, Patients, Attribution.
"""

from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required

from .models import Patient


@login_required
def dashboard(request):
    """Main dashboard view."""
    context = {
        'page_title': 'Dashboard',
    }
    return render(request, 'core/dashboard.html', context)


@login_required
def patient_list(request):
    """List all patients."""
    patients = Patient.objects.filter(clinic__is_active=True).select_related('clinic')
    context = {
        'page_title': 'Patients',
        'patients': patients,
    }
    return render(request, 'core/patient_list.html', context)


@login_required
def patient_detail(request, pk):
    """Patient detail view with appointments, invoices, and attribution."""
    patient = get_object_or_404(
        Patient.objects.select_related('clinic', 'attribution'),
        pk=pk
    )
    context = {
        'page_title': patient.full_name,
        'patient': patient,
        'appointments': patient.appointments.all()[:10],
        'invoices': patient.invoices.all()[:10],
    }
    return render(request, 'core/patient_detail.html', context)


@login_required
def patient_timeline(request, pk):
    """
    Patient timeline - HTMX partial for loading more events.
    """
    patient = get_object_or_404(Patient, pk=pk)
    offset = int(request.GET.get('offset', 0))
    limit = 20

    # Combine appointments and call events, sort by date
    # This is a simplified version - full implementation would use union queries
    appointments = patient.appointments.all()[offset:offset + limit]

    context = {
        'patient': patient,
        'appointments': appointments,
        'next_offset': offset + limit,
    }
    return render(request, 'core/partials/patient_timeline.html', context)


@login_required
def patient_attribution(request, pk):
    """View and edit patient attribution."""
    patient = get_object_or_404(
        Patient.objects.select_related('attribution'),
        pk=pk
    )

    if request.method == 'POST':
        # Handle manual attribution override
        # Implementation would go here
        pass

    context = {
        'page_title': f'Attribution - {patient.full_name}',
        'patient': patient,
    }
    return render(request, 'core/patient_attribution.html', context)
