"""
Direct Open-Meteo weather data module.

Provides reliable weather forecasts for San Francisco locations.
No API key required. Free for non-commercial use.
API docs: https://open-meteo.com/en/docs
"""

import requests
from datetime import datetime, timedelta
from typing import Optional


# --- WMO Weather Code Mapping ---

WMO_CODES = {
    0: "Clear sky",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Fog",
    48: "Depositing rime fog",
    51: "Light drizzle",
    53: "Moderate drizzle",
    55: "Dense drizzle",
    56: "Light freezing drizzle",
    57: "Dense freezing drizzle",
    61: "Slight rain",
    63: "Moderate rain",
    65: "Heavy rain",
    66: "Light freezing rain",
    67: "Heavy freezing rain",
    71: "Slight snowfall",
    73: "Moderate snowfall",
    75: "Heavy snowfall",
    77: "Snow grains",
    80: "Slight rain showers",
    81: "Moderate rain showers",
    82: "Violent rain showers",
    85: "Slight snow showers",
    86: "Heavy snow showers",
    95: "Thunderstorm",
    96: "Thunderstorm with slight hail",
    99: "Thunderstorm with heavy hail",
}

# --- San Francisco Locations ---

SF_LOCATIONS = {
    "downtown": {"lat": 37.7749, "lon": -122.4194, "name": "Downtown SF"},
    "golden_gate_park": {"lat": 37.7694, "lon": -122.4862, "name": "Golden Gate Park"},
    "fishermans_wharf": {"lat": 37.8080, "lon": -122.4177, "name": "Fisherman's Wharf"},
    "mission_district": {"lat": 37.7599, "lon": -122.4148, "name": "Mission District"},
    "ocean_beach": {"lat": 37.7594, "lon": -122.5107, "name": "Ocean Beach"},
    "twin_peaks": {"lat": 37.7544, "lon": -122.4477, "name": "Twin Peaks"},
    "presidio": {"lat": 37.7989, "lon": -122.4662, "name": "The Presidio"},
    "soma": {"lat": 37.7785, "lon": -122.3950, "name": "SoMa"},
    "castro": {"lat": 37.7609, "lon": -122.4350, "name": "The Castro"},
    "north_beach": {"lat": 37.8060, "lon": -122.4103, "name": "North Beach"},
}

BASE_URL = "https://api.open-meteo.com/v1/forecast"


def _c_to_f(celsius: float) -> float:
    """Convert Celsius to Fahrenheit."""
    return round(celsius * 9 / 5 + 32, 1)


def _kmh_to_mph(kmh: float) -> float:
    """Convert km/h to mph."""
    return round(kmh * 0.621371, 1)


def _describe_weather(code: int) -> str:
    """Get human-readable weather description from WMO code."""
    return WMO_CODES.get(code, f"Unknown ({code})")


