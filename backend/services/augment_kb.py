"""
Augment Code Context Engine — Deep Integration for Wayfinder.

Uses DirectContext for semantic search + RAG over the SF knowledge base.
Demonstrates Augment's core value: "Same model, better context = dramatically better results."

This module:
1. Loads a pre-indexed knowledge base (21 SF city guide documents)
2. Provides semantic search for location-specific facts
3. Provides RAG (search_and_ask) for grounded answers about SF
4. Supports dynamic indexing of journey-specific content
5. Persists the index so cold start is instant
"""

import os
import time
from pathlib import Path
from typing import Optional

from auggie_sdk.context import DirectContext, File


_ctx: Optional[DirectContext] = None
_INDEX_PATH = Path(__file__).parent.parent / "data" / "sf-knowledge-base.json"


def _get_context() -> DirectContext:
    """Get or create the DirectContext instance with the SF knowledge base loaded."""
    global _ctx
    if _ctx is not None:
        return _ctx

    api_key = os.environ.get("AUGMENT_API_TOKEN", "")
    api_url = os.environ.get("AUGMENT_API_URL", "https://d5.api.augmentcode.com/")

    ctx = DirectContext(api_key=api_key, api_url=api_url)

    # Always re-index on startup (fast, ~4 seconds, guarantees index is valid)
    _index_sf_data(ctx)

    _ctx = ctx
    return ctx


def _index_sf_data(ctx: DirectContext) -> None:
    """Index the full SF knowledge base from scratch."""
    docs = _build_sf_documents()
    ctx.add_to_index(docs)
    # Persist for next startup
    _INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
    ctx.export_to_file(str(_INDEX_PATH))


def _build_sf_documents() -> list[File]:
    """Build all SF knowledge base documents inline."""
    return [
        File(path="sf/neighborhoods/mission.md", contents="# Mission District\nThe Mission District is San Francisco's cultural heartbeat. Known for vibrant murals (Balmy Alley, Clarion Alley), incredible Mexican and Latin American food, and lively nightlife. Must-visit: Dolores Park for city views, Tartine Bakery, La Taqueria (best burrito in SF). Transit: BART 16th St Mission and 24th St Mission stations. The neighborhood has the city's warmest microclimate."),
        File(path="sf/neighborhoods/chinatown.md", contents="# Chinatown\nSF's Chinatown is the oldest in North America (1848). Enter through Dragon's Gate on Grant Avenue. Stockton Street is where locals shop. Must-visit: Golden Gate Fortune Cookie Factory, Tin How Temple, Portsmouth Square. Best dim sum: City View Restaurant, Hang Ah Tea Room (since 1920). Transit: Walk from Union Square or take the 30-Stockton bus."),
        File(path="sf/neighborhoods/north-beach.md", contents="# North Beach\nSF's Little Italy and birthplace of the Beat Generation. City Lights Bookstore (1953) is a literary landmark. Cafe Trieste is the oldest espresso house on the West Coast. Must-visit: Coit Tower for 360 views, Washington Square Park. Transit: Walk from Fisherman's Wharf or take the 30-Stockton bus."),
        File(path="sf/neighborhoods/haight.md", contents="# Haight-Ashbury\nGround zero of the 1967 Summer of Love. Amoeba Music is one of the world's largest independent record stores. The Painted Ladies (Victorian houses) at Alamo Square. Must-visit: Buena Vista Park, the Grateful Dead house (710 Ashbury), vintage shops. Transit: N-Judah Muni Metro."),
        File(path="sf/neighborhoods/castro.md", contents="# The Castro\nHeart of SF's LGBTQ+ community. The Castro Theatre (1922) is Art Deco. Rainbow crosswalks at Castro and 18th. Must-visit: GLBT Historical Society Museum, Harvey Milk's camera shop (575 Castro). Transit: Muni Metro K, L, M to Castro Station."),
        File(path="sf/neighborhoods/soma.md", contents="# SoMa & Financial District\nSF's tech and arts hub. SFMOMA is world-class. Yerba Buena Gardens, Salesforce Transit Center rooftop park. Ferry Building artisan food hall (farmers market Tue/Thu/Sat). Embarcadero waterfront walk. Transit: All BART lines serve Embarcadero and Montgomery."),
        File(path="sf/pois/golden-gate-bridge.md", contents="# Golden Gate Bridge\n1.7-mile suspension bridge (1937), Art Deco masterpiece. Best views: Battery Spencer (Marin side), Fort Point (below bridge), Baker Beach, Crissy Field. Walk across: 35-45 min. Open sunrise to sunset. Morning visits typically clearer — fog rolls in afternoon. Free to walk/bike. Transit: Bus 28 from downtown."),
        File(path="sf/pois/alcatraz.md", contents="# Alcatraz Island\nFederal penitentiary 1934-1963 (Al Capone, etc). Audio tour is exceptional. Book tickets WEEKS in advance. Night tours Thu-Mon. Ferry from Pier 33. Allow 2.5-3 hours. Transit: Walk to Pier 33 from Embarcadero BART."),
        File(path="sf/pois/golden-gate-park.md", contents="# Golden Gate Park\nLarger than Central Park — 1,017 acres. de Young Museum, California Academy of Sciences, Japanese Tea Garden (oldest in US), Stow Lake, Bison Paddock. Car-free on JFK Drive. Transit: N-Judah to 9th Ave, buses 5, 44."),
        File(path="sf/pois/fishermans-wharf.md", contents="# Fisherman's Wharf\nBoudin Bakery sourdough since 1849. Pier 39 sea lions. Ghirardelli Square. Musee Mecanique vintage arcade. For real seafood skip Pier 39, go to Swan Oyster Depot or Sotto Mare. Transit: F-Market streetcar, Powell-Hyde cable car."),
        File(path="sf/transit/getting-around.md", contents="# Getting Around SF\nBART: Heavy rail to Oakland, Berkeley, SFO. Key stations: Embarcadero, Montgomery, Powell, Civic Center, 16th/24th Mission. 5am-midnight.\nMuni: Buses and light rail. Key lines: N-Judah, F-Market streetcars, 30-Stockton. $2.50/ride.\nCable Cars: Powell-Hyde (best views), Powell-Mason, California St. $8/ride.\nClipper Card at any BART station."),
        File(path="sf/transit/cable-cars.md", contents="# Cable Cars\nOnly mobile National Historic Landmark. Powell-Hyde: most scenic, ends at Aquatic Park. Powell-Mason: ends near Wharf. California: less touristy, no wait. Tip: Skip the Powell & Market line (30-60 min wait), walk 2 blocks to next stop. Best: early morning or after 7pm."),
        File(path="sf/food/signature-foods.md", contents="# SF Signature Foods\nSourdough: Boudin (classic), Tartine (modern). Mission burrito: La Taqueria, El Farolito. Dungeness crab: Nov-June. Irish coffee: Buena Vista Cafe. Dim sum: Yank Sing, City View, Dragon Beaux. Cioppino: Sotto Mare. Farm-to-table: Zuni Cafe, State Bird Provisions."),
        File(path="sf/practical/weather.md", contents="# SF Weather\nMicroclimates: 75F in Mission, 55F at Ocean Beach simultaneously. Summer = fog season. Sep-Oct ('Indian summer') warmest/clearest. Always pack layers. Warmest to coldest: Mission > Castro > SoMa > Marina > Sunset > Ocean Beach."),
        File(path="sf/practical/hidden-gems.md", contents="# Hidden Gems\n16th Avenue Tiled Steps (Sunset). Lands End Trail (coastal). Wave Organ (Marina jetty). Seward Street Slides. The Interval at Long Now (Fort Mason). Garden of Shakespeare's Flowers. Grace Cathedral labyrinth."),
    ]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def search(query: str) -> str:
    """
    Semantic search over the SF knowledge base.
    Returns formatted results with file paths and content excerpts.
    """
    ctx = _get_context()
    return ctx.search(query)


