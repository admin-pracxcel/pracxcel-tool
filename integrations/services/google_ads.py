"""
Google Ads API client.

API Documentation: https://developers.google.com/google-ads/api/docs/start

Uses OAuth2 with refresh tokens.
Rate limit: 15k requests/day per developer token.
"""

import logging
from datetime import date
from typing import List, Optional

from google.ads.googleads.client import GoogleAdsClient as LibGoogleAdsClient
from google.oauth2.credentials import Credentials
from django.conf import settings

logger = logging.getLogger(__name__)


class GoogleAdsClient:
    """
    Client for Google Ads API.

    Usage:
        client = GoogleAdsClient(
            access_token='xxx',
            refresh_token='xxx',
            customer_id='123-456-7890'
        )
        campaigns = client.get_campaigns()
    """

    def __init__(
        self,
        access_token: str,
        refresh_token: str,
        customer_id: str,
        developer_token: Optional[str] = None
    ):
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.customer_id = customer_id.replace('-', '')
        self.developer_token = developer_token or settings.GOOGLE_ADS_DEVELOPER_TOKEN

        self.credentials = Credentials(
            token=access_token,
            refresh_token=refresh_token,
            client_id=settings.GOOGLE_ADS_CLIENT_ID,
            client_secret=settings.GOOGLE_ADS_CLIENT_SECRET,
            token_uri="https://oauth2.googleapis.com/token",
        )

        try:
            self.client = LibGoogleAdsClient(
                credentials=self.credentials,
                developer_token=self.developer_token,
            )
        except Exception as e:
            logger.error(f"Failed to initialize Google Ads client: {e}")
            raise

    def get_campaigns(self) -> List[dict]:
        """
        Get all campaigns for the account.

        Returns:
            List of campaign dicts with id, name, status
        """
        ga_service = self.client.get_service("GoogleAdsService")

        query = """
            SELECT
                campaign.id,
                campaign.name,
                campaign.status
            FROM campaign
        """

        try:
            stream = ga_service.search_stream(
                customer_id=self.customer_id,
                query=query,
            )

            campaigns = []
            for batch in stream:
                for row in batch.results:
                    campaigns.append({
                        'id': str(row.campaign.id),
                        'name': row.campaign.name,
                        'status': row.campaign.status.name
                    })

            return campaigns
        except Exception as e:
            logger.error(f"Error fetching campaigns: {e}")
            return []

    def get_campaign_metrics(
        self,
        start_date: date,
        end_date: date
    ) -> List[dict]:
        """
        Get campaign performance metrics for a date range.

        Args:
            start_date: Start of date range
            end_date: End of date range

        Returns:
            List of campaign dicts with metrics and daily_metrics
        """
        ga_service = self.client.get_service("GoogleAdsService")

        # Query to get campaign details + metrics segmented by date
        # Note: All metrics must be compatible with segments.date
        query = f"""
            SELECT
                campaign.id,
                campaign.name,
                campaign.status,
                segments.date,
                metrics.cost_micros,
                metrics.impressions,
                metrics.clicks,
                metrics.conversions
            FROM campaign
            WHERE segments.date BETWEEN '{start_date}' AND '{end_date}'
            ORDER BY segments.date ASC
        """

        try:
            # We need to construct the request manually or use kwargs, search_stream takes customer_id and query
            stream = ga_service.search_stream(
                customer_id=self.customer_id,
                query=query,
            )

            campaigns_map = {}

            for batch in stream:
                for row in batch.results:
                    campaign_id = row.campaign.id

                    if campaign_id not in campaigns_map:
                        campaigns_map[campaign_id] = {
                            'id': str(campaign_id),
                            'name': row.campaign.name,
                            'status': row.campaign.status.name,
                            'daily_metrics': []
                        }

                    campaigns_map[campaign_id]['daily_metrics'].append({
                        'date': row.segments.date,  # Returns 'YYYY-MM-DD'
                        'cost_micros': row.metrics.cost_micros,
                        'impressions': row.metrics.impressions,
                        'clicks': row.metrics.clicks,
                        'conversions': row.metrics.conversions
                    })

            return list(campaigns_map.values())
        except Exception as e:
            logger.error(f"Error fetching campaign metrics: {e}")
            return []

    def get_conversion_actions(self) -> List[dict]:
        """Get all conversion actions for the account."""
        ga_service = self.client.get_service("GoogleAdsService")

        query = """
            SELECT
                conversion_action.id,
                conversion_action.name,
                conversion_action.status,
                conversion_action.type
            FROM conversion_action
        """

        try:
            stream = ga_service.search_stream(
                customer_id=self.customer_id,
                query=query,
            )

            actions = []
            for batch in stream:
                for row in batch.results:
                    actions.append({
                        'id': str(row.conversion_action.id),
                        'name': row.conversion_action.name,
                        'status': row.conversion_action.status.name,
                        'type': row.conversion_action.type_.name
                    })
            return actions
        except Exception as e:
            logger.error(f"Error fetching conversion actions: {e}")
            return []