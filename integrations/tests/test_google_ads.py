import pytest
from unittest.mock import MagicMock, patch
from datetime import date
from integrations.services.google_ads import GoogleAdsClient

@patch('integrations.services.google_ads.LibGoogleAdsClient')
@patch('integrations.services.google_ads.Credentials')
def test_google_ads_client_init(mock_credentials, mock_lib_client):
    """Test initialization of GoogleAdsClient."""
    mock_lib_client.load_from_dict.return_value = MagicMock()
    
    client = GoogleAdsClient(
        access_token='fake_token',
        refresh_token='fake_refresh',
        customer_id='123-456-7890'
    )
    
    assert client.customer_id == '1234567890'
    mock_credentials.assert_called_once()
    mock_lib_client.assert_called_once()

@patch('integrations.services.google_ads.LibGoogleAdsClient')
@patch('integrations.services.google_ads.Credentials')
def test_get_campaigns(mock_credentials, mock_lib_client):
    """Test get_campaigns method."""
    mock_ga_service = MagicMock()
    mock_client_instance = MagicMock()
    mock_client_instance.get_service.return_value = mock_ga_service
    mock_lib_client.return_value = mock_client_instance
    
    # Mock stream response
    mock_row = MagicMock()
    mock_row.campaign.id = 123
    mock_row.campaign.name = 'Test Campaign'
    mock_row.campaign.status.name = 'ENABLED'
    
    mock_batch = MagicMock()
    mock_batch.results = [mock_row]
    
    mock_ga_service.search_stream.return_value = [mock_batch]
    
    client = GoogleAdsClient(
        access_token='fake_token',
        refresh_token='fake_refresh',
        customer_id='123-456-7890'
    )
    
    campaigns = client.get_campaigns()
    
    assert len(campaigns) == 1
    assert campaigns[0]['id'] == '123'
    assert campaigns[0]['name'] == 'Test Campaign'
    assert campaigns[0]['status'] == 'ENABLED'

@patch('integrations.services.google_ads.LibGoogleAdsClient')
@patch('integrations.services.google_ads.Credentials')
def test_get_campaign_metrics(mock_credentials, mock_lib_client):
    """Test get_campaign_metrics method."""
    mock_ga_service = MagicMock()
    mock_client_instance = MagicMock()
    mock_client_instance.get_service.return_value = mock_ga_service
    mock_lib_client.return_value = mock_client_instance
    
    # Mock stream response
    mock_row = MagicMock()
    mock_row.campaign.id = 123
    mock_row.campaign.name = 'Test Campaign'
    mock_row.campaign.status.name = 'ENABLED'
    mock_row.segments.date = '2023-10-27'
    mock_row.metrics.cost_micros = 1000000
    mock_row.metrics.impressions = 100
    mock_row.metrics.clicks = 10
    mock_row.metrics.conversions = 1
    
    mock_batch = MagicMock()
    mock_batch.results = [mock_row]
    
    mock_ga_service.search_stream.return_value = [mock_batch]
    
    client = GoogleAdsClient(
        access_token='fake_token',
        refresh_token='fake_refresh',
        customer_id='123-456-7890'
    )
    
    metrics = client.get_campaign_metrics(date(2023, 10, 20), date(2023, 10, 27))
    
    assert len(metrics) == 1
    campaign = metrics[0]
    assert campaign['id'] == '123'
    assert len(campaign['daily_metrics']) == 1
    daily = campaign['daily_metrics'][0]
    assert daily['date'] == '2023-10-27'
    assert daily['cost_micros'] == 1000000