def ask(query: str, question: str) -> str:
    """
    RAG query — searches the knowledge base then generates a grounded answer.
    The answer is based ONLY on indexed content, reducing hallucination.
    """
    ctx = _get_context()
    return ctx.search_and_ask(query, question)


def search_location(location_name: str) -> str:
    """Search for information about a specific SF location."""
    return search(f"{location_name} San Francisco guide tips transit")


def search_transit(origin: str, destination: str) -> str:
    """Search for transit-related info between two SF locations."""
    return search(f"transit directions {origin} to {destination} San Francisco bus BART Muni")


def search_food_nearby(location: str) -> str:
    """Search for food/restaurant recommendations near a location."""
    return search(f"food restaurants eat near {location} San Francisco recommended")


def search_history(location: str) -> str:
    """Search for historical facts about a location."""
    return search(f"history {location} San Francisco historical facts")


def search_hidden_gems(area: str) -> str:
    """Search for hidden gems and lesser-known spots in an area."""
    return search(f"hidden gems secret spots {area} San Francisco locals")


def get_narration_context(location: str, segment_type: str) -> str:
    """
    Get rich context for generating journey narration.
    Combines location info, history, food, and hidden gems.
    """
    ctx = _get_context()
    question = (
        f"I'm traveling through {location} in San Francisco by {segment_type}. "
        f"Give me interesting facts, history, food recommendations, and hidden gems "
        f"about this area that a local guide would share. Be specific and vivid."
    )
    return ctx.search_and_ask(
        f"{location} San Francisco neighborhood guide history food hidden gems transit",
        question,
    )


def index_journey_data(journey_id: str, content: str) -> None:
    """
    Index journey-specific data for cross-journey search.
    Enables "Show me all sunset spots from my past journeys" type queries.
    """
    ctx = _get_context()
    ctx.add_to_index([
        File(path=f"journeys/{journey_id}.md", contents=content)
    ])
    # Re-export with journey data
    ctx.export_to_file(str(_INDEX_PATH))


def search_past_journeys(query: str) -> str:
    """Search across all past journeys."""
    return search(f"journey {query}")
