"""
Nexla-integrated weather data pipeline.

This module provides weather data through Nexla's data platform,
with automatic fallback to direct Open-Meteo API calls.

Setup:
    1. Sign up at https://express.dev (free)
    2. Create a Service Key: Settings > Authentication > Create Service Key
    3. Set environment variable: export NEXLA_SERVICE_KEY="your_key"
    4. Create a REST API connector to Open-Meteo (see setup_nexla_pipeline() below)

For the hackathon: Even if you only set up the Nexla pipeline via the UI
and use the SDK to read from it, that demonstrates genuine Nexla integration.
"""

import os
import json
import logging
from typing import Optional

import requests

# Direct Open-Meteo fallback
from weather_openmeteo import (
    get_current_weather as _direct_current,
    get_forecast as _direct_forecast,
    get_hourly_forecast as _direct_hourly,
    get_historical_summary as _direct_history,
    get_all_sf_current as _direct_all_sf,
    SF_LOCATIONS,
)

logger = logging.getLogger(__name__)

# --- Nexla Configuration ---

NEXLA_SERVICE_KEY = os.environ.get("NEXLA_SERVICE_KEY", "")
NEXLA_API_URL = os.environ.get("NEXLA_API_URL", "https://api.nexla.io")
NEXLA_NEXSET_ID = os.environ.get("NEXLA_NEXSET_ID", "")  # Set after creating pipeline


def _get_nexla_client():
    """
    Initialize and return a NexlaClient instance.
    Returns None if nexla-sdk is not installed or credentials are missing.
    """
    if not NEXLA_SERVICE_KEY:
        logger.info("NEXLA_SERVICE_KEY not set, will use direct API fallback")
        return None

    try:
        from nexla_sdk import NexlaClient
        return NexlaClient(service_key=NEXLA_SERVICE_KEY)
    except ImportError:
        logger.warning(
            "nexla-sdk not installed. Install with: pip install nexla-sdk"
        )
        return None
    except Exception as e:
        logger.warning(f"Failed to initialize NexlaClient: {e}")
        return None


def _fetch_from_nexla(nexset_id: str, count: int = 10) -> Optional[list]:
    """
    Fetch weather data samples from a Nexla Nexset.

    Args:
        nexset_id: The Nexset ID containing weather data
        count: Number of samples to retrieve

    Returns:
        List of data records, or None if Nexla is unavailable.
    """
    client = _get_nexla_client()
    if not client:
        return None

    try:
        samples = client.nexsets.get_samples(
            set_id=int(nexset_id),
            count=count,
            include_metadata=True,
        )
        logger.info(f"Retrieved {len(samples)} records from Nexla Nexset {nexset_id}")
        return samples
    except Exception as e:
        logger.warning(f"Nexla fetch failed: {e}")
        return None


def _fetch_from_nexla_api(nexset_id: str, count: int = 10) -> Optional[list]:
    """
    Fetch data from Nexla using the REST API directly (no SDK needed).

    This is an alternative if you don't want to install nexla-sdk
    but still want to pull data from your Nexla pipeline.
    """
    if not NEXLA_SERVICE_KEY:
        return None

    # First, exchange service key for access token
    try:
        token_resp = requests.post(
            f"{NEXLA_API_URL}/session/service_key",
            json={"service_key": NEXLA_SERVICE_KEY},
            headers={"Accept": "application/vnd.nexla.api.v1+json"},
            timeout=10,
        )
        token_resp.raise_for_status()
        access_token = token_resp.json().get("access_token")
        if not access_token:
            logger.warning("No access_token in Nexla response")
            return None
    except Exception as e:
        logger.warning(f"Nexla auth failed: {e}")
        return None

    # Fetch samples from the nexset
    try:
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/vnd.nexla.api.v1+json",
        }
        sample_resp = requests.get(
            f"{NEXLA_API_URL}/data_sets/{nexset_id}/samples",
            params={"count": count},
            headers=headers,
            timeout=15,
        )
        sample_resp.raise_for_status()
        return sample_resp.json()
    except Exception as e:
        logger.warning(f"Nexla data fetch failed: {e}")
        return None


# --- Public API (with Nexla-first, fallback to direct) ---


def get_current_weather(
    location_key: str = "downtown",
    units: str = "imperial",
    use_nexla: bool = True,
) -> dict:
    """
    Get current weather, trying Nexla first, falling back to Open-Meteo.

    The 'source' field in the response tells you where the data came from.
    """
    if use_nexla and NEXLA_NEXSET_ID:
        data = _fetch_from_nexla(NEXLA_NEXSET_ID, count=1)
        if data:
            return {
                "source": "nexla",
                "nexset_id": NEXLA_NEXSET_ID,
                "data": data[0] if data else {},
            }

    result = _direct_current(location_key=location_key, units=units)
    result["source"] = "open-meteo-direct"
    return result


