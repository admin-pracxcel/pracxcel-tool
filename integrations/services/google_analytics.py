"""
Google Analytics 4 Data API client.

API Documentation: https://developers.google.com/analytics/devguides/reporting/data/v1

Uses OAuth2 authentication — users sign in with their Google account
and grant analytics read access. No service account setup required.
"""

import logging
from datetime import date, datetime
from typing import List, Optional
from urllib.parse import urlencode

import requests
from django.conf import settings
from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import (
    DateRange,
    Dimension,
    Metric,
    RunReportRequest,
    RunReportResponse,
)
from google.oauth2.credentials import Credentials

logger = logging.getLogger(__name__)

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GA4_ADMIN_API_URL = "https://analyticsadmin.googleapis.com/v1beta/accountSummaries"

SCOPES = [
    "https://www.googleapis.com/auth/analytics.readonly",
]


def build_oauth_url(redirect_uri: str, state: str = "") -> str:
    """
    Build the Google OAuth authorization URL.

    Args:
        redirect_uri: The callback URL Google redirects to after consent.
        state: Optional CSRF state parameter.

    Returns:
        The full authorization URL to redirect the user to.
    """
    params = {
        "client_id": settings.GOOGLE_OAUTH_CLIENT_ID,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": " ".join(SCOPES),
        "access_type": "offline",
        "prompt": "consent",
    }
    if state:
        params["state"] = state
    return f"{GOOGLE_AUTH_URL}?{urlencode(params)}"


def exchange_code(code: str, redirect_uri: str) -> dict:
    """
    Exchange an authorization code for access + refresh tokens.

    Args:
        code: The authorization code from Google's callback.
        redirect_uri: Must match the redirect_uri used in the auth URL.

    Returns:
        Dict with 'access_token', 'refresh_token', 'expires_in'.

    Raises:
        ValueError: If the token exchange fails.
    """
    resp = requests.post(GOOGLE_TOKEN_URL, data={
        "code": code,
        "client_id": settings.GOOGLE_OAUTH_CLIENT_ID,
        "client_secret": settings.GOOGLE_OAUTH_CLIENT_SECRET,
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code",
    }, timeout=15)

    data = resp.json()
    if "error" in data:
        raise ValueError(f"Token exchange failed: {data['error_description']}")

    return {
        "access_token": data["access_token"],
        "refresh_token": data.get("refresh_token", ""),
        "expires_in": data.get("expires_in", 3600),
    }


def refresh_access_token(refresh_token: str) -> dict:
    """
    Refresh an expired access token.

    Args:
        refresh_token: The stored refresh token.

    Returns:
        Dict with 'access_token' and 'expires_in'.

    Raises:
        ValueError: If the refresh fails.
    """
    resp = requests.post(GOOGLE_TOKEN_URL, data={
        "refresh_token": refresh_token,
        "client_id": settings.GOOGLE_OAUTH_CLIENT_ID,
        "client_secret": settings.GOOGLE_OAUTH_CLIENT_SECRET,
        "grant_type": "refresh_token",
    }, timeout=15)

    data = resp.json()
    if "error" in data:
        raise ValueError(f"Token refresh failed: {data.get('error_description', data['error'])}")

    return {
        "access_token": data["access_token"],
        "expires_in": data.get("expires_in", 3600),
    }


