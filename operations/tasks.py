"""
Celery tasks for generating operations tasks.

These run hourly via Celery Beat.
"""

import logging
from datetime import timedelta
from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task
def generate_missed_call_tasks():
    """
    Generate callback tasks for missed calls.

    A call is considered missed if:
    - Duration < 30 seconds
    - No appointment was booked
    - No existing pending task for this call
    """
    from core.models import Clinic
    from integrations.models import CallEvent
    from operations.models import Task

    clinics = Clinic.objects.filter(is_active=True)
    tasks_created = 0

    for clinic in clinics:
        # Find missed calls from the last 24 hours
        cutoff = timezone.now() - timedelta(hours=24)

        missed_calls = CallEvent.objects.filter(
            clinic=clinic,
            timestamp__gte=cutoff,
            duration_seconds__lt=30,
            resulted_in_appointment=False,
            is_processed=False,
        )

        for call in missed_calls:
            # Create idempotency key
            idempotency_key = f"callback_call_{call.call_sid}"

            # Check if task already exists
            if Task.objects.filter(idempotency_key=idempotency_key).exists():
                continue

            # Find patient by phone
            from core.models import Patient
            patient = Patient.objects.filter(
                clinic=clinic,
                phone=call.caller_phone
            ).first()

            if not patient:
                # Could create unknown patient or skip
                continue

            Task.objects.create(
                clinic=clinic,
                patient=patient,
                task_type='callback',
                title=f'Callback - Missed call from {call.caller_phone}',
                description=f'Missed call at {call.timestamp.strftime("%H:%M")}. Duration: {call.duration_seconds}s',
                priority=2,  # High priority
                source_type='call_event',
                source_id=call.id,
                idempotency_key=idempotency_key,
            )

            call.is_processed = True
            call.save(update_fields=['is_processed'])
            tasks_created += 1

    logger.info(f"Created {tasks_created} callback tasks")
    return tasks_created


@shared_task
def generate_review_request_tasks():
    """
    Generate review request tasks for completed appointments.

    Triggered 24 hours after appointment completion for patients who consented.
    """
    from core.models import Appointment
    from operations.models import ReviewRequest

    # Find appointments completed ~24 hours ago
    target_time = timezone.now() - timedelta(hours=24)
    window_start = target_time - timedelta(hours=1)
    window_end = target_time + timedelta(hours=1)

    appointments = Appointment.objects.filter(
        status='completed',
        clinic__is_active=True,
        scheduled_at__gte=window_start,
        scheduled_at__lte=window_end,
    ).select_related('patient', 'clinic')

    requests_created = 0

    for appt in appointments:
        patient = appt.patient

        # Check consent
        if not (patient.sms_consent or patient.email_consent):
            continue

        # Create idempotency key
        idempotency_key = f"review_{appt.cliniko_id}"

        # Check if already exists
        if ReviewRequest.objects.filter(idempotency_key=idempotency_key).exists():
            continue

        # Determine channel
        channel = 'sms' if patient.sms_consent else 'email'

        ReviewRequest.objects.create(
            clinic=appt.clinic,
            patient=patient,
            appointment=appt,
            channel=channel,
            scheduled_at=timezone.now(),
            idempotency_key=idempotency_key,
        )
        requests_created += 1

    logger.info(f"Created {requests_created} review requests")
    return requests_created


@shared_task
def generate_treatment_followup_tasks():
    """
    Generate follow-up tasks for treatment plans with no response.

    Triggered 7 days after treatment plan was sent.
    """
    from operations.models import Task, TreatmentPlan

    # Find treatment plans sent 7 days ago with no response
    target_date = timezone.now() - timedelta(days=7)
    window_start = target_date - timedelta(hours=12)
    window_end = target_date + timedelta(hours=12)

    plans = TreatmentPlan.objects.filter(
        status='sent',
        clinic__is_active=True,
        sent_at__gte=window_start,
        sent_at__lte=window_end,
    ).select_related('patient', 'clinic')

    tasks_created = 0

    for plan in plans:
        # Create idempotency key
        idempotency_key = f"treatment_followup_{plan.id}"

        # Check if already exists
        if Task.objects.filter(idempotency_key=idempotency_key).exists():
            continue

        Task.objects.create(
            clinic=plan.clinic,
            patient=plan.patient,
            task_type='treatment_followup',
            title=f'Follow up on treatment plan: {plan.title}',
            description=f'Treatment plan sent {plan.sent_at.strftime("%Y-%m-%d")} with no response.',
            priority=3,  # Normal priority
            source_type='treatment_plan',
            source_id=plan.id,
            idempotency_key=idempotency_key,
        )
        tasks_created += 1

    logger.info(f"Created {tasks_created} treatment follow-up tasks")
    return tasks_created


@shared_task
def generate_recall_tasks():
    """
    Generate recall tasks for patients who haven't visited in 6+ months.

    Runs monthly.
    """
    from core.models import Patient
    from operations.models import Task

    cutoff = timezone.now() - timedelta(days=180)

    patients = Patient.objects.filter(
        clinic__is_active=True,
        last_appointment_date__lt=cutoff.date(),
    ).select_related('clinic')

    tasks_created = 0

    for patient in patients:
        # Create monthly idempotency key
        month_key = timezone.now().strftime("%Y-%m")
        idempotency_key = f"recall_{patient.id}_{month_key}"

        if Task.objects.filter(idempotency_key=idempotency_key).exists():
            continue

        Task.objects.create(
            clinic=patient.clinic,
            patient=patient,
            task_type='recall',
            title=f'Recall: {patient.full_name}',
            description=f'Last visit: {patient.last_appointment_date}. Consider reaching out.',
            priority=4,  # Low priority
            idempotency_key=idempotency_key,
        )
        tasks_created += 1

    logger.info(f"Created {tasks_created} recall tasks")
    return tasks_created
