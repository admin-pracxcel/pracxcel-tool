"""
Meta (Facebook) Ads API client.

API Documentation: https://developers.facebook.com/docs/marketing-apis/

Uses OAuth2 with long-lived tokens (60-day expiry, auto-refresh).
Rate limit: 200 calls/hour per user.
"""

import requests
import logging
from datetime import date
from typing import List, Optional

logger = logging.getLogger(__name__)

GRAPH_API_VERSION = 'v18.0'
BASE_URL = f'https://graph.facebook.com/{GRAPH_API_VERSION}'


class MetaAdsClient:
    """
    Client for Meta Marketing API.

    Usage:
        client = MetaAdsClient(
            access_token='xxx',
            ad_account_id='act_123456789'
        )
        campaigns = client.get_campaigns()
    """

    def __init__(self, access_token: str, ad_account_id: str):
        self.access_token = access_token
        self.ad_account_id = ad_account_id
        self.session = requests.Session()

    def _request(self, method: str, endpoint: str, **kwargs) -> dict:
        """Make an API request."""
        url = f"{BASE_URL}/{endpoint}"

        params = kwargs.get('params', {})
        params['access_token'] = self.access_token
        kwargs['params'] = params

        try:
            response = self.session.request(method, url, **kwargs)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Meta Ads API error: {e}")
            raise

    def get_campaigns(self) -> List[dict]:
        """
        Get all campaigns for the ad account.

        Returns:
            List of campaign dicts with id, name, status
        """
        endpoint = f"{self.ad_account_id}/campaigns"
        params = {
            'fields': 'id,name,status,objective,created_time',
            'limit': 500,
        }

        data = self._request('GET', endpoint, params=params)
        return data.get('data', [])

    def get_campaign_insights(
        self,
        start_date: date,
        end_date: date,
        campaign_ids: Optional[List[str]] = None
    ) -> List[dict]:
        """
        Get campaign insights for a date range.

        Args:
            start_date: Start of date range
            end_date: End of date range
            campaign_ids: Optional list of specific campaign IDs

        Returns:
            List of campaign dicts with daily metrics
        """
        endpoint = f"{self.ad_account_id}/insights"
        params = {
            'fields': 'campaign_id,campaign_name,impressions,clicks,spend,actions',
            'time_range': f'{{"since":"{start_date}","until":"{end_date}"}}',
            'time_increment': 1,  # Daily breakdown
            'level': 'campaign',
            'limit': 500,
        }

        if campaign_ids:
            params['filtering'] = f'[{{"field":"campaign.id","operator":"IN","value":{campaign_ids}}}]'

        data = self._request('GET', endpoint, params=params)

        # Group by campaign and add daily_metrics
        campaigns = {}
        for row in data.get('data', []):
            campaign_id = row['campaign_id']
            if campaign_id not in campaigns:
                campaigns[campaign_id] = {
                    'id': campaign_id,
                    'name': row['campaign_name'],
                    'status': 'ACTIVE',  # Would need separate call to get status
                    'daily_metrics': []
                }

            campaigns[campaign_id]['daily_metrics'].append({
                'date': row.get('date_start'),
                'impressions': int(row.get('impressions', 0)),
                'clicks': int(row.get('clicks', 0)),
                'spend': float(row.get('spend', 0)),
                'conversions': self._extract_conversions(row.get('actions', [])),
            })

        return list(campaigns.values())

    def _extract_conversions(self, actions: List[dict]) -> int:
        """Extract conversion count from actions array."""
        for action in actions:
            if action.get('action_type') in ['purchase', 'lead', 'complete_registration']:
                return int(action.get('value', 0))
        return 0

    def exchange_token(self, short_lived_token: str, app_id: str, app_secret: str) -> dict:
        """
        Exchange short-lived token for long-lived token.

        Returns:
            Dict with access_token and expires_in
        """
        endpoint = 'oauth/access_token'
        params = {
            'grant_type': 'fb_exchange_token',
            'client_id': app_id,
            'client_secret': app_secret,
            'fb_exchange_token': short_lived_token,
        }

        return self._request('GET', endpoint, params=params)
