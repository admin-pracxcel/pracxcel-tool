"""
Pytest configuration and fixtures.
"""

import pytest
from django.contrib.auth import get_user_model

User = get_user_model()


@pytest.fixture
def user(db):
    """Create a test user."""
    return User.objects.create_user(
        username='testuser',
        email='test@example.com',
        password='testpass123'
    )


@pytest.fixture
def authenticated_client(client, user):
    """Return a client with an authenticated user."""
    client.force_login(user)
    return client


@pytest.fixture
def clinic(db):
    """Create a test clinic."""
    from core.models import Clinic
    return Clinic.objects.create(
        name='Test Clinic',
        is_active=True
    )


@pytest.fixture
def patient(db, clinic):
    """Create a test patient."""
    from core.models import Patient
    return Patient.objects.create(
        clinic=clinic,
        cliniko_id='12345',
        first_name='John',
        last_name='Doe',
        email='john@example.com',
        phone='+1234567890'
    )


@pytest.fixture
def appointment(db, clinic, patient):
    """Create a test appointment."""
    from core.models import Appointment
    from django.utils import timezone
    return Appointment.objects.create(
        clinic=clinic,
        patient=patient,
        cliniko_id='appt123',
        scheduled_at=timezone.now(),
        status='scheduled'
    )


@pytest.fixture
def invoice(db, clinic, patient):
    """Create a test invoice."""
    from core.models import Invoice
    from django.utils import timezone
    from decimal import Decimal
    return Invoice.objects.create(
        clinic=clinic,
        patient=patient,
        cliniko_id='inv123',
        invoice_number='INV-001',
        status='paid',
        total_amount=Decimal('500.00'),
        paid_at=timezone.now()
    )
