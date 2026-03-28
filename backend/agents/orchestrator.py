"""
Wayfinder Agent Orchestrator — Railtracks Multi-Agent Pipeline.

This is the core brain of Wayfinder. Given an uploaded photo and user location,
it orchestrates a team of specialized agents to plan and narrate an immersive
guided journey through San Francisco.

Architecture:
  Orchestrator Flow
  ├── identify_location    — Vision AI identifies the place in the photo
  ├── geocode_location     — Converts place name to GPS coordinates
  ├── analyze_weather      — Gets weather + best time to visit
  ├── plan_route           — Gets transit directions with segments
  ├── research_knowledge   — Searches Augment knowledge base for each segment
  ├── find_pois            — Finds points of interest along the route
  ├── generate_chapters    — Creates narration, images, audio, music for each chapter
  └── assemble_journey     — Packages everything into the final journey response
"""

import asyncio
import base64
import json
import os
import time
from typing import Optional

import railtracks as rt
from pydantic import BaseModel, Field

from services import gradient, maps, spotify, augment_kb
from services.weather_openmeteo import get_current_weather, get_forecast


# ---------------------------------------------------------------------------
# Structured Output Schemas
# ---------------------------------------------------------------------------

class IdentifiedLocation(BaseModel):
    name: str = Field(description="Name of the identified place")
    neighborhood: str = Field(description="SF neighborhood it's in")
    description: str = Field(description="Brief description of the place")
    confidence: float = Field(description="Confidence score 0-1")
    place_type: str = Field(description="Type: landmark, park, restaurant, museum, viewpoint, etc.")


class JourneyChapter(BaseModel):
    chapter_number: int
    title: str
    segment_type: str = Field(description="WALKING, TRANSIT, ARRIVAL, DEPARTURE, EXPLORE")
    narration: str = Field(description="Engaging narration text for this chapter, 2-4 sentences")
    duration: str = Field(description="How long this segment takes")
    transit_info: Optional[str] = Field(default=None, description="Transit line name if applicable")
    image_prompt: str = Field(description="Prompt for AI image generation of this scene")
    music_mood: str = Field(description="Mood keyword for music selection")
    pois: list[str] = Field(default_factory=list, description="Points of interest visible during this segment")
    knowledge_facts: list[str] = Field(default_factory=list, description="Interesting facts from knowledge base")


class JourneyPlan(BaseModel):
    destination_name: str
    destination_neighborhood: str
    total_duration: str
    departure_time: str
    arrival_time: str
    weather_summary: str
    best_time_note: str
    chapters: list[JourneyChapter]


# ---------------------------------------------------------------------------
# Railtracks Tool Nodes
# ---------------------------------------------------------------------------

@rt.function_node
def identify_location_from_image(image_b64: str, mime_type: str = "image/jpeg") -> dict:
    """Identify a location from an uploaded photo using vision AI.

    Args:
        image_b64 (str): Base64-encoded image data.
        mime_type (str): MIME type of the image.

    Returns:
        dict: Identified location with name, neighborhood, description, confidence, place_type.
    """
    prompt = """Analyze this image and identify the specific location in San Francisco (or nearby Bay Area).

Return a JSON object with these fields:
- name: The specific place name (e.g., "Golden Gate Bridge", "Dolores Park", "Coit Tower")
- neighborhood: The SF neighborhood (e.g., "Presidio", "Mission District", "North Beach")
- description: A brief description of what you see and why this place is notable
- confidence: Your confidence that you correctly identified the location (0.0-1.0)
- place_type: One of: landmark, park, restaurant, museum, viewpoint, beach, bridge, building, street, neighborhood

If you cannot identify a specific place, provide your best guess based on architectural style, vegetation, geography, and any visible text/signs.

Return ONLY the JSON object, no other text."""

    result = gradient.analyze_image(image_b64, prompt, mime_type)

    # Parse the JSON from the response
    try:
        # Handle markdown code blocks
        if "```" in result:
            result = result.split("```")[1]
            if result.startswith("json"):
                result = result[4:]
        return json.loads(result.strip())
    except json.JSONDecodeError:
        return {
            "name": "Unknown Location",
            "neighborhood": "San Francisco",
            "description": result[:200],
            "confidence": 0.3,
            "place_type": "landmark",
        }