def list_ga4_properties(access_token: str) -> List[dict]:
    """
    List GA4 properties the user has access to via the Admin API.

    Args:
        access_token: A valid OAuth access token.

    Returns:
        List of dicts with 'account', 'account_name', 'property_id', 'property_name'.
    """
    properties = []
    page_token = None

    while True:
        params = {}
        if page_token:
            params["pageToken"] = page_token

        resp = requests.get(
            GA4_ADMIN_API_URL,
            headers={"Authorization": f"Bearer {access_token}"},
            params=params,
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()

        for account_summary in data.get("accountSummaries", []):
            account_name = account_summary.get("displayName", "Unknown Account")
            for prop in account_summary.get("propertySummaries", []):
                # property name is "properties/123456789"
                prop_resource = prop.get("property", "")
                prop_id = prop_resource.replace("properties/", "")
                properties.append({
                    "account": account_summary.get("account", ""),
                    "account_name": account_name,
                    "property_id": prop_id,
                    "property_name": prop.get("displayName", prop_id),
                })

        page_token = data.get("nextPageToken")
        if not page_token:
            break

    return properties


class GA4Client:
    """
    Client for Google Analytics 4 Data API.

    Usage:
        client = GA4Client(
            access_token='ya29.xxx',
            property_id='123456789'
        )
        client.test_connection()
        sessions = client.get_session_report(start_date, end_date)
    """

    def __init__(self, access_token: str, property_id: str):
        self.property_id = property_id
        self.credentials = Credentials(token=access_token)
        self.client = BetaAnalyticsDataClient(credentials=self.credentials)

    def test_connection(self) -> dict:
        """
        Test the connection by running a minimal report.
        Returns dict with 'sessions' count if successful.
        Raises exception on failure.
        """
        request = RunReportRequest(
            property=f"properties/{self.property_id}",
            date_ranges=[DateRange(start_date="7daysAgo", end_date="today")],
            metrics=[Metric(name="sessions")],
            limit=1,
        )

        response = self.client.run_report(request)

        total_sessions = 0
        if response.rows:
            total_sessions = int(response.rows[0].metric_values[0].value)

        return {
            'sessions_last_7_days': total_sessions,
            'property_id': self.property_id,
        }

    def get_session_report(
        self,
        start_date: date,
        end_date: date,
        limit: int = 10000,
    ) -> List[dict]:
        """
        Fetch session data grouped by source/medium/campaign/landing page/date.

        Args:
            start_date: Start of date range
            end_date: End of date range
            limit: Max rows to return

        Returns:
            List of dicts with keys matching MarketingTouch fields:
            - date, utm_source, utm_medium, utm_campaign,
              utm_content, landing_page, sessions
        """
        request = RunReportRequest(
            property=f"properties/{self.property_id}",
            date_ranges=[DateRange(
                start_date=start_date.isoformat(),
                end_date=end_date.isoformat(),
            )],
            dimensions=[
                Dimension(name="date"),
                Dimension(name="sessionSource"),
                Dimension(name="sessionMedium"),
                Dimension(name="sessionCampaignName"),
                Dimension(name="sessionManualAdContent"),
                Dimension(name="landingPage"),
            ],
            metrics=[
                Metric(name="sessions"),
            ],
            limit=limit,
        )

        response = self.client.run_report(request)
        return self._parse_report(response)

    def _parse_report(self, response: RunReportResponse) -> List[dict]:
        """Parse GA4 report response into a list of dicts."""
        results = []

        for row in response.rows:
            dims = row.dimension_values
            metrics = row.metric_values

            # Parse date from YYYYMMDD format
            date_str = dims[0].value
            try:
                row_date = datetime.strptime(date_str, "%Y%m%d").date()
            except ValueError:
                logger.warning(f"Could not parse GA4 date: {date_str}")
                continue

            utm_source = dims[1].value if dims[1].value != "(not set)" else ""
            utm_medium = dims[2].value if dims[2].value != "(not set)" else ""
            utm_campaign = dims[3].value if dims[3].value != "(not set)" else ""
            utm_content = dims[4].value if dims[4].value != "(not set)" else ""
            landing_page = dims[5].value if dims[5].value != "(not set)" else ""

            sessions = int(metrics[0].value)

            # Skip rows with no meaningful source info
            if not utm_source and not utm_medium and not landing_page:
                continue

            results.append({
                'date': row_date,
                'utm_source': utm_source,
                'utm_medium': utm_medium,
                'utm_campaign': utm_campaign,
                'utm_content': utm_content,
                'landing_page': landing_page,
                'sessions': sessions,
            })

        logger.info(f"Parsed {len(results)} rows from GA4 report")
        return results
