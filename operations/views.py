"""
Views for operations - Task inbox, review requests, treatment plans.
"""

from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.utils import timezone

from .models import Task, ReviewRequest, TreatmentPlan


@login_required
def task_inbox(request):
    """
    Staff task inbox - priority queue of actionable items.
    HTMX-enabled for real-time updates.
    """
    tasks = Task.objects.filter(
        clinic__is_active=True,
        status__in=['pending', 'in_progress']
    ).select_related('patient', 'clinic', 'assigned_to').order_by('priority', '-created_at')

    # Filter by assigned user if specified
    if request.GET.get('mine'):
        tasks = tasks.filter(assigned_to=request.user)

    context = {
        'page_title': 'Task Inbox',
        'tasks': tasks[:50],
    }

    # Return partial for HTMX requests
    if request.headers.get('HX-Request'):
        return render(request, 'operations/partials/task_list.html', context)

    return render(request, 'operations/task_inbox.html', context)


@login_required
def task_detail(request, pk):
    """Task detail with patient context."""
    task = get_object_or_404(
        Task.objects.select_related('patient', 'clinic', 'assigned_to'),
        pk=pk
    )
    context = {
        'page_title': task.title,
        'task': task,
    }
    return render(request, 'operations/task_detail.html', context)


@login_required
def task_complete(request, pk):
    """
    Mark a task as completed.
    HTMX endpoint - returns updated task row.
    """
    task = get_object_or_404(Task, pk=pk)

    if request.method == 'POST':
        task.status = 'completed'
        task.completed_at = timezone.now()
        task.completed_by = request.user
        task.completion_notes = request.POST.get('notes', '')
        task.save()

        # Return empty response to remove from list, or updated row
        if request.headers.get('HX-Request'):
            return HttpResponse('')

    return render(request, 'operations/partials/task_row.html', {'task': task})


@login_required
def task_snooze(request, pk):
    """
    Snooze a task for later.
    HTMX endpoint.
    """
    from datetime import timedelta

    task = get_object_or_404(Task, pk=pk)

    if request.method == 'POST':
        hours = int(request.POST.get('hours', 1))
        task.status = 'snoozed'
        task.snoozed_until = timezone.now() + timedelta(hours=hours)
        task.save()

        if request.headers.get('HX-Request'):
            return HttpResponse('')

    return render(request, 'operations/partials/task_row.html', {'task': task})


@login_required
def review_list(request):
    """List of review requests."""
    reviews = ReviewRequest.objects.filter(
        clinic__is_active=True
    ).select_related('patient', 'clinic').order_by('-scheduled_at')

    context = {
        'page_title': 'Review Requests',
        'reviews': reviews[:50],
    }
    return render(request, 'operations/review_list.html', context)


@login_required
def review_detail(request, pk):
    """Review request detail."""
    review = get_object_or_404(
        ReviewRequest.objects.select_related('patient', 'clinic', 'appointment'),
        pk=pk
    )
    context = {
        'page_title': f'Review Request - {review.patient}',
        'review': review,
    }
    return render(request, 'operations/review_detail.html', context)


@login_required
def treatment_plan_list(request):
    """List of treatment plans."""
    plans = TreatmentPlan.objects.filter(
        clinic__is_active=True
    ).select_related('patient', 'clinic', 'created_by').order_by('-created_at')

    context = {
        'page_title': 'Treatment Plans',
        'plans': plans[:50],
    }
    return render(request, 'operations/treatment_plan_list.html', context)


@login_required
def treatment_plan_detail(request, pk):
    """Treatment plan detail."""
    plan = get_object_or_404(
        TreatmentPlan.objects.select_related('patient', 'clinic', 'created_by'),
        pk=pk
    )
    context = {
        'page_title': plan.title,
        'plan': plan,
    }
    return render(request, 'operations/treatment_plan_detail.html', context)