@rt.function_node
def geocode_place(place_name: str) -> dict:
    """Convert a place name to GPS coordinates using Google Geocoding API.

    Args:
        place_name (str): Name of the place to geocode.

    Returns:
        dict: Location with lat, lng, formatted_address.
    """
    result = maps.geocode(f"{place_name}, San Francisco, CA")
    if result:
        return result

    # Fallback: use Nominatim (free, no key)
    import httpx
    resp = httpx.get("https://nominatim.openstreetmap.org/search", params={
        "q": f"{place_name}, San Francisco",
        "format": "json",
        "limit": "1",
        "viewbox": "-122.5272,37.8324,-122.3482,37.7034",
        "bounded": "1",
    }, headers={"User-Agent": "Wayfinder/1.0"})
    data = resp.json()
    if data:
        return {
            "lat": float(data[0]["lat"]),
            "lng": float(data[0]["lon"]),
            "formatted_address": data[0].get("display_name", place_name),
        }

    return {"lat": 37.7749, "lng": -122.4194, "formatted_address": "San Francisco, CA"}


@rt.function_node
def get_weather_data(lat: float, lng: float) -> dict:
    """Get current weather and forecast for a location.

    Args:
        lat (float): Latitude.
        lng (float): Longitude.

    Returns:
        dict: Current weather and 3-day forecast.
    """
    current = get_current_weather(lat, lng)
    forecast = get_forecast(lat, lng, days=3)
    return {
        "current": current,
        "forecast": forecast,
    }


@rt.function_node
def plan_transit_route(origin: str, destination: str, origin_coords: dict, dest_coords: dict) -> dict:
    """Plan a public transit route using Google Maps Directions API.

    Args:
        origin (str): Origin address or place name.
        destination (str): Destination address or place name.
        origin_coords (dict): Origin coordinates with lat, lng.
        dest_coords (dict): Destination coordinates with lat, lng.

    Returns:
        dict: Transit route with segments, duration, polyline.
    """
    result = maps.get_transit_directions(origin, destination, origin_coords, dest_coords)
    if result:
        return result
    return {"error": "Could not find transit route", "segments": []}


@rt.function_node
def research_location(location_name: str, segment_type: str) -> str:
    """Research a location using Augment Context Engine knowledge base.

    Args:
        location_name (str): Name of the location or area to research.
        segment_type (str): Type of journey segment (walking, transit, etc.).

    Returns:
        str: Rich contextual information about the location.
    """
    return augment_kb.get_narration_context(location_name, segment_type)


@rt.function_node
def find_route_pois(segments: list) -> list:
    """Find points of interest along the transit route.

    Args:
        segments (list): List of route segments with start/end locations.

    Returns:
        list: Points of interest along the route.
    """
    return maps.get_pois_along_route(segments, max_pois=8)


@rt.function_node
def generate_chapter_narration(chapter_data: dict) -> str:
    """Generate engaging narration text for a journey chapter.

    Args:
        chapter_data (dict): Chapter info including location, segment_type, transit_info, knowledge_facts.

    Returns:
        str: Engaging narration text.
    """
    system = """You are an expert San Francisco city guide creating narration for an immersive audio-guided journey.
Your narration should be vivid, personal, and informative — like a friend who knows every corner of the city.
Keep each narration to 3-5 sentences. Include specific details, not generic descriptions.
Reference real landmarks, streets, and local knowledge. Make the listener feel like they're discovering the city."""

    user_prompt = f"""Write narration for this journey chapter:
- Chapter: {chapter_data.get('title', 'Unknown')}
- Segment type: {chapter_data.get('segment_type', 'walking')}
- Location/Area: {chapter_data.get('location', 'San Francisco')}
- Transit info: {chapter_data.get('transit_info', 'N/A')}
- Duration: {chapter_data.get('duration', 'unknown')}
- Points of interest nearby: {chapter_data.get('pois', [])}
- Knowledge base context: {chapter_data.get('knowledge', 'No additional context')}

Write the narration in second person ("you"). Make it feel like the listener is there right now."""

    return gradient.chat(
        messages=[{"role": "user", "content": user_prompt}],
        system=system,
        max_tokens=300,
    )


