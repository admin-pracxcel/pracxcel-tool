"""
Cliniko API client.

API Documentation: https://docs.api.cliniko.com/
Sharding guide: https://docs.api.cliniko.com/guides/urls

Base URL: https://api.{shard}.cliniko.com/v1
Shard is embedded in the API key (suffix after last hyphen, e.g. "...key-au2" → shard "au2").
Keys without a shard suffix default to "au1".
"""

import re
import requests
import logging
from typing import Optional
from datetime import datetime

logger = logging.getLogger(__name__)

BASE_URL = "https://api.{shard}.cliniko.com/v1"


def extract_shard_from_key(api_key: str) -> str:
    """
    Extract the shard from a Cliniko API key.
    Modern keys end with the shard suffix (e.g., "-au2", "-uk1").
    If no shard suffix is found, defaults to "au1".
    """
    match = re.search(r'-([a-z]{2}\d+)$', api_key)
    if match:
        return match.group(1)
    return 'au1'


class ClinikoClient:
    """
    Client for Cliniko API.

    Usage:
        client = ClinikoClient(api_key='xxx-au2')
        patients = client.get_patients()

    The shard is auto-detected from the API key. You can override it
    by passing shard explicitly.
    """

    def __init__(self, api_key: str, shard: Optional[str] = None):
        self.api_key = api_key
        self.shard = shard or extract_shard_from_key(api_key)
        self.base_url = BASE_URL.format(shard=self.shard)
        self.session = requests.Session()
        self.session.headers.update({
            'Accept': 'application/json',
            'User-Agent': 'Pracxcel (support@pracxcel.com)',
        })
        self.session.auth = (self.api_key, '')

    def _request(self, method: str, endpoint: str, **kwargs) -> dict:
        """Make an API request."""
        url = f"{self.base_url}/{endpoint}"

        try:
            response = self.session.request(method, url, **kwargs)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Cliniko API error: {e}")
            raise

    def get_patients(
        self,
        since_cursor: Optional[str] = None,
        updated_since: Optional[datetime] = None,
        per_page: int = 100
    ) -> dict:
        """
        Get patients with optional filtering.

        Args:
            since_cursor: Cursor for pagination
            updated_since: Only get patients updated after this time
            per_page: Number of results per page (max 100)

        Returns:
            Dict with 'patients' list and 'next_cursor'
        """
        params = {'per_page': per_page}

        if updated_since:
            params['updated_at'] = f">={updated_since.isoformat()}"

        if since_cursor:
            params['page'] = since_cursor

        data = self._request('GET', 'patients', params=params)

        return {
            'patients': data.get('patients', []),
            'next_cursor': data.get('links', {}).get('next'),
            'total_entries': data.get('total_entries', 0),
        }

    def get_patient(self, patient_id: str) -> dict:
        """Get a single patient by ID."""
        return self._request('GET', f'patients/{patient_id}')

    def get_appointments(
        self,
        patient_id: Optional[str] = None,
        updated_since: Optional[datetime] = None,
        per_page: int = 100
    ) -> dict:
        """
        Get appointments with optional filtering.
        """
        params = {'per_page': per_page}

        if patient_id:
            params['patient_id'] = patient_id

        if updated_since:
            params['updated_at'] = f">={updated_since.isoformat()}"

        data = self._request('GET', 'appointments', params=params)

        return {
            'appointments': data.get('appointments', []),
            'next_cursor': data.get('links', {}).get('next'),
        }

    def get_invoices(
        self,
        patient_id: Optional[str] = None,
        updated_since: Optional[datetime] = None,
        per_page: int = 100
    ) -> dict:
        """
        Get invoices with optional filtering.
        """
        params = {'per_page': per_page}

        if patient_id:
            params['patient_id'] = patient_id

        if updated_since:
            params['updated_at'] = f">={updated_since.isoformat()}"

        data = self._request('GET', 'invoices', params=params)

        return {
            'invoices': data.get('invoices', []),
            'next_cursor': data.get('links', {}).get('next'),
        }