def get_current_weather(
    location_key: str = "downtown",
    lat: Optional[float] = None,
    lon: Optional[float] = None,
    units: str = "imperial",
) -> dict:
    """
    Get current weather conditions for a San Francisco location.

    Args:
        location_key: Key from SF_LOCATIONS (e.g., "downtown", "golden_gate_park")
        lat: Override latitude (ignores location_key if provided with lon)
        lon: Override longitude (ignores location_key if provided with lat)
        units: "imperial" (Fahrenheit/mph) or "metric" (Celsius/km/h)

    Returns:
        Dict with current weather data.
    """
    if lat is not None and lon is not None:
        location_name = f"Custom ({lat}, {lon})"
    else:
        loc = SF_LOCATIONS.get(location_key)
        if not loc:
            raise ValueError(
                f"Unknown location '{location_key}'. "
                f"Valid keys: {list(SF_LOCATIONS.keys())}"
            )
        lat, lon, location_name = loc["lat"], loc["lon"], loc["name"]

    params = {
        "latitude": lat,
        "longitude": lon,
        "current": ",".join([
            "temperature_2m",
            "relative_humidity_2m",
            "apparent_temperature",
            "weather_code",
            "wind_speed_10m",
            "wind_direction_10m",
            "precipitation",
            "is_day",
        ]),
        "timezone": "America/Los_Angeles",
    }

    resp = requests.get(BASE_URL, params=params, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    c = data["current"]

    temp_c = c["temperature_2m"]
    feels_like_c = c["apparent_temperature"]
    wind_kmh = c["wind_speed_10m"]

    result = {
        "location": location_name,
        "latitude": data["latitude"],
        "longitude": data["longitude"],
        "elevation_m": data["elevation"],
        "time": c["time"],
        "weather": _describe_weather(c["weather_code"]),
        "weather_code": c["weather_code"],
        "is_day": bool(c["is_day"]),
        "humidity_pct": c["relative_humidity_2m"],
        "wind_direction_deg": c["wind_direction_10m"],
        "precipitation_mm": c["precipitation"],
    }

    if units == "imperial":
        result["temperature_f"] = _c_to_f(temp_c)
        result["feels_like_f"] = _c_to_f(feels_like_c)
        result["wind_speed_mph"] = _kmh_to_mph(wind_kmh)
    else:
        result["temperature_c"] = temp_c
        result["feels_like_c"] = feels_like_c
        result["wind_speed_kmh"] = wind_kmh

    return result


def get_forecast(
    location_key: str = "downtown",
    lat: Optional[float] = None,
    lon: Optional[float] = None,
    days: int = 7,
    units: str = "imperial",
) -> dict:
    """
    Get daily weather forecast for a San Francisco location.

    Args:
        location_key: Key from SF_LOCATIONS
        lat/lon: Override coordinates
        days: Forecast days (1-16)
        units: "imperial" or "metric"

    Returns:
        Dict with location info and list of daily forecasts.
    """
    if lat is not None and lon is not None:
        location_name = f"Custom ({lat}, {lon})"
    else:
        loc = SF_LOCATIONS.get(location_key)
        if not loc:
            raise ValueError(f"Unknown location '{location_key}'.")
        lat, lon, location_name = loc["lat"], loc["lon"], loc["name"]

    params = {
        "latitude": lat,
        "longitude": lon,
        "daily": ",".join([
            "weather_code",
            "temperature_2m_max",
            "temperature_2m_min",
            "apparent_temperature_max",
            "apparent_temperature_min",
            "sunrise",
            "sunset",
            "uv_index_max",
            "precipitation_sum",
            "precipitation_probability_max",
            "wind_speed_10m_max",
            "sunshine_duration",
        ]),
        "timezone": "America/Los_Angeles",
        "forecast_days": min(max(days, 1), 16),
    }

    resp = requests.get(BASE_URL, params=params, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    d = data["daily"]

    forecasts = []
    for i in range(len(d["time"])):
        high_c = d["temperature_2m_max"][i]
        low_c = d["temperature_2m_min"][i]
        feels_high_c = d["apparent_temperature_max"][i]
        feels_low_c = d["apparent_temperature_min"][i]
        wind_kmh = d["wind_speed_10m_max"][i]

        day_data = {
            "date": d["time"][i],
            "weather": _describe_weather(d["weather_code"][i]),
            "weather_code": d["weather_code"][i],
            "sunrise": d["sunrise"][i],
            "sunset": d["sunset"][i],
            "uv_index_max": d["uv_index_max"][i],
            "precipitation_mm": d["precipitation_sum"][i],
            "precipitation_probability_pct": d["precipitation_probability_max"][i],
            "sunshine_hours": round(d["sunshine_duration"][i] / 3600, 1),
        }

        if units == "imperial":
            day_data["high_f"] = _c_to_f(high_c)
            day_data["low_f"] = _c_to_f(low_c)
            day_data["feels_like_high_f"] = _c_to_f(feels_high_c)
            day_data["feels_like_low_f"] = _c_to_f(feels_low_c)
            day_data["wind_max_mph"] = _kmh_to_mph(wind_kmh)
        else:
            day_data["high_c"] = high_c
            day_data["low_c"] = low_c
            day_data["feels_like_high_c"] = feels_high_c
            day_data["feels_like_low_c"] = feels_low_c
            day_data["wind_max_kmh"] = wind_kmh

        forecasts.append(day_data)

    return {
        "location": location_name,
        "latitude": data["latitude"],
        "longitude": data["longitude"],
        "forecast": forecasts,
    }


def get_hourly_forecast(
    location_key: str = "downtown",
    lat: Optional[float] = None,
    lon: Optional[float] = None,
    hours: int = 24,
    units: str = "imperial",
) -> dict:
    """
    Get hourly weather forecast for a San Francisco location.

    Args:
        location_key: Key from SF_LOCATIONS
        lat/lon: Override coordinates
        hours: Number of forecast hours (max 384 = 16 days)
        units: "imperial" or "metric"

    Returns:
        Dict with location info and list of hourly forecasts.
    """
    if lat is not None and lon is not None:
        location_name = f"Custom ({lat}, {lon})"
    else:
        loc = SF_LOCATIONS.get(location_key)
        if not loc:
            raise ValueError(f"Unknown location '{location_key}'.")
        lat, lon, location_name = loc["lat"], loc["lon"], loc["name"]

    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": ",".join([
            "temperature_2m",
            "relative_humidity_2m",
            "apparent_temperature",
            "precipitation_probability",
            "precipitation",
            "weather_code",
            "wind_speed_10m",
            "uv_index",
            "is_day",
        ]),
        "timezone": "America/Los_Angeles",
        "forecast_hours": min(hours, 384),
    }

    resp = requests.get(BASE_URL, params=params, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    h = data["hourly"]

    hourly_data = []
    for i in range(len(h["time"])):
        temp_c = h["temperature_2m"][i]
        feels_c = h["apparent_temperature"][i]
        wind_kmh = h["wind_speed_10m"][i]

        entry = {
            "time": h["time"][i],
            "weather": _describe_weather(h["weather_code"][i]),
            "weather_code": h["weather_code"][i],
            "humidity_pct": h["relative_humidity_2m"][i],
            "precipitation_probability_pct": h["precipitation_probability"][i],
            "precipitation_mm": h["precipitation"][i],
            "uv_index": h["uv_index"][i],
            "is_day": bool(h["is_day"][i]),
        }

        if units == "imperial":
            entry["temperature_f"] = _c_to_f(temp_c)
            entry["feels_like_f"] = _c_to_f(feels_c)
            entry["wind_speed_mph"] = _kmh_to_mph(wind_kmh)
        else:
            entry["temperature_c"] = temp_c
            entry["feels_like_c"] = feels_c
            entry["wind_speed_kmh"] = wind_kmh

        hourly_data.append(entry)

    return {
        "location": location_name,
        "latitude": data["latitude"],
        "longitude": data["longitude"],
        "hourly": hourly_data,
    }


def get_historical_summary(
    location_key: str = "downtown",
    past_days: int = 30,
) -> dict:
    """
    Get historical weather summary for "best time to visit" analysis.

    Returns average temperatures, total precipitation, and sunshine
    over the past N days.
    """
    loc = SF_LOCATIONS.get(location_key)
    if not loc:
        raise ValueError(f"Unknown location '{location_key}'.")

    params = {
        "latitude": loc["lat"],
        "longitude": loc["lon"],
        "daily": ",".join([
            "temperature_2m_max",
            "temperature_2m_min",
            "precipitation_sum",
            "sunshine_duration",
            "weather_code",
        ]),
        "timezone": "America/Los_Angeles",
        "past_days": past_days,
        "forecast_days": 1,
    }

    resp = requests.get(BASE_URL, params=params, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    d = data["daily"]

    temps_max = [t for t in d["temperature_2m_max"] if t is not None]
    temps_min = [t for t in d["temperature_2m_min"] if t is not None]
    precip = [p for p in d["precipitation_sum"] if p is not None]
    sunshine = [s for s in d["sunshine_duration"] if s is not None]
    codes = d["weather_code"]

    # Count weather types
    clear_days = sum(1 for c in codes if c is not None and c <= 3)
    rainy_days = sum(1 for c in codes if c is not None and c in range(51, 100))

    avg_high_c = sum(temps_max) / len(temps_max) if temps_max else 0
    avg_low_c = sum(temps_min) / len(temps_min) if temps_min else 0

    return {
        "location": loc["name"],
        "period_days": past_days,
        "avg_high_f": _c_to_f(avg_high_c),
        "avg_low_f": _c_to_f(avg_low_c),
        "avg_high_c": round(avg_high_c, 1),
        "avg_low_c": round(avg_low_c, 1),
        "total_precipitation_mm": round(sum(precip), 1),
        "avg_sunshine_hours_per_day": round(
            sum(sunshine) / len(sunshine) / 3600, 1
        ) if sunshine else 0,
        "clear_days": clear_days,
        "rainy_days": rainy_days,
        "total_days": len(codes),
    }


def get_all_sf_current(units: str = "imperial") -> list[dict]:
    """Get current weather for ALL San Francisco locations at once."""
    # Open-Meteo supports multi-location queries
    lats = ",".join(str(loc["lat"]) for loc in SF_LOCATIONS.values())
    lons = ",".join(str(loc["lon"]) for loc in SF_LOCATIONS.values())
    names = list(SF_LOCATIONS.values())

    params = {
        "latitude": lats,
        "longitude": lons,
        "current": ",".join([
            "temperature_2m",
            "relative_humidity_2m",
            "apparent_temperature",
            "weather_code",
            "wind_speed_10m",
            "is_day",
        ]),
        "timezone": "America/Los_Angeles",
    }

    resp = requests.get(BASE_URL, params=params, timeout=10)
    resp.raise_for_status()
    results_raw = resp.json()

    # Multi-location returns a list
    if not isinstance(results_raw, list):
        results_raw = [results_raw]

    results = []
    for i, data in enumerate(results_raw):
        c = data["current"]
        temp_c = c["temperature_2m"]
        feels_c = c["apparent_temperature"]
        wind_kmh = c["wind_speed_10m"]

        entry = {
            "location": names[i]["name"],
            "weather": _describe_weather(c["weather_code"]),
            "humidity_pct": c["relative_humidity_2m"],
            "is_day": bool(c["is_day"]),
        }

        if units == "imperial":
            entry["temperature_f"] = _c_to_f(temp_c)
            entry["feels_like_f"] = _c_to_f(feels_c)
            entry["wind_speed_mph"] = _kmh_to_mph(wind_kmh)
        else:
            entry["temperature_c"] = temp_c
            entry["feels_like_c"] = feels_c
            entry["wind_speed_kmh"] = wind_kmh

        results.append(entry)

    return results


# --- Quick test ---

if __name__ == "__main__":
    import json

    print("=== Current Weather (Downtown SF) ===")
    current = get_current_weather("downtown")
    print(json.dumps(current, indent=2))

    print("\n=== 3-Day Forecast (Golden Gate Park) ===")
    forecast = get_forecast("golden_gate_park", days=3)
    print(json.dumps(forecast, indent=2))

    print("\n=== Historical Summary (past 30 days) ===")
    history = get_historical_summary("downtown", past_days=30)
    print(json.dumps(history, indent=2))

    print("\n=== All SF Locations Current ===")
    all_weather = get_all_sf_current()
    for w in all_weather:
        print(f"  {w['location']}: {w['temperature_f']}F - {w['weather']}")