@rt.function_node
def generate_scene_image(prompt: str) -> str:
    """Generate an AI preview image for a journey chapter.

    Args:
        prompt (str): Image generation prompt describing the scene.

    Returns:
        str: Base64-encoded PNG image, or empty string if generation fails.
    """
    result = gradient.generate_image(prompt, size="1024x1024")
    return result or ""


@rt.function_node
def generate_audio_narration(text: str, voice: str = "Aria") -> str:
    """Generate TTS audio narration for a journey chapter.

    Args:
        text (str): Narration text to speak.
        voice (str): Voice name for TTS.

    Returns:
        str: URL to the generated MP3 audio file, or empty string.
    """
    result = gradient.text_to_speech(text, voice=voice)
    return result or ""


@rt.function_node
def select_chapter_music(segment_type: str, chapter_index: int, total_chapters: int) -> dict:
    """Select mood-appropriate Spotify playlist for a journey chapter.

    Args:
        segment_type (str): WALKING, TRANSIT, ARRIVAL, etc.
        chapter_index (int): Position in the journey (0-based).
        total_chapters (int): Total number of chapters.

    Returns:
        dict: Spotify playlist info with embed URL.
    """
    return spotify.select_mood_for_segment(
        segment_type=segment_type,
        segment_index=chapter_index,
        total_segments=total_chapters,
    )


# ---------------------------------------------------------------------------
# Main Orchestrator Flow
# ---------------------------------------------------------------------------