def get_forecast(
    location_key: str = "downtown",
    days: int = 7,
    units: str = "imperial",
    use_nexla: bool = True,
) -> dict:
    """Get forecast, trying Nexla first."""
    if use_nexla and NEXLA_NEXSET_ID:
        data = _fetch_from_nexla(NEXLA_NEXSET_ID, count=days)
        if data:
            return {
                "source": "nexla",
                "nexset_id": NEXLA_NEXSET_ID,
                "data": data,
            }

    result = _direct_forecast(location_key=location_key, days=days, units=units)
    result["source"] = "open-meteo-direct"
    return result


def get_hourly_forecast(
    location_key: str = "downtown",
    hours: int = 24,
    units: str = "imperial",
) -> dict:
    """Hourly forecast (direct API only -- Nexla pipeline typically does daily)."""
    result = _direct_hourly(location_key=location_key, hours=hours, units=units)
    result["source"] = "open-meteo-direct"
    return result


def get_historical_summary(
    location_key: str = "downtown",
    past_days: int = 30,
) -> dict:
    """Historical weather summary (direct API only)."""
    result = _direct_history(location_key=location_key, past_days=past_days)
    result["source"] = "open-meteo-direct"
    return result


def get_pipeline_status() -> dict:
    """
    Check the status of the Nexla pipeline.
    Useful for the demo to show the pipeline is active.
    """
    client = _get_nexla_client()
    if not client:
        return {
            "nexla_available": False,
            "reason": "SDK not installed or service key not set",
            "fallback": "open-meteo-direct",
        }

    try:
        flows = client.flows.list()
        flow_list = []
        for flow_response in flows:
            for flow in flow_response.flows:
                flow_list.append({
                    "id": flow.id,
                    "name": flow.name,
                })

        return {
            "nexla_available": True,
            "flows": flow_list,
            "nexset_id": NEXLA_NEXSET_ID or "not configured",
        }
    except Exception as e:
        return {
            "nexla_available": False,
            "reason": str(e),
            "fallback": "open-meteo-direct",
        }


# --- Express.dev Pipeline Setup Guide ---


def print_setup_guide():
    """Print step-by-step instructions for setting up the Nexla pipeline."""
    guide = """
    ============================================================
    NEXLA EXPRESS.DEV PIPELINE SETUP (< 5 minutes)
    ============================================================

    OPTION A: Express.dev Natural Language (Fastest)
    ------------------------------------------------
    1. Go to https://express.dev and sign up (free)
    2. In the prompt box, type:
       "Create a REST API source that fetches weather data from
        https://api.open-meteo.com/v1/forecast with parameters
        latitude=37.7749, longitude=-122.4194, daily variables
        temperature_2m_max, temperature_2m_min, precipitation_sum,
        sunrise, sunset, uv_index_max, and timezone=America/Los_Angeles"
    3. Express will auto-generate the pipeline
    4. Activate the flow

    OPTION B: Manual Setup via Nexla UI
    ------------------------------------
    1. Log in at https://dataops.nexla.io (or your instance)
    2. Go to Integrate > New Data Flow
    3. Select "FlexFlow" as flow type
    4. Choose the "REST API (Universal)" connector
    5. Skip credentials (Open-Meteo needs no auth)
    6. Configure source:
       - Method: GET
       - URL: https://api.open-meteo.com/v1/forecast
       - Add URL parameters:
         * latitude = 37.7749
         * longitude = -122.4194
         * daily = weather_code,temperature_2m_max,temperature_2m_min,
                   sunrise,sunset,uv_index_max,precipitation_sum,
                   precipitation_probability_max,wind_speed_10m_max
         * timezone = America/Los_Angeles
         * forecast_days = 7
       - Path to data: $.daily
       - Schedule: Every 1 hour
    7. Click Create -- Nexla creates a Nexset automatically
    8. Note the Nexset ID from the URL or details panel
    9. Go to Settings > Authentication > Create Service Key
    10. Set environment variables:
        export NEXLA_SERVICE_KEY="your_service_key_here"
        export NEXLA_NEXSET_ID="your_nexset_id_here"

    OPTION C: Minimal Demo Integration
    -----------------------------------
    If time is tight, just do steps 1-8 above via the UI.
    Show the pipeline in Express.dev during the demo.
    The code already falls back to direct Open-Meteo calls,
    so the app works either way. The Nexla integration is
    visible in the code and in the Express.dev dashboard.

    ============================================================
    """
    print(guide)


# --- Quick test ---

if __name__ == "__main__":
    print_setup_guide()

    print("\n=== Pipeline Status ===")
    status = get_pipeline_status()
    print(json.dumps(status, indent=2))

    print("\n=== Current Weather (with Nexla fallback) ===")
    weather = get_current_weather("downtown")
    print(json.dumps(weather, indent=2))
    print(f"\nData source: {weather['source']}")

    print("\n=== 3-Day Forecast ===")
    forecast = get_forecast("golden_gate_park", days=3)
    print(json.dumps(forecast, indent=2))
    print(f"\nData source: {forecast['source']}")
