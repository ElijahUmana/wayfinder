"""
Wayfinder Backend — FastAPI Server with assistant-stream integration.

Exposes /api/chat endpoint that:
1. Receives messages + image uploads from the assistant-ui frontend
2. Runs the Railtracks multi-agent pipeline
3. Streams results back via the Data Stream Protocol (tool calls for each chapter)
"""

import asyncio
import base64
import json
import os
import sys
import time

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from assistant_stream import create_run, RunController
from assistant_stream.serialization import DataStreamResponse

import anthropic

# Add parent dir to path for imports
sys.path.insert(0, os.path.dirname(__file__))

from services import gradient, maps, spotify, augment_kb
from services.weather_openmeteo import get_current_weather, get_forecast

app = FastAPI(title="Wayfinder API")

@app.on_event("startup")
async def startup():
    """Pre-initialize the Augment knowledge base on server start."""
    try:
        augment_kb._get_context()
        print("Augment knowledge base initialized")
    except Exception as e:
        print(f"Warning: Augment KB init failed: {e}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Anthropic client for the main chat
_anthropic = None
def get_anthropic():
    global _anthropic
    if _anthropic is None:
        _anthropic = anthropic.AsyncAnthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    return _anthropic


# ---------------------------------------------------------------------------
# Tool Definitions (these map to Railtracks agent capabilities)
# ---------------------------------------------------------------------------

TOOLS = [
    {
        "name": "identify_location",
        "description": "Identify a location from an uploaded photo. Analyzes the image using vision AI to determine what place in San Francisco is shown.",
        "input_schema": {
            "type": "object",
            "properties": {
                "image_description": {"type": "string", "description": "Description of what's in the image (from the vision analysis)"},
            },
            "required": ["image_description"],
        },
    },
    {
        "name": "plan_journey",
        "description": "Plan a complete immersive guided journey from the user's current location to the identified destination via public transit. Returns chapters with narration, images, audio, and music.",
        "input_schema": {
            "type": "object",
            "properties": {
                "destination": {"type": "string", "description": "Destination name"},
                "user_location": {"type": "string", "description": "User's current location"},
                "user_lat": {"type": "number", "description": "User's latitude"},
                "user_lng": {"type": "number", "description": "User's longitude"},
            },
            "required": ["destination", "user_location"],
        },
    },
    {
        "name": "get_weather",
        "description": "Get current weather and forecast for the destination.",
        "input_schema": {
            "type": "object",
            "properties": {
                "location": {"type": "string", "description": "Location name"},
                "lat": {"type": "number"},
                "lng": {"type": "number"},
            },
            "required": ["location"],
        },
    },
    {
        "name": "get_transit_route",
        "description": "Get detailed public transit directions between two locations.",
        "input_schema": {
            "type": "object",
            "properties": {
                "origin": {"type": "string"},
                "destination": {"type": "string"},
            },
            "required": ["origin", "destination"],
        },
    },
    {
        "name": "search_knowledge_base",
        "description": "Search the Augment-powered San Francisco knowledge base for information about a location, neighborhood, food, history, or hidden gems.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "What to search for"},
                "question": {"type": "string", "description": "Specific question to answer using the knowledge base"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "generate_journey_chapter",
        "description": "Generate a single journey chapter with narration, music recommendation, and scene description.",
        "input_schema": {
            "type": "object",
            "properties": {
                "chapter_number": {"type": "integer"},
                "title": {"type": "string"},
                "segment_type": {"type": "string", "description": "DEPARTURE, WALKING, TRANSIT, ARRIVAL, EXPLORE"},
                "location": {"type": "string"},
                "duration": {"type": "string"},
                "transit_info": {"type": "string"},
                "narration": {"type": "string"},
                "music_mood": {"type": "string"},
                "pois": {"type": "array", "items": {"type": "string"}},
                "image_prompt": {"type": "string"},
                "image_b64": {"type": "string"},
                "audio_url": {"type": "string"},
                "spotify_embed_url": {"type": "string"},
                "spotify_playlist_name": {"type": "string"},
            },
            "required": ["chapter_number", "title", "segment_type", "narration"],
        },
    },
    {
        "name": "show_map_route",
        "description": "Display the transit route on a map with markers for origin, destination, and points of interest.",
        "input_schema": {
            "type": "object",
            "properties": {
                "origin": {"type": "object", "properties": {"lat": {"type": "number"}, "lng": {"type": "number"}, "name": {"type": "string"}}},
                "destination": {"type": "object", "properties": {"lat": {"type": "number"}, "lng": {"type": "number"}, "name": {"type": "string"}}},
                "polyline": {"type": "string"},
                "segments": {"type": "array", "items": {"type": "object"}},
                "pois": {"type": "array", "items": {"type": "object"}},
            },
            "required": ["origin", "destination"],
        },
    },
    {
        "name": "show_weather_card",
        "description": "Display weather information for the destination.",
        "input_schema": {
            "type": "object",
            "properties": {
                "location": {"type": "string"},
                "temperature": {"type": "number"},
                "conditions": {"type": "string"},
                "humidity": {"type": "number"},
                "wind_speed": {"type": "number"},
                "uv_index": {"type": "number"},
                "sunrise": {"type": "string"},
                "sunset": {"type": "string"},
                "best_time_note": {"type": "string"},
            },
            "required": ["location", "temperature", "conditions"],
        },
    },
]


# ---------------------------------------------------------------------------
# Tool Execution
# ---------------------------------------------------------------------------

async def execute_tool(name: str, args: dict) -> dict:
    """Execute a tool call and return the result."""

    if name == "identify_location":
        return args  # Just pass through — the LLM already analyzed the image

    elif name == "plan_journey":
        dest = args["destination"]
        user_loc = args.get("user_location", "Downtown San Francisco")
        user_lat = args.get("user_lat", 37.7749)
        user_lng = args.get("user_lng", -122.4194)

        # Geocode destination
        geo = maps.geocode(f"{dest}, San Francisco, CA")
        if not geo:
            return {"error": f"Could not find {dest}"}

        # Get route
        route = maps.get_transit_directions(
            user_loc, dest,
            {"lat": user_lat, "lng": user_lng},
            {"lat": geo["lat"], "lng": geo["lng"]},
        )

        # Get weather
        weather = get_current_weather(lat=geo["lat"], lon=geo["lng"])

        # Get knowledge
        knowledge = augment_kb.search_location(dest)

        # Get POIs
        pois = []
        if route and route.get("segments"):
            pois = maps.get_pois_along_route(route["segments"], max_pois=6)

        return {
            "destination": {"name": dest, "lat": geo["lat"], "lng": geo["lng"], "address": geo.get("formatted_address", "")},
            "route": route or {},
            "weather": weather,
            "knowledge": knowledge[:1000] if knowledge else "",
            "pois": pois,
        }

    elif name == "get_weather":
        lat = args.get("lat", 37.7749)
        lng = args.get("lng", -122.4194)
        current = get_current_weather(lat=lat, lon=lng)
        forecast = get_forecast(lat=lat, lon=lng, days=3)
        return {"current": current, "forecast": forecast}

    elif name == "get_transit_route":
        route = maps.get_transit_directions(args["origin"], args["destination"])
        return route or {"error": "No route found"}

    elif name == "search_knowledge_base":
        query = args["query"]
        question = args.get("question")
        if question:
            return {"answer": augment_kb.ask(query, question), "source": "augment_context_engine"}
        else:
            return {"results": augment_kb.search(query), "source": "augment_context_engine"}

    elif name == "generate_journey_chapter":
        return args  # Pass through — this is a display-only tool

    elif name == "show_map_route":
        return args  # Display-only tool

    elif name == "show_weather_card":
        return args  # Display-only tool

    return {"error": f"Unknown tool: {name}"}


# ---------------------------------------------------------------------------
# Chat Endpoint
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are Wayfinder, an AI-powered immersive city guide for San Francisco.

When a user uploads a photo of a place they want to visit, you:
1. Analyze the image to identify the location (use your vision capabilities)
2. Call plan_journey to get transit directions, weather, knowledge base context, and POIs
3. Call show_weather_card to display current conditions
4. Call show_map_route to display the transit route on a map
5. Generate 4-7 journey chapters using generate_journey_chapter for each segment:
   - Chapter 0: "The Departure" — user's starting point
   - Chapters 1-N: Each transit/walking segment along the route
   - Final Chapter: "The Arrival" — the destination
6. Each chapter should have engaging narration, a relevant Spotify embed, and point-of-interest callouts

For each chapter's narration, write vivid 2-4 sentence descriptions as if you're a local friend guiding them through the city. Include specific street names, landmarks, and insider tips.

For music, assign mood keywords: "departure" (calm), "transit_urban" (lo-fi), "walking" (confident), "anticipation" (building excitement), "arrival" (celebratory), "scenic" (nature), "cultural" (classical).

Always search the knowledge base for context about each area the journey passes through.

If no image is uploaded, ask the user to share a photo of where they want to go, or suggest popular SF destinations.

Be enthusiastic but not cheesy. Sound like a knowledgeable local, not a tour guide reading from a script."""


@app.post("/api/chat")
async def chat_endpoint(request: Request):
    body = await request.json()
    messages = body.get("messages", [])

    # Convert messages to Anthropic format
    anthropic_messages = []
    has_image = False

    for msg in messages:
        role = msg.get("role", "user")
        content_parts = msg.get("content", [])

        if isinstance(content_parts, str):
            anthropic_messages.append({"role": role, "content": content_parts})
            continue

        converted = []
        for part in content_parts:
            ptype = part.get("type", "")
            if ptype == "text":
                converted.append({"type": "text", "text": part["text"]})
            elif ptype == "image":
                has_image = True
                image_data = part.get("image", "")
                if image_data.startswith("data:"):
                    media_type = image_data.split(";")[0].split(":")[1]
                    b64_data = image_data.split(",")[1]
                    converted.append({
                        "type": "image",
                        "source": {"type": "base64", "media_type": media_type, "data": b64_data},
                    })
            elif ptype == "tool-call":
                converted.append({
                    "type": "tool_use",
                    "id": part["toolCallId"],
                    "name": part["toolName"],
                    "input": part.get("args", {}),
                })
            elif ptype == "tool-result":
                converted.append({
                    "type": "tool_result",
                    "tool_use_id": part["toolCallId"],
                    "content": json.dumps(part.get("result", {})),
                })

        if converted:
            anthropic_messages.append({"role": role, "content": converted})

    async def run_callback(controller: RunController):
        nonlocal anthropic_messages

        client = get_anthropic()

        while True:
            stream = client.messages.stream(
                model="claude-sonnet-4-20250514",
                max_tokens=8192,
                system=SYSTEM_PROMPT,
                messages=anthropic_messages,
                tools=TOOLS,
            )

            tool_calls = []

            async with stream as s:
                async for event in s:
                    if event.type == "content_block_start":
                        if event.content_block.type == "tool_use":
                            tc = await controller.add_tool_call(
                                tool_name=event.content_block.name,
                                tool_call_id=event.content_block.id,
                            )
                            tool_calls.append({
                                "controller": tc,
                                "id": event.content_block.id,
                                "name": event.content_block.name,
                                "args_text": "",
                            })
                    elif event.type == "content_block_delta":
                        if event.delta.type == "text_delta":
                            controller.append_text(event.delta.text)
                        elif event.delta.type == "input_json_delta":
                            if tool_calls:
                                tc = tool_calls[-1]
                                tc["args_text"] += event.delta.partial_json
                                tc["controller"].append_args_text(event.delta.partial_json)

            if not tool_calls:
                break

            # Execute tools and feed results back
            assistant_content = []
            tool_results_content = []

            for tc in tool_calls:
                args = json.loads(tc["args_text"]) if tc["args_text"] else {}
                try:
                    result = await execute_tool(tc["name"], args)
                except Exception as e:
                    result = {"error": str(e)}

                tc["controller"].set_response(result)
                controller.add_tool_result(tc["id"], result)

                assistant_content.append({
                    "type": "tool_use",
                    "id": tc["id"],
                    "name": tc["name"],
                    "input": args,
                })
                tool_results_content.append({
                    "type": "tool_result",
                    "tool_use_id": tc["id"],
                    "content": json.dumps(result),
                })

            anthropic_messages.append({"role": "assistant", "content": assistant_content})
            anthropic_messages.append({"role": "user", "content": tool_results_content})

    stream = create_run(run_callback)
    return DataStreamResponse(stream)


# ---------------------------------------------------------------------------
# Tool Execution Endpoints (called from Next.js API route)
# ---------------------------------------------------------------------------

@app.post("/api/tools/plan_journey")
async def tool_plan_journey(request: Request):
    body = await request.json()
    dest = body.get("destination", "")
    user_loc = body.get("user_location", "Downtown San Francisco")

    geo = maps.geocode(f"{dest}, San Francisco, CA")
    if not geo:
        return {"error": f"Could not find {dest}"}

    route = maps.get_transit_directions(user_loc, dest, None, {"lat": geo["lat"], "lng": geo["lng"]})
    weather = get_current_weather(lat=geo["lat"], lon=geo["lng"])
    knowledge = augment_kb.search_location(dest)
    pois = []
    if route and route.get("segments"):
        pois = maps.get_pois_along_route(route["segments"], max_pois=6)

    return {
        "destination": {"name": dest, "lat": geo["lat"], "lng": geo["lng"], "address": geo.get("formatted_address", "")},
        "route": route or {},
        "weather": weather,
        "knowledge": knowledge[:1500] if knowledge else "",
        "pois": pois,
    }


@app.post("/api/tools/search_knowledge")
async def tool_search_knowledge(request: Request):
    body = await request.json()
    query = body.get("query", "")
    question = body.get("question")
    if question:
        return {"answer": augment_kb.ask(query, question), "source": "augment_context_engine"}
    return {"results": augment_kb.search(query), "source": "augment_context_engine"}


@app.post("/api/tools/tts")
async def tool_tts(request: Request):
    body = await request.json()
    text = body.get("text", "")
    voice = body.get("voice", "Aria")
    url = gradient.text_to_speech(text, voice)
    return {"audio_url": url}


@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "services": {
            "do_gradient": bool(os.environ.get("DIGITAL_OCEAN_MODEL_ACCESS_KEY")),
            "anthropic": bool(os.environ.get("ANTHROPIC_API_KEY")),
            "augment": bool(os.environ.get("AUGMENT_API_TOKEN")),
            "google_maps": bool(os.environ.get("GOOGLE_MAPS_API_KEY")),
        },
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