@rt.function_node
async def plan_journey(image_b64: str, mime_type: str, user_location: str, user_lat: float, user_lng: float) -> dict:
    """Main orchestrator: plans a complete immersive journey from a photo upload.

    Args:
        image_b64 (str): Base64-encoded uploaded photo.
        mime_type (str): MIME type of the photo.
        user_location (str): User's current location description.
        user_lat (float): User's current latitude.
        user_lng (float): User's current longitude.

    Returns:
        dict: Complete journey plan with chapters, each containing narration, image, audio, music.
    """
    # Step 1: Identify the location in the photo
    location = await rt.call(identify_location_from_image, image_b64, mime_type)
    location_data = location.structured if hasattr(location, 'structured') and location.structured else json.loads(location.text) if hasattr(location, 'text') else location

    dest_name = location_data.get("name", "Unknown Location")
    dest_neighborhood = location_data.get("neighborhood", "San Francisco")
    dest_type = location_data.get("place_type", "landmark")

    # Step 2: Geocode the destination
    dest_geo = await rt.call(geocode_place, dest_name)
    dest_geo_data = dest_geo.structured if hasattr(dest_geo, 'structured') and dest_geo.structured else json.loads(dest_geo.text) if hasattr(dest_geo, 'text') else dest_geo

    dest_lat = dest_geo_data.get("lat", 37.7749)
    dest_lng = dest_geo_data.get("lng", -122.4194)

    # Step 3: Get weather + route in parallel
    weather_result, route_result = await asyncio.gather(
        rt.call(get_weather_data, dest_lat, dest_lng),
        rt.call(plan_transit_route, user_location, dest_name,
                {"lat": user_lat, "lng": user_lng},
                {"lat": dest_lat, "lng": dest_lng}),
    )

    # Parse results
    weather_data = weather_result.structured if hasattr(weather_result, 'structured') and weather_result.structured else json.loads(weather_result.text) if hasattr(weather_result, 'text') else weather_result
    route_data = route_result.structured if hasattr(route_result, 'structured') and route_result.structured else json.loads(route_result.text) if hasattr(route_result, 'text') else route_result

    segments = route_data.get("segments", [])

    # Step 4: Research + POIs in parallel
    knowledge_result, pois_result = await asyncio.gather(
        rt.call(research_location, dest_name, dest_type),
        rt.call(find_route_pois, segments),
    )

    knowledge_text = knowledge_result.text if hasattr(knowledge_result, 'text') else str(knowledge_result)
    pois = pois_result.structured if hasattr(pois_result, 'structured') and pois_result.structured else json.loads(pois_result.text) if hasattr(pois_result, 'text') else pois_result

    # Step 5: Build chapters from route segments
    chapters = []
    total_chapters = len(segments) + 2  # departure + segments + arrival

    # Chapter 0: Departure
    chapters.append({
        "chapter_number": 0,
        "title": "The Departure",
        "segment_type": "DEPARTURE",
        "location": user_location,
        "duration": "Starting your journey",
        "transit_info": None,
        "pois": [],
        "knowledge": "",
    })

    # Chapters 1..N: Route segments
    for i, seg in enumerate(segments):
        chapter = {
            "chapter_number": i + 1,
            "title": _get_chapter_title(seg, i, len(segments)),
            "segment_type": seg.get("mode", "WALKING"),
            "location": seg.get("transit", {}).get("departure_stop", "") or "en route",
            "duration": seg.get("duration", ""),
            "transit_info": seg.get("transit", {}).get("line_name", None),
            "pois": [p["name"] for p in pois if _poi_near_segment(p, seg)],
            "knowledge": "",
        }
        chapters.append(chapter)

    # Final chapter: Arrival
    chapters.append({
        "chapter_number": len(chapters),
        "title": "The Arrival",
        "segment_type": "ARRIVAL",
        "location": dest_name,
        "duration": "You've arrived",
        "transit_info": None,
        "pois": [],
        "knowledge": knowledge_text[:500] if knowledge_text else "",
    })

    total_chapters = len(chapters)

    # Step 6: Generate content for each chapter (narration + music)
    enriched_chapters = []
    for ch in chapters:
        # Generate narration
        narration = await rt.call(generate_chapter_narration, ch)
        narration_text = narration.text if hasattr(narration, 'text') else str(narration)

        # Select music
        music = await rt.call(select_chapter_music, ch["segment_type"], ch["chapter_number"], total_chapters)
        music_data = music.structured if hasattr(music, 'structured') and music.structured else json.loads(music.text) if hasattr(music, 'text') else music

        # Build image prompt
        image_prompt = _build_image_prompt(ch, dest_name, weather_data)

        enriched_chapters.append({
            "chapter_number": ch["chapter_number"],
            "title": ch["title"],
            "segment_type": ch["segment_type"],
            "duration": ch["duration"],
            "transit_info": ch.get("transit_info"),
            "narration": narration_text,
            "image_prompt": image_prompt,
            "music": music_data,
            "pois": ch.get("pois", []),
        })

    # Step 7: Generate images + audio for key chapters (departure, midpoint, arrival)
    key_chapters = [0, len(enriched_chapters) // 2, len(enriched_chapters) - 1]
    for idx in key_chapters:
        if idx < len(enriched_chapters):
            ch = enriched_chapters[idx]
            # Generate image and audio in parallel
            img_result, audio_result = await asyncio.gather(
                rt.call(generate_scene_image, ch["image_prompt"]),
                rt.call(generate_audio_narration, ch["narration"]),
            )
            ch["image_b64"] = img_result.text if hasattr(img_result, 'text') else str(img_result)
            ch["audio_url"] = audio_result.text if hasattr(audio_result, 'text') else str(audio_result)

    # Build weather summary
    current_weather = weather_data.get("current", {})
    weather_summary = f"{current_weather.get('temperature', 'N/A')}°C, {current_weather.get('conditions', 'N/A')}"

    # Assemble final journey
    journey = {
        "destination": {
            "name": dest_name,
            "neighborhood": dest_neighborhood,
            "type": dest_type,
            "lat": dest_lat,
            "lng": dest_lng,
            "description": location_data.get("description", ""),
        },
        "route": {
            "total_duration": route_data.get("duration", ""),
            "total_distance": route_data.get("distance", ""),
            "departure_time": route_data.get("departure_time", ""),
            "arrival_time": route_data.get("arrival_time", ""),
            "overview_polyline": route_data.get("overview_polyline", ""),
            "bounds": route_data.get("bounds", {}),
        },
        "weather": weather_summary,
        "chapters": enriched_chapters,
        "pois": pois if isinstance(pois, list) else [],
    }

    # Index this journey in Augment for cross-journey search
    journey_summary = f"Journey to {dest_name} in {dest_neighborhood}. {weather_summary}. {route_data.get('duration', '')}."
    augment_kb.index_journey_data(f"journey-{int(time.time())}", journey_summary)

    return journey


# ---------------------------------------------------------------------------
# Helper Functions
# ---------------------------------------------------------------------------

def _get_chapter_title(segment: dict, index: int, total: int) -> str:
    """Generate a chapter title based on segment type and position."""
    mode = segment.get("mode", "WALKING")
    transit = segment.get("transit", {})

    if mode == "TRANSIT":
        line = transit.get("line_name", "")
        vehicle = transit.get("vehicle_name", "transit")
        return f"The {vehicle.title()} Ride" if not line else f"Riding the {line}"
    elif mode == "WALKING":
        if index == total - 1:
            return "The Final Approach"
        elif index == 0:
            return "Walking to the Station"
        else:
            return "The Transfer"
    return f"Chapter {index + 1}"


def _build_image_prompt(chapter: dict, destination: str, weather: dict) -> str:
    """Build a prompt for AI image generation."""
    location = chapter.get("location", "San Francisco")
    seg_type = chapter.get("segment_type", "walking")
    conditions = weather.get("current", {}).get("conditions", "clear sky")

    if seg_type == "DEPARTURE":
        return f"A person starting a journey through San Francisco streets, {conditions} weather, warm lighting, street-level perspective, cinematic"
    elif seg_type == "ARRIVAL":
        return f"Arriving at {destination} in San Francisco, golden hour lighting, {conditions}, stunning view, wide angle, cinematic photography"
    elif seg_type == "TRANSIT":
        transit = chapter.get("transit_info", "bus")
        return f"View from inside a {transit} in San Francisco, looking out the window at the passing city, {conditions}, atmospheric, cinematic"
    else:
        return f"Walking through {location} in San Francisco, street-level view, {conditions}, vibrant urban scene, cinematic photography"


def _poi_near_segment(poi: dict, segment: dict) -> bool:
    """Check if a POI is near a route segment (rough bounding box check)."""
    poi_lat = poi.get("lat", 0)
    poi_lng = poi.get("lng", 0)
    start = segment.get("start_location", {})
    end = segment.get("end_location", {})

    if not start or not end:
        return False

    min_lat = min(start.get("lat", 0), end.get("lat", 0)) - 0.005
    max_lat = max(start.get("lat", 0), end.get("lat", 0)) + 0.005
    min_lng = min(start.get("lng", 0), end.get("lng", 0)) - 0.005
    max_lng = max(start.get("lng", 0), end.get("lng", 0)) + 0.005

    return min_lat <= poi_lat <= max_lat and min_lng <= poi_lng <= max_lng


# ---------------------------------------------------------------------------
# Flow Definition
# ---------------------------------------------------------------------------

def create_journey_flow() -> rt.Flow:
    """Create the main Wayfinder journey planning flow."""
    return rt.Flow(
        name="Wayfinder Journey Planner",
        entry_point=plan_journey,
        timeout=300,
        save_state=True,
    )
