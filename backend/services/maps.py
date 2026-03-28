"""
Google Maps service client.

Provides: geocoding (place name -> coordinates), transit directions,
and points of interest along a route.
"""

import os
from typing import Optional

import httpx


def _get_key() -> str:
    return os.environ.get("GOOGLE_MAPS_API_KEY", "")


# ---------------------------------------------------------------------------
# Geocoding
# ---------------------------------------------------------------------------

def geocode(place_name: str) -> Optional[dict]:
    """
    Convert a place name to GPS coordinates.
    Returns {"lat": float, "lng": float, "formatted_address": str} or None.
    """
    key = _get_key()
    if not key:
        return None

    resp = httpx.get("https://maps.googleapis.com/maps/api/geocode/json", params={
        "address": place_name,
        "bounds": "37.7034,-122.5272|37.8324,-122.3482",  # Bias toward SF
        "key": key,
    })
    data = resp.json()
    if data["status"] != "OK" or not data["results"]:
        return None

    result = data["results"][0]
    return {
        "lat": result["geometry"]["location"]["lat"],
        "lng": result["geometry"]["location"]["lng"],
        "formatted_address": result["formatted_address"],
        "place_id": result.get("place_id", ""),
        "types": result.get("types", []),
    }


# ---------------------------------------------------------------------------
# Transit Directions
# ---------------------------------------------------------------------------

def get_transit_directions(origin: str, destination: str, origin_coords: Optional[dict] = None, dest_coords: Optional[dict] = None) -> Optional[dict]:
    """
    Get public transit directions between two points.
    Returns structured route with segments (chapters).
    """
    key = _get_key()
    if not key:
        return None

    origin_str = f"{origin_coords['lat']},{origin_coords['lng']}" if origin_coords else origin
    dest_str = f"{dest_coords['lat']},{dest_coords['lng']}" if dest_coords else destination

    resp = httpx.get("https://maps.googleapis.com/maps/api/directions/json", params={
        "origin": origin_str,
        "destination": dest_str,
        "mode": "transit",
        "alternatives": "true",
        "key": key,
    })
    data = resp.json()
    if data["status"] != "OK" or not data["routes"]:
        return None

    route = data["routes"][0]
    leg = route["legs"][0]

    segments = []
    for step in leg["steps"]:
        segment = {
            "mode": step["travel_mode"],
            "duration": step["duration"]["text"],
            "duration_seconds": step["duration"]["value"],
            "distance": step["distance"]["text"],
            "instructions": step.get("html_instructions", ""),
            "start_location": step["start_location"],
            "end_location": step["end_location"],
            "polyline": step["polyline"]["points"],
        }

        if step["travel_mode"] == "TRANSIT" and "transit_details" in step:
            td = step["transit_details"]
            segment["transit"] = {
                "line_name": td["line"].get("short_name") or td["line"].get("name", ""),
                "line_long_name": td["line"].get("name", ""),
                "line_color": td["line"].get("color", "#4285F4"),
                "vehicle_type": td["line"]["vehicle"]["type"],
                "vehicle_name": td["line"]["vehicle"].get("name", ""),
                "departure_stop": td["departure_stop"]["name"],
                "arrival_stop": td["arrival_stop"]["name"],
                "departure_time": td.get("departure_time", {}).get("text", ""),
                "arrival_time": td.get("arrival_time", {}).get("text", ""),
                "num_stops": td.get("num_stops", 0),
                "headsign": td.get("headsign", ""),
            }

        segments.append(segment)

    return {
        "duration": leg["duration"]["text"],
        "duration_seconds": leg["duration"]["value"],
        "distance": leg["distance"]["text"],
        "departure_time": leg.get("departure_time", {}).get("text", ""),
        "arrival_time": leg.get("arrival_time", {}).get("text", ""),
        "start_address": leg["start_address"],
        "end_address": leg["end_address"],
        "segments": segments,
        "overview_polyline": route["overview_polyline"]["points"],
        "bounds": route.get("bounds", {}),
    }


# ---------------------------------------------------------------------------
# Points of Interest (via Overpass API - free, no key needed)
# ---------------------------------------------------------------------------

def get_pois_near(lat: float, lng: float, radius_meters: int = 500) -> list[dict]:
    """
    Get points of interest near a location using OpenStreetMap Overpass API.
    Free, no API key needed.
    """
    query = f"""
    [out:json][timeout:10];
    (
      node["tourism"~"attraction|museum|artwork|gallery|viewpoint"](around:{radius_meters},{lat},{lng});
      node["historic"](around:{radius_meters},{lat},{lng});
      node["amenity"~"restaurant|cafe|bar"](around:{radius_meters},{lat},{lng});
    );
    out body 10;
    """

    try:
        resp = httpx.post(
            "https://overpass-api.de/api/interpreter",
            data={"data": query},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=15,
        )
        data = resp.json()

        pois = []
        for el in data.get("elements", []):
            tags = el.get("tags", {})
            name = tags.get("name")
            if not name:
                continue
            pois.append({
                "name": name,
                "lat": el["lat"],
                "lng": el["lon"],
                "type": tags.get("tourism") or tags.get("historic") or tags.get("amenity", "poi"),
                "description": tags.get("description", ""),
                "wikipedia": tags.get("wikipedia", ""),
            })

        return pois
    except Exception as e:
        print(f"POI lookup failed: {e}")
        return []


def get_pois_along_route(segments: list[dict], max_pois: int = 10) -> list[dict]:
    """Get POIs along a transit route by sampling midpoints of segments."""
    all_pois = {}

    # Sample midpoints of transit and walking segments
    for seg in segments:
        mid_lat = (seg["start_location"]["lat"] + seg["end_location"]["lat"]) / 2
        mid_lng = (seg["start_location"]["lng"] + seg["end_location"]["lng"]) / 2

        for poi in get_pois_near(mid_lat, mid_lng, radius_meters=400):
            key = poi["name"]
            if key not in all_pois:
                all_pois[key] = poi

        if len(all_pois) >= max_pois:
            break

    return list(all_pois.values())[:max_pois]
