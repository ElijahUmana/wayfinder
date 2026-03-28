"""
San Francisco City Guide Knowledge Base
Powered by Augment Code's Context Engine SDK (auggie-sdk)

This module provides:
  1. SFKnowledgeBase - indexes city guide data and provides semantic search + RAG
  2. Pre-built SF data loader with 20+ documents covering neighborhoods, transit, POIs, history
  3. FastAPI integration with /search and /ask endpoints
  4. Index persistence (export/import) so you don't re-index on every restart

Requirements:
  pip install auggie-sdk fastapi uvicorn

Authentication (pick one, in priority order):
  1. Pass api_key/api_url directly
  2. Set AUGMENT_API_TOKEN and AUGMENT_API_URL env vars
  3. Run `auggie login` (creates ~/.augment/session.json) -- EASIEST
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from auggie_sdk.context import DirectContext, File


# ---------------------------------------------------------------------------
# Knowledge Base wrapper
# ---------------------------------------------------------------------------

@dataclass
class SearchResult:
    """Structured search result from the knowledge base."""
    query: str
    raw_results: str          # Formatted string from Context Engine (includes paths + content)
    elapsed_ms: float


@dataclass
class AskResult:
    """Structured RAG result from the knowledge base."""
    query: str
    prompt: Optional[str]
    answer: str               # LLM-generated answer grounded in indexed data
    elapsed_ms: float


class SFKnowledgeBase:
    """
    Semantic search over San Francisco city guide data using Augment's Context Engine.

    The Context Engine handles:
      - Chunking and embedding your documents
      - Semantic vector search (not keyword matching)
      - RAG (search + LLM answer generation) via search_and_ask

    Usage:
        kb = SFKnowledgeBase.create()
        kb.load_sf_data()                           # Index all SF documents
        kb.export_index("./sf-index.json")          # Persist for fast restarts

        results = kb.search("best dim sum")
        answer = kb.ask("best dim sum", "Where should I get dim sum in SF?")

    Restore from saved index:
        kb = SFKnowledgeBase.from_saved("./sf-index.json")
        answer = kb.ask("transit tips", "How do I get from SFO to downtown?")
    """

    def __init__(self, ctx: DirectContext):
        self._ctx = ctx

    # -- Factory methods --

    @classmethod
    def create(
        cls,
        *,
        api_key: Optional[str] = None,
        api_url: Optional[str] = None,
        debug: bool = False,
    ) -> "SFKnowledgeBase":
        """Create a new empty knowledge base. Auth resolves automatically."""
        ctx = DirectContext.create(api_key=api_key, api_url=api_url, debug=debug)
        return cls(ctx)

    @classmethod
    def from_saved(
        cls,
        index_path: str,
        *,
        api_key: Optional[str] = None,
        api_url: Optional[str] = None,
        debug: bool = False,
    ) -> "SFKnowledgeBase":
        """Restore from a previously exported index file (skips re-indexing)."""
        ctx = DirectContext.import_from_file(
            index_path, api_key=api_key, api_url=api_url, debug=debug
        )
        return cls(ctx)

    # -- Core operations --

    def index_documents(self, files: list[File], wait: bool = True) -> dict:
        """
        Add documents to the semantic index.

        Args:
            files: List of File(path, contents) to index. Path is a virtual
                   identifier (doesn't need to be a real filesystem path).
                   Contents is plain text, markdown, JSON-as-string, etc.
            wait: If True (default), blocks until indexing is complete.

        Returns:
            Dict with 'newly_uploaded' and 'already_uploaded' path lists.
        """
        result = self._ctx.add_to_index(files, wait_for_indexing=wait)
        return {
            "newly_uploaded": result.newly_uploaded,
            "already_uploaded": result.already_uploaded,
        }

    def search(self, query: str, max_length: Optional[int] = None) -> SearchResult:
        """
        Semantic search over indexed documents.

        Args:
            query: Natural language query (e.g. "best viewpoints in SF")
            max_length: Max character length of results (default 20000, max 80000)

        Returns:
            SearchResult with formatted results ready for LLM consumption.
        """
        t0 = time.monotonic()
        raw = self._ctx.search(query, max_output_length=max_length)
        elapsed = (time.monotonic() - t0) * 1000
        return SearchResult(query=query, raw_results=raw, elapsed_ms=round(elapsed, 1))

    def ask(self, search_query: str, prompt: Optional[str] = None) -> AskResult:
        """
        RAG: semantic search + LLM answer generation.

        Args:
            search_query: What to search for in the knowledge base.
            prompt: Question to answer using the search results.
                    If None, search_query is used as the prompt too.

        Returns:
            AskResult with the LLM's grounded answer.
        """
        t0 = time.monotonic()
        answer = self._ctx.search_and_ask(search_query, prompt)
        elapsed = (time.monotonic() - t0) * 1000
        return AskResult(
            query=search_query,
            prompt=prompt,
            answer=answer,
            elapsed_ms=round(elapsed, 1),
        )

    def export_index(self, path: str) -> None:
        """Export the current index state to a JSON file for fast restarts."""
        self._ctx.export_to_file(path)

    def get_indexed_paths(self) -> list[str]:
        """Return all document paths currently in the index."""
        return self._ctx.get_indexed_paths()

    def remove_documents(self, paths: list[str]) -> None:
        """Remove specific documents from the index by path."""
        self._ctx.remove_from_index(paths)

    def clear(self) -> None:
        """Remove all documents from the index."""
        self._ctx.clear_index()

    # -- Convenience: load all SF data --

    def load_sf_data(self) -> dict:
        """Index all pre-built San Francisco city guide documents."""
        files = get_sf_documents()
        return self.index_documents(files)

    def load_from_directory(self, directory: str, glob_pattern: str = "**/*.md") -> dict:
        """
        Index all matching files from a local directory.

        Args:
            directory: Path to directory containing knowledge base files.
            glob_pattern: File pattern to match (default: all .md files recursively).

        Returns:
            Indexing result dict.
        """
        dir_path = Path(directory)
        if not dir_path.is_dir():
            raise FileNotFoundError(f"Directory not found: {directory}")

        files = []
        for file_path in sorted(dir_path.glob(glob_pattern)):
            if file_path.is_file():
                contents = file_path.read_text(encoding="utf-8")
                # Use relative path as the virtual path
                rel = str(file_path.relative_to(dir_path))
                files.append(File(path=rel, contents=contents))

        if not files:
            raise ValueError(f"No files matching '{glob_pattern}' found in {directory}")

        return self.index_documents(files)


# ---------------------------------------------------------------------------
# San Francisco City Guide Data
# ---------------------------------------------------------------------------

def get_sf_documents() -> list[File]:
    """
    Returns 20+ documents covering SF neighborhoods, POIs, transit, food,
    history, and practical tips. Each document is a File(path, contents).
    """
    return [
        # --- Neighborhoods ---
        File(
            path="neighborhoods/mission-district.md",
            contents="""# The Mission District
The Mission District is one of San Francisco's most vibrant and culturally rich neighborhoods. Named after Mission Dolores (founded 1776), it is the oldest neighborhood in the city.

## Character
- Heart of SF's Latino community with murals, taquerias, and cultural institutions
- Rapidly gentrifying but retains strong cultural identity
- Known for having the warmest, sunniest microclimate in the city (protected from fog by Twin Peaks)

## Key Streets
- **Valencia Street**: Trendy restaurants, bookshops (Dog Eared Books, Adobe Books), bars, and boutiques
- **Mission Street**: More traditional, taquerias, discount stores, produce markets
- **24th Street**: Cultural corridor with murals, panaderias, and community organizations

## Must-See
- **Balmy Alley**: Entire alleyway covered in stunning murals depicting Latin American history and social justice themes
- **Clarion Alley**: Another mural alley near Valencia, more contemporary/experimental art
- **Mission Dolores**: Founded June 29, 1776 - the oldest surviving structure in San Francisco
- **Dolores Park**: Hilltop park with panoramic city views, popular weekend gathering spot

## Food Highlights
- **La Taqueria** (2889 Mission St): Legendary burritos, James Beard Award winner
- **Tartine Bakery** (600 Guerrero St): World-famous sourdough and morning buns
- **Bi-Rite Creamery** (3692 18th St): Artisan ice cream, long lines worth the wait
- **El Farolito** (2779 Mission St): Best late-night super burritos

## Getting There
- BART: 16th St Mission or 24th St Mission stations
- Muni: 14-Mission, 49-Van Ness/Mission, 33-Ashbury/18th
""",
        ),
        File(
            path="neighborhoods/chinatown.md",
            contents="""# Chinatown
San Francisco's Chinatown is the oldest in North America (established 1848) and the most densely populated neighborhood west of Manhattan. It is a living, working neighborhood — not a tourist attraction.

## Boundaries
Roughly bounded by Bush Street (south), Broadway (north), Kearny Street (east), and Powell Street (west). The iconic Dragon's Gate at Grant Avenue and Bush Street marks the formal entrance.

## Key Streets
- **Grant Avenue**: Tourist-facing street with souvenir shops, restaurants, and the ornamental streetlamps
- **Stockton Street**: Where locals shop — produce markets, live seafood, herbal medicine shops, and bakeries
- **Waverly Place**: "Street of Painted Balconies" — ornate temple buildings, Tin How Temple (oldest Chinese temple in US, est. 1852)
- **Ross Alley**: Narrow alley with Golden Gate Fortune Cookie Factory (watch cookies being made by hand)

## History
- Chinese immigrants arrived during the Gold Rush (1848-1855) and later built the Transcontinental Railroad
- The 1906 earthquake and fire destroyed original Chinatown; rebuilt with deliberate "Oriental" architecture to attract tourists and prevent displacement
- Underwent decades of exclusion laws (Chinese Exclusion Act 1882-1943)
- Today home to ~15,000 residents, many elderly Cantonese speakers

## Food Highlights
- **R&G Lounge** (631 Kearny St): Michelin-recognized Cantonese, famous salt-and-pepper crab
- **Good Mong Kok Bakery** (1039 Stockton St): Best char siu bao (BBQ pork buns) in SF
- **City View Restaurant** (662 Commercial St): Excellent dim sum
- **Sam Wo Restaurant** (713 Clay St): Historic late-night noodle house, reopened after renovation
- **Golden Gate Bakery** (1029 Grant Ave): Legendary egg tarts (warning: erratic hours)

## Getting There
- BART/Muni: Powell St station, walk north on Grant Ave
- Muni bus: 1-California, 30-Stockton, 45-Union/Stockton
- Cable Car: Powell-Mason line stops at Washington/Mason (edge of Chinatown)
""",
        ),
        File(
            path="neighborhoods/north-beach.md",
            contents="""# North Beach
San Francisco's "Little Italy" — a neighborhood defined by Italian heritage, Beat Generation literary history, and vibrant nightlife.

## Character
- Italian delis, cafes, and restaurants along Columbus Avenue
- Beat Generation landmarks: City Lights Bookstore, Vesuvio Cafe, Caffe Trieste
- Adjacent to Chinatown (walking distance) and below Telegraph Hill/Coit Tower
- Lively bar scene along Broadway and Columbus

## Must-See
- **City Lights Bookstore** (261 Columbus Ave): Founded 1953 by Lawrence Ferlinghetti, epicenter of the Beat movement. Published Allen Ginsberg's "Howl." Independent bookstore with incredible poetry section.
- **Coit Tower** (atop Telegraph Hill): 210-foot art deco tower with WPA murals inside and 360-degree city views from the top. Free to enter lobby; $10 to ride elevator to top.
- **Washington Square Park**: Heart of the neighborhood, morning tai chi, surrounded by Italian cafes
- **Vesuvio Cafe** (255 Columbus Ave): Historic Beat hangout next to City Lights, great for a drink

## Food Highlights
- **Tony's Pizza Napoletana** (1570 Stockton St): World Pizza Champion Tony Gemignani's flagship, 7+ styles of pizza
- **Liguria Bakery** (1700 Stockton St): Only sells focaccia, opens 8am, sells out by noon. Cash only.
- **Mama's on Washington Square** (1701 Stockton St): Legendary brunch, expect 1-2 hour wait on weekends
- **Caffe Trieste** (601 Vallejo St): Oldest espresso house on the West Coast (1956), Saturday Italian music sessions
- **Molinari Delicatessen** (373 Columbus Ave): Classic Italian deli since 1896

## Getting There
- Muni: 30-Stockton, 45-Union/Stockton, 8-Bayshore
- Walk from Chinatown (5 min), Fisherman's Wharf (10 min), or Financial District (10 min)
""",
        ),
        File(
            path="neighborhoods/haight-ashbury.md",
            contents="""# Haight-Ashbury
Ground zero of the 1967 Summer of Love and the counterculture movement. Today it blends hippie heritage with Victorian architecture and eclectic shops.

## History
- 1960s: Became the epicenter of the hippie movement. The Grateful Dead lived at 710 Ashbury St. Janis Joplin lived at 112 Lyon St.
- **Summer of Love (1967)**: ~100,000 young people descended on the neighborhood. Free concerts in Golden Gate Park, communal living, psychedelic culture.
- The intersection of Haight and Ashbury streets became a global symbol of counterculture.

## Today
- Vintage clothing stores (Wasteland, Held Over), record shops (Amoeba Music — now moved to Haight from original location), head shops
- Beautiful Victorian and Edwardian houses, including the famous "Painted Ladies" nearby at Alamo Square
- Gateway to the east end of Golden Gate Park

## Must-See
- **Haight & Ashbury intersection**: The famous street sign, photo op
- **Amoeba Music**: Massive independent record store (if still at Haight location)
- **Buena Vista Park**: Oldest park in SF (1867), forested hilltop with views
- **The Panhandle**: Narrow strip of Golden Gate Park extending into the neighborhood, great for walking/biking

## Getting There
- Muni: 6-Haight/Parnassus, 7-Haight/Noriega, 33-Ashbury/18th, 43-Masonic
- Walk from Golden Gate Park's east entrance
""",
        ),
        File(
            path="neighborhoods/castro.md",
            contents="""# The Castro
The Castro is the historic heart of San Francisco's LGBTQ+ community and one of the first openly gay neighborhoods in the United States.

## History
- Became an LGBTQ+ neighborhood in the 1960s-70s as gay men moved from the Tenderloin/Polk Street area
- **Harvey Milk** opened Castro Camera at 575 Castro St in 1972, became the first openly gay elected official in California (1977)
- Harvey Milk was assassinated along with Mayor George Moscone on November 27, 1978
- The neighborhood was devastated by the AIDS crisis in the 1980s-90s
- Today: A symbol of LGBTQ+ rights worldwide, though gentrification has changed its character

## Must-See
- **Castro Theatre** (429 Castro St): 1922 Spanish Colonial Baroque movie palace, recently renovated. Iconic neon marquee.
- **Rainbow Crosswalks**: Permanent rainbow-painted crosswalks at Castro & 18th
- **Harvey Milk Plaza**: At Castro & Market, with a large rainbow flag
- **GLBT Historical Society Museum** (4127 18th St): Exhibits on LGBTQ+ history
- **Pink Triangle Park**: Memorial at 17th & Market, honors LGBTQ+ victims of the Holocaust

## Getting There
- Muni Metro: Castro station (K, L, M lines)
- Muni bus: 24-Divisadero, 33-Ashbury/18th, 35-Eureka, 37-Corbett
- Walk from Mission Dolores (10 min)
""",
        ),
        File(
            path="neighborhoods/pacific-heights-marina.md",
            contents="""# Pacific Heights & The Marina

## Pacific Heights
San Francisco's wealthiest residential neighborhood with stunning Victorian mansions and panoramic views.

- **Fillmore Street**: Upscale shopping and dining corridor
- **Lyon Street Steps**: 288 steps with views of the Palace of Fine Arts, Bay, and Alcatraz
- **Billionaire's Row (Broadway)**: Some of the most expensive homes in SF ($20M+)
- **Alta Plaza Park**: Terraced park with city views, featured in films

## The Marina
Flat, waterfront neighborhood popular with young professionals. Built on fill from the 1906 earthquake rubble and 1915 Panama-Pacific Exhibition.

- **Chestnut Street**: Restaurants, bars, boutiques — the commercial heart
- **Marina Green**: Waterfront park perfect for jogging, kite-flying, picnics with Golden Gate Bridge views
- **Palace of Fine Arts**: Romanesque rotunda and colonnade, originally built for 1915 exposition, reconstructed 1965. Free to visit, stunning at sunset.
- **Fort Mason Center**: Former military base, now arts/cultural center with restaurants (Greens vegetarian restaurant), galleries, and events
- **Wave Organ**: Acoustic sculpture on a jetty — waves create sounds through pipes. Best at high tide.

## Getting There
- Muni: 30-Stockton, 22-Fillmore, 28-19th Avenue, 43-Masonic
- Walk from Fisherman's Wharf along the waterfront
""",
        ),
        File(
            path="neighborhoods/soma-fidi.md",
            contents="""# SoMa & Financial District

## SoMa (South of Market)
San Francisco's largest neighborhood by area, encompassing tech offices, museums, nightclubs, and residential developments.

### Museums
- **SFMOMA** (151 3rd St): San Francisco Museum of Modern Art, 170,000+ sq ft, expanded 2016. Incredible collection of modern and contemporary art. Adults $25.
- **Yerba Buena Center for the Arts**: Adjacent to SFMOMA, contemporary art exhibitions and performances
- **California Academy of Sciences**: In Golden Gate Park (not SoMa), but worth noting — aquarium, planetarium, rainforest dome, living roof
- **Exploratorium** (Pier 15): Hands-on science museum on the Embarcadero, amazing for all ages

### Key Areas
- **Yerba Buena Gardens**: Urban park between 3rd/4th and Mission/Howard, with waterfall memorial to MLK Jr.
- **Oracle Park**: Home of the SF Giants (baseball), beautiful waterfront ballpark at 3rd & King
- **Chase Center**: Home of the Golden State Warriors (basketball), in Mission Bay

## Financial District
- **Transamerica Pyramid** (600 Montgomery St): Iconic 1972 pyramid-shaped skyscraper, 853 feet tall
- **Ferry Building** (foot of Market St): 1898 Beaux-Arts building, now a gourmet marketplace. Saturday farmers market is legendary. Don't miss: Acme Bread, Cowgirl Creamery, Blue Bottle Coffee, Hog Island Oysters.
- **Embarcadero**: Waterfront promenade from Fisherman's Wharf to Oracle Park, great for walking/biking

## Getting There
- BART: Montgomery, Embarcadero, or Powell stations
- Muni: Many lines converge on Market Street
- Caltrain: 4th & King station (SoMa)
""",
        ),

        # --- Major POIs ---
        File(
            path="pois/golden-gate-bridge.md",
            contents="""# Golden Gate Bridge
The Golden Gate Bridge is the most iconic landmark in San Francisco and one of the most photographed bridges in the world.

## Facts
- **Opened**: May 27, 1937
- **Length**: 8,981 feet (1.7 miles) total; 4,200-foot main span
- **Height**: 746 feet (towers), 220 feet (roadway above water)
- **Color**: "International Orange" — chosen for visibility in fog and aesthetic harmony with the landscape. NOT red.
- **Engineer**: Joseph Strauss (chief), Irving Morrow (architect/design), Charles Ellis (structural engineering)
- **Cost**: $35 million (1937 dollars)
- **Daily traffic**: ~112,000 vehicles

## Visiting
- **Walk/bike across**: Free, pedestrians on east sidewalk (5am-6:30pm summer, 5am-6pm winter). Bikes allowed on both sidewalks depending on time. Takes ~30-45 minutes to walk one way.
- **Toll**: $8.80 southbound only (electronic only, no cash). Use FasTrak or pay online within 48 hours.
- **Best photo spots**:
  - Battery Spencer (Marin side, north): Classic overhead angle
  - Fort Point (south, underneath the bridge): Dramatic perspective
  - Baker Beach (south, west side): Beach with bridge backdrop
  - Crissy Field (south, east side): Full bridge view with city
  - Hawk Hill (Marin Headlands): Elevated panoramic view

## Getting There
- Muni bus: 28-19th Avenue to the bridge parking lot
- Bike: Rent from Fisherman's Wharf, ride through Crissy Field (~30 min)
- Drive: Parking at the Welcome Center (southeast side), limited on weekends
- Walk: From the Presidio via the Coastal Trail
""",
        ),
        File(
            path="pois/alcatraz.md",
            contents="""# Alcatraz Island
A former federal penitentiary on a rocky island in San Francisco Bay, now a national park and one of the city's most popular attractions.

## History
- Originally a military fortification (1850s)
- Federal penitentiary: 1934-1963
- Famous inmates: Al Capone, Robert "Birdman" Stroud, George "Machine Gun" Kelly
- **1962 escape**: Frank Morris and the Anglin brothers — the only inmates believed to have possibly survived an escape attempt. Their fate remains unknown.
- Occupied by Native American activists 1969-1971 (Indians of All Tribes)
- Became part of Golden Gate National Recreation Area in 1972

## Visiting
- **BOOK IN ADVANCE**: Tickets sell out days/weeks ahead, especially in summer. Book at alcatrazcruises.com.
- **Day tour**: Departs from Pier 33 every 30 min, 8:45am-3:50pm. Adults ~$42. Includes ferry + audio tour (narrated by former guards and inmates — excellent).
- **Night tour**: Limited availability, departs 5:55pm or 6:30pm. ~$52. More atmospheric, smaller crowds, sunset views.
- **Behind the Scenes tour**: Seasonal, explores areas not on the standard tour.
- **Duration**: Plan 2.5-3 hours total (ferry ride + island time)

## Tips
- Wear layers — it is ALWAYS windy and cold on the island
- Audio tour is included and is genuinely one of the best audio tours anywhere
- Bring water and snacks (no food sold on island)
- The gardens are surprisingly beautiful (maintained by volunteers)

## Getting There
- All ferries depart from Pier 33 (Alcatraz Landing), NOT Fisherman's Wharf
- Pier 33 is a 10-minute walk east of Fisherman's Wharf
- Muni: F-Market streetcar to Pier 33 stop
""",
        ),
        File(
            path="pois/golden-gate-park.md",
            contents="""# Golden Gate Park
A 1,017-acre urban park stretching from the Haight-Ashbury neighborhood to the Pacific Ocean — larger than Central Park.

## Key Attractions
- **California Academy of Sciences**: Natural history museum + aquarium + planetarium + rainforest dome under a living roof. Adults $42. Thursday nights (21+) are popular.
- **de Young Museum**: Fine art museum with a free observation tower offering 360-degree views. Adults $15.
- **Japanese Tea Garden**: Oldest public Japanese garden in the US (1894). Beautiful pagodas, koi ponds, arched bridges. Adults $13. Free before 10am Mon/Wed/Fri.
- **Conservatory of Flowers**: Victorian greenhouse (1879) with exotic tropical plants. Adults $12.
- **San Francisco Botanical Garden**: 55 acres with 9,000+ plant species. Free for SF residents, $13 for visitors.
- **Stow Lake**: Rent paddle boats, walk around the lake, climb Strawberry Hill for views
- **Bison Paddock**: Yes, there are actual bison in Golden Gate Park since 1891
- **Dutch Windmill & Tulip Garden**: Western edge of the park, stunning in spring
- **Music Concourse**: Open-air plaza between the de Young and Academy of Sciences, free concerts

## Activities
- Biking: Rent bikes on Stanyan St or Haight St, ride through the park to Ocean Beach
- Sunday car-free: JFK Drive is permanently car-free, perfect for biking/skating/walking
- Disc golf course near the polo fields
- Lawn bowling, tennis, archery, fly casting pools

## Getting There
- Muni: N-Judah (south side), 5-Fulton (north side), 7-Haight/Noriega
- Entrance from Haight-Ashbury at Stanyan & Haight
- Parking: Very limited on weekends; use transit
""",
        ),
        File(
            path="pois/fishermans-wharf.md",
            contents="""# Fisherman's Wharf
San Francisco's most visited tourist area, stretching along the northern waterfront from Pier 39 to Ghirardelli Square.

## What's Actually Worth Doing (vs Tourist Traps)

### Worth It
- **Musee Mecanique** (Pier 45): Free admission, 200+ antique arcade machines and mechanical curiosities. Genuinely delightful.
- **Ghirardelli Square**: The hot fudge sundae at the original Ghirardelli chocolate shop is a legitimate treat
- **Sea Lions at Pier 39**: Free to watch from the viewing platforms. K-Dock. They arrived after the 1989 earthquake and never left. Loudest in winter/spring.
- **Hyde Street Pier / San Francisco Maritime National Historical Park**: Board historic ships (1886 square-rigger Balclutha, 1890 ferry Eureka). Adults $15.
- **Cable Car turnaround**: The Powell-Hyde line terminates at Aquatic Park — ride it UP from here (shorter line than Powell & Market)
- **Boudin Bakery**: Watch sourdough bread being made through the window. The bread bowls of clam chowder are touristy but good.

### Skip
- Most Pier 39 shops (generic souvenirs)
- "Authentic" seafood restaurants along Jefferson Street (overpriced, mediocre)

### Better Seafood Options Nearby
- **Swan Oyster Depot** (1517 Polk St, 15 min walk): Counter-only, legendary raw bar. Cash only. Open 10:30am-5:30pm, closed Sunday. Line forms early.
- **Scoma's** (Pier 47): Actually on the wharf, actually good. Founded 1965.
- **In-N-Out Burger** (333 Jefferson St): Yes, it's a chain, but this location has insane views of Alcatraz and the Golden Gate Bridge

## Getting There
- Cable Car: Powell-Hyde or Powell-Mason lines
- Muni: F-Market historic streetcar
- Walk from Pier 33 (Alcatraz ferry), North Beach, or Marina
""",
        ),

        # --- Transit ---
        File(
            path="transit/getting-around.md",
            contents="""# Getting Around San Francisco

## From the Airports

### SFO (San Francisco International)
- **BART** (best option): Direct train to downtown, 30 min, ~$10. Runs 5am-midnight (shorter hours Sun).
- **SamTrans bus**: Cheaper ($2.25) but slower
- **Rideshare/Taxi**: $35-60 to downtown, 20-45 min depending on traffic
- **Rental car**: Usually unnecessary in SF proper. Parking is $30-60/day downtown.

### OAK (Oakland International)
- **BART**: Take AirBART shuttle to Coliseum BART station, then BART to SF. ~45 min total, ~$12.
- **Rideshare**: $40-70 to SF

## Within San Francisco

### BART (Bay Area Rapid Transit)
- Heavy rail system connecting SF to East Bay (Oakland, Berkeley) and SFO
- Within SF: 8 stations along Market Street + Balboa Park, Glen Park, Daly City
- Fare: Distance-based ($2.15-$12.80). Use Clipper card.
- Runs 5am-midnight weekdays, shorter weekends

### Muni (SF Municipal Transit)
- **Buses**: Extensive network covering the entire city. Key routes: 38-Geary, 30-Stockton, 14-Mission
- **Metro (light rail)**: J, K, L, M, N, T lines. Underground downtown, surface in neighborhoods
- **F-Market streetcar**: Historic vintage streetcars along Market St to Fisherman's Wharf. Scenic + functional.
- **Cable Cars**: Three lines — Powell-Hyde, Powell-Mason, California Street. $8/ride. Iconic but slow.
- **Fare**: $2.50 single ride (bus/metro), free transfers within 2 hours. $5 for cable car. Use Clipper card or MuniMobile app.
- **Muni Passport**: $13/day, $31/3-day, $41/7-day — unlimited Muni including cable cars

### Clipper Card
- Reloadable transit card for BART, Muni, Caltrain, ferries, and more
- Get at Walgreens, BART stations, or online
- Tap on AND off for BART; just tap on for Muni

### Biking
- **Bay Wheels (Lyft)**: Bikeshare, stations throughout the city. $3/trip or day pass.
- **E-bike rentals**: Many shops near Fisherman's Wharf. ~$35-65/day.
- **Great routes**: Embarcadero waterfront, Golden Gate Park (car-free JFK Drive), across the Golden Gate Bridge to Sausalito

### Rideshare/Taxi
- Uber and Lyft widely available
- Taxis: Flywheel app or street hail. ~$3.50 base + $2.75/mile

### Ferry
- **Golden Gate Ferry**: SF Ferry Building to Sausalito ($14) or Larkspur ($13). Scenic commuter ferry with bar.
- **SF Bay Ferry**: To Oakland/Alameda, Vallejo, Richmond. From Ferry Building.

## Pro Tips
- **Hills are real**: San Francisco is EXTREMELY hilly. Plan walking routes accordingly. The steepest streets exceed 30% grade.
- **Fog**: Summer is the foggiest season (June-August). "The coldest winter I ever spent was a summer in San Francisco." Dress in layers.
- **Parking**: Street parking requires reading signs carefully (street cleaning days, permit zones, time limits). Meters enforced until 10pm in busy areas. Curb your wheels on hills (it's the law — $200 fine).
- **Don't leave ANYTHING visible in your car**: Car break-ins are extremely common, especially at tourist spots. Trunk isn't safe either — they watch you put bags in.
""",
        ),
        File(
            path="transit/cable-cars.md",
            contents="""# Cable Cars
San Francisco's cable cars are the last manually operated cable car system in the world and a National Historic Landmark.

## The Three Lines
1. **Powell-Hyde**: Most scenic. From Powell & Market to Aquatic Park (near Ghirardelli Square). Passes Russian Hill with views of Alcatraz, the bay, and Lombard Street.
2. **Powell-Mason**: From Powell & Market to Bay & Taylor (near Fisherman's Wharf). Less scenic but shorter lines.
3. **California Street**: Runs east-west along California St from Market Street through Chinatown to Van Ness. Least crowded, double-ended car (no turntable).

## How They Work
- Grip mechanism clamps onto a continuously moving underground cable (9.5 mph)
- The "gripman" operates the grip lever and two brake systems
- Cars weigh about 8 tons each
- The cable runs through a slot in the street, powered by engines at the Cable Car Barn (1201 Mason St — free museum, open 10am-5pm)

## Tips
- **$8 per ride** (one way, any distance). Free with Muni Passport.
- **Lines are long** at Powell & Market turntable (30-60 min on weekends). Skip the line by:
  - Boarding at intermediate stops (not guaranteed a spot, but no line)
  - Walking 1-2 blocks up from the turntable
  - Taking the California Street line (rarely has a line)
  - Boarding at the Hyde St turnaround (Fisherman's Wharf end of Powell-Hyde)
- **Hang off the side** (standing on the running board) for the full experience
- **Hours**: ~6am-12:30am daily
""",
        ),

        # --- History ---
        File(
            path="history/earthquake-fire-1906.md",
            contents="""# The 1906 Earthquake and Fire
The most significant event in San Francisco's history. On April 18, 1906, at 5:12 AM, a massive earthquake (estimated 7.9 magnitude) struck along the San Andreas Fault.

## The Earthquake
- Lasted about 45-60 seconds
- Felt from Oregon to Los Angeles, inland to Nevada
- The ground displacement was up to 28 feet along the fault line

## The Fire
- The earthquake ruptured gas mains and water pipes throughout the city
- Fires broke out immediately and burned for three days (April 18-21)
- With water mains broken, firefighters could not stop the blazes
- The military used dynamite to create firebreaks, sometimes making things worse
- 80% of the city was destroyed — primarily by fire, not the earthquake itself

## Impact
- ~3,000 people killed (originally reported as 478 — the city suppressed the real number)
- 225,000-300,000 left homeless (out of a population of 410,000)
- 28,000+ buildings destroyed
- Refugee camps in Golden Gate Park, the Presidio, and other open spaces
- Insurance claims led to the bankruptcy of several major insurance companies

## Rebuilding
- The city rebuilt with remarkable speed — most of the downtown was rebuilt within 3 years
- Chinatown was rebuilt with deliberate "Chinese" architecture (designed by white architects) to establish it as a tourist destination
- The disaster led to major advances in building codes and fire safety
- San Francisco hosted the 1915 Panama-Pacific International Exposition to showcase its recovery

## Visiting
- **1906 Earthquake hydrant** (20th & Church): The one hydrant that still worked, painted gold annually on the anniversary
- **Cable Car Museum**: Photos and artifacts from the earthquake
- **SF Public Library**: Extensive photo collection
""",
        ),
        File(
            path="history/gold-rush.md",
            contents="""# The California Gold Rush and San Francisco
The discovery of gold at Sutter's Mill on January 24, 1848, transformed San Francisco from a tiny settlement (population ~200) into a booming city almost overnight.

## Timeline
- **January 1848**: James Marshall discovers gold at Sutter's Mill in Coloma, ~130 miles northeast of SF
- **May 1848**: Sam Brannan runs through SF streets waving a bottle of gold dust, shouting "Gold! Gold! Gold from the American River!" Population exodus begins.
- **1849**: ~90,000 people arrive in California — the "Forty-Niners." SF's population explodes from ~1,000 to ~25,000.
- **1850**: California becomes a state. SF becomes the de facto capital of the gold rush.
- **1855**: Easy surface gold is largely exhausted. Industrial mining takes over.

## Impact on San Francisco
- The city grew so fast that ships were abandoned in the harbor (crews deserted for gold fields). Many were converted into buildings or landfill — parts of today's Financial District are built on buried ships.
- **Barbary Coast** (now Jackson Square/North Beach area): Notorious red-light district with gambling halls, saloons, and brothels
- Chinese immigration began (eventually forming Chinatown)
- The city's culture of risk-taking, entrepreneurship, and booms/busts traces directly to the Gold Rush — and continues through tech today

## Gold Rush Sites in SF
- **Wells Fargo History Museum** (420 Montgomery St): Gold rush artifacts, original stagecoach
- **Jackson Square Historic District**: Some of the oldest commercial buildings in SF, survived the 1906 fire
- **SS City of Rio de Janeiro** marker: One of many ships buried under the city
""",
        ),

        # --- Food ---
        File(
            path="food/signature-foods.md",
            contents="""# San Francisco's Signature Foods

## Sourdough Bread
San Francisco sourdough has a unique tang from wild Lactobacillus sanfranciscensis bacteria (literally named after the city). The cool, foggy climate creates the perfect environment.
- **Tartine Bakery** (Mission): Country loaf drops at 5pm, line starts at 4
- **Boudin Bakery** (Fisherman's Wharf): Since 1849, oldest continually operating sourdough bakery in the city. Watch bread being made.
- **Josey Baker Bread** (The Mill): Whole-grain artisan focus

## Mission-Style Burrito
Invented in SF's Mission District in the 1960s. Distinguished by: steamed flour tortilla, rice included, everything wrapped in foil.
- **La Taqueria**: James Beard "best restaurant in America" — no rice in their burritos (purist style)
- **El Farolito**: Best super burrito, especially after midnight
- **Taqueria Cancun**: Another top contender on Mission Street
- **Papalote**: Known for their salsa (bottled and sold in stores)

## Cioppino
San Francisco's signature seafood stew, created by Italian fishermen in North Beach in the late 1800s. Tomato-based with Dungeness crab, shrimp, clams, mussels, fish.
- **Sotto Mare** (North Beach): Acclaimed "best cioppino"
- **Cioppino's** (Fisherman's Wharf): Named for the dish

## Dungeness Crab
Season runs November through June. Best at the wharf during crab season.
- **Crab stands on Fisherman's Wharf**: Fresh-cooked crab cocktails and crab sandwiches
- **Thanh Long** (Outer Sunset): Vietnamese-style roasted crab with garlic noodles — legendary

## Irish Coffee
Invented at the Buena Vista Cafe (2765 Hyde St) in 1952. They make 2,000+ per day. It's a legitimate must-try — not just a gimmick.

## Dim Sum
- **Yank Sing** (SoMa): Upscale, cart service, pricey but excellent
- **City View** (Chinatown): Great quality, reasonable prices
- **Good Luck Dim Sum** (Clement St / Inner Richmond): Cheap, takeout-style, excellent har gow

## It's-Its
Ice cream sandwiched between oatmeal cookies, dipped in chocolate. Originally sold at Playland-at-the-Beach (closed 1972). Now widely available in stores. A true SF treat.
""",
        ),
        File(
            path="food/coffee-culture.md",
            contents="""# San Francisco Coffee Culture
San Francisco is one of the most serious coffee cities in the world, home to several influential third-wave roasters.

## Iconic Roasters/Cafes
- **Blue Bottle Coffee**: Founded 2002 in Oakland, HQ in SF. Flagship at Ferry Building. Known for single-origin pour-overs and precise brewing. Multiple locations.
- **Sightglass Coffee**: Founded 2009, SoMa roastery on 7th St is a stunning industrial space. Emphasizes direct trade.
- **Ritual Coffee Roasters**: Founded 2005 in the Mission. One of the originators of SF's third-wave movement. Valencia St location is iconic.
- **Philz Coffee**: Founded 1978 in the Mission by Phil Jaber. Unique custom-blended drip style (not espresso-based). Each cup made individually. Mint Mojito Iced Coffee is the signature.
- **Four Barrel Coffee**: Mission District, minimalist aesthetic, excellent espresso
- **Verve Coffee Roasters**: Originally from Santa Cruz, Pacific Heights location
- **Caffe Trieste** (North Beach): Since 1956, oldest espresso house on the West Coast. No pour-overs — proper Italian espresso culture.

## The Ferry Building
The Ferry Building marketplace is a coffee destination itself:
- Blue Bottle
- Equator Coffees (first certified B Corp roaster)
- Peet's Coffee (founded in Berkeley 1966, the "grandfather" of specialty coffee on the West Coast)
""",
        ),

        # --- Practical Tips ---
        File(
            path="tips/weather-packing.md",
            contents="""# Weather & Packing Guide for San Francisco

## The Truth About SF Weather
"The coldest winter I ever spent was a summer in San Francisco." (Often attributed to Mark Twain, probably apocryphal, but accurate.)

### Summer (June-August) — The Fog Season
- Average high: 65°F (18°C). Average low: 54°F (12°C).
- Karl the Fog (yes, SF named its fog) rolls in through the Golden Gate most afternoons, especially June-July
- Can drop temperatures 15-20°F in minutes when fog arrives
- The Mission and downtown can be sunny while the Sunset/Richmond districts are socked in fog
- It is NOT warm California beach weather. Do NOT pack for summer as you would for LA.

### September-October — "Indian Summer" (Best Weather)
- The warmest months in SF. Highs can reach 75-80°F.
- Clear skies, minimal fog
- This is the best time to visit

### Winter (November-March)
- Rainy season, but mild. Highs: 55-60°F, Lows: 45-50°F.
- Rain is intermittent, not constant. Many sunny days between storms.
- Rarely drops below 40°F. Snow is essentially unheard of.

### Spring (April-May)
- Warming up, occasional fog, wildflowers
- Good visiting weather, fewer tourists than summer

## What to Pack
- **Layers**: The #1 rule. A t-shirt + sweater + windbreaker is the daily uniform.
- **Windbreaker/light jacket**: Essential. Not optional. Even in July.
- **Comfortable walking shoes**: The hills are steep (some streets exceed 30% grade). Flip-flops and heels are a bad idea.
- **Sunscreen**: The sun is strong when it's out, even when it feels cool
- **NO heavy winter coat**: Unless visiting Nov-Feb, a heavy coat is overkill. Layers work better.
""",
        ),
        File(
            path="tips/safety-and-etiquette.md",
            contents="""# Safety & Etiquette in San Francisco

## Safety
San Francisco is generally safe for tourists, but like any major city, awareness matters.

### Car Break-ins
- **THE #1 tourist crime in SF.** Do NOT leave anything visible in your car. Not a bag, not a jacket, not a phone charger. Nothing.
- Trunk is not safe — thieves watch you load it
- Worst spots: Fisherman's Wharf lots, Alamo Square, Golden Gate Park, any tourist viewpoint parking
- If renting a car, keep it completely empty when parked

### Areas to Be Aware Of
- **Tenderloin** (between Union Square and City Hall): Open drug use, homelessness. Not dangerous for most, but can be uncomfortable. Walk purposefully, avoid after dark if unfamiliar.
- **Mid-Market**: Similar to Tenderloin in parts
- **Some BART stations at night**: Civic Center/UN Plaza, 16th St Mission — be alert

### General Tips
- Keep phone in a secure pocket (snatch thefts happen)
- Tourist areas are heavily patrolled and generally safe
- 911 for emergencies, 311 for non-emergencies

## Etiquette
- **Don't call it "San Fran" or "Frisco"**: Locals will cringe. "SF" or "the city" is acceptable.
- **Tipping**: 18-20% at restaurants, $1-2 per drink at bars. Not optional.
- **Tech culture**: Be sensitive — tech gentrification is a sore topic for many longtime residents
- **Homelessness**: A visible, complex issue. Treat unhoused people with basic dignity and respect.
- **Eco-conscious**: SF is very environmentally conscious. Plastic bag ban, composting is mandatory, bring reusable bags.
""",
        ),
        File(
            path="tips/hidden-gems.md",
            contents="""# Hidden Gems & Locals' Favorites

## Viewpoints Most Tourists Miss
- **Tank Hill**: Small, unmarked hilltop in the center of the city with 360-degree views. No crowds. Sunset is magical. Access from Twin Peaks Blvd or Belgrave Ave.
- **Bernal Heights Hill**: Dog-friendly hilltop in Bernal Heights with panoramic views. Much less crowded than Twin Peaks.
- **Lands End Trail**: Coastal trail in the northwest corner of the city. Ruins of Sutro Baths, views of Golden Gate Bridge, rocky beaches. The Labyrinth (rock spiral on the cliff) is a popular photo spot.
- **16th Avenue Tiled Steps** (Moraga Steps): Mosaic-tiled stairway in the Sunset district. Beautiful at sunset. Nearby Hidden Garden Steps (16th Ave & Kirkham) is equally stunning and less known.

## Experiences
- **Stern Grove Festival** (June-August): Free Sunday concerts in a eucalyptus grove. Jazz, classical, pop, world music. Bring a blanket and a picnic.
- **Balmy Alley Mural Walk** (Mission): Self-guided tour of 30+ murals in a single block
- **Urban Putt** (Mission): Indoor miniature golf in a converted mortuary. Creative, whimsical. Good cocktails.
- **Musee Mecanique** (Pier 45): Free admission, hundreds of antique arcade machines
- **826 Valencia**: Dave Eggers' writing center for kids, fronted by a pirate supply store. Yes, a pirate supply store.

## Neighborhoods Worth Exploring (Beyond the Tourist Trail)
- **Inner Richmond / Clement Street**: SF's "other Chinatown" — amazing Chinese, Burmese, and Russian food. Green Apple Books (one of the best used bookstores in the US).
- **Noe Valley**: Quiet, family-friendly neighborhood on 24th Street with cafes and boutiques. Sunday farmers market.
- **Dogpatch**: Former industrial area turned hipster enclave. Anchor Brewing (now closed for tours, sadly), Museum of Craft and Design, great breweries.
- **Outer Sunset**: Surfing at Ocean Beach, Andytown Coffee, Devil's Teeth Baking Company (breakfast sandwiches), Mollusk Surf Shop. Foggy and mellow.

## Secret Spots
- **Seward Street Slides**: Two concrete slides built into a hillside in the Castro/Eureka Valley. Bring a piece of cardboard to sit on. Free, open to public.
- **Wave Organ** (Marina): Acoustic sculpture on a jetty made from demolished cemetery headstones. Waves create sounds through pipes. Best at high tide.
- **Cayuga Park**: Tiny park in the Excelsior with an elaborate, eclectic garden maintained by one dedicated neighbor
""",
        ),
        File(
            path="tips/day-trips.md",
            contents="""# Day Trips from San Francisco

## Sausalito (30 min)
- Charming waterfront town across the Golden Gate Bridge
- **Best approach**: Bike across the Golden Gate Bridge, take the ferry back ($14)
- Houseboats community, art galleries, waterfront restaurants
- **Heath Ceramics**: Factory and showroom

## Muir Woods (45 min)
- Old-growth coastal redwood forest in Marin County
- **Reservation required**: Must book parking or shuttle at nps.gov/muwo ($9 parking + $15/person entry)
- Easy 1-mile loop through the tallest trees; longer trails available
- Go early morning or late afternoon to avoid crowds

## Point Reyes National Seashore (1.5 hours)
- Stunning coastal wilderness on a separate tectonic plate
- Lighthouse, elephant seal viewing (Dec-March), Tule elk preserve
- **Point Reyes Station**: Small town with great food (Bovine Bakery, Cowgirl Creamery)

## Napa Valley / Sonoma (1-1.5 hours)
- World-famous wine country
- **Sonoma**: More casual, less expensive, fewer crowds than Napa
- **Napa**: More upscale, famous wineries (Opus One, Robert Mondavi, Domaine Chandon)
- **Tip**: Designate a driver or use a tour service. DUI enforcement is strict.

## Half Moon Bay (45 min)
- Coastal town south of SF on Highway 1
- **Mavericks**: Legendary big-wave surf spot (competition held in winter)
- Sam's Chowder House: Lobster rolls with ocean views
- Pumpkin festival in October

## Santa Cruz (1.5 hours)
- Beach boardwalk (free admission to boardwalk, pay per ride), surfing, UC Santa Cruz campus in the redwoods
- Highway 1 drive down is scenic but winding
""",
        ),
    ]


# ---------------------------------------------------------------------------
# FastAPI integration
# ---------------------------------------------------------------------------

def create_app(
    index_path: Optional[str] = None,
    auto_load: bool = True,
) -> "FastAPI":
    """
    Create a FastAPI app with /search, /ask, /index, and /status endpoints.

    Args:
        index_path: Path to a saved index file. If provided AND exists, the
                    index is restored from this file instead of re-indexing.
        auto_load: If True and no saved index exists, automatically loads SF data.
    """
    from fastapi import FastAPI, HTTPException, Query
    from pydantic import BaseModel

    app = FastAPI(
        title="SF City Guide Knowledge Base",
        description="Semantic search over San Francisco city guide data, powered by Augment Code Context Engine",
        version="1.0.0",
    )

    # Initialize knowledge base
    kb: Optional[SFKnowledgeBase] = None

    @app.on_event("startup")
    def startup():
        nonlocal kb
        if index_path and os.path.exists(index_path):
            print(f"Restoring index from {index_path}...")
            kb = SFKnowledgeBase.from_saved(index_path)
            print(f"Restored {len(kb.get_indexed_paths())} documents")
        else:
            print("Creating fresh knowledge base...")
            kb = SFKnowledgeBase.create()
            if auto_load:
                print("Indexing SF city guide data...")
                result = kb.load_sf_data()
                print(f"Indexed {len(result['newly_uploaded'])} documents")
                if index_path:
                    kb.export_index(index_path)
                    print(f"Saved index to {index_path}")

    # --- Request/Response models ---

    class SearchResponse(BaseModel):
        query: str
        results: str
        elapsed_ms: float

    class AskResponse(BaseModel):
        query: str
        prompt: Optional[str] = None
        answer: str
        elapsed_ms: float

    class IndexRequest(BaseModel):
        path: str
        contents: str

    class IndexResponse(BaseModel):
        newly_uploaded: list[str]
        already_uploaded: list[str]

    class StatusResponse(BaseModel):
        indexed_documents: int
        document_paths: list[str]

    # --- Endpoints ---

    @app.get("/search", response_model=SearchResponse)
    def search(
        q: str = Query(..., description="Natural language search query"),
        max_length: Optional[int] = Query(None, description="Max result length (default 20000, max 80000)"),
    ):
        """Semantic search over the SF knowledge base."""
        if kb is None:
            raise HTTPException(status_code=503, detail="Knowledge base not initialized")
        result = kb.search(q, max_length=max_length)
        return SearchResponse(
            query=result.query,
            results=result.raw_results,
            elapsed_ms=result.elapsed_ms,
        )

    @app.get("/ask", response_model=AskResponse)
    def ask(
        q: str = Query(..., description="Search query to find relevant documents"),
        prompt: Optional[str] = Query(None, description="Question to answer (defaults to q)"),
    ):
        """RAG: search the knowledge base and get an LLM-generated answer."""
        if kb is None:
            raise HTTPException(status_code=503, detail="Knowledge base not initialized")
        result = kb.ask(q, prompt)
        return AskResponse(
            query=result.query,
            prompt=result.prompt,
            answer=result.answer,
            elapsed_ms=result.elapsed_ms,
        )

    @app.post("/index", response_model=IndexResponse)
    def add_documents(docs: list[IndexRequest]):
        """Add new documents to the knowledge base."""
        if kb is None:
            raise HTTPException(status_code=503, detail="Knowledge base not initialized")
        files = [File(path=d.path, contents=d.contents) for d in docs]
        result = kb.index_documents(files)
        # Auto-save if index_path is configured
        if index_path:
            kb.export_index(index_path)
        return IndexResponse(**result)

    @app.get("/status", response_model=StatusResponse)
    def status():
        """Get the current state of the knowledge base."""
        if kb is None:
            raise HTTPException(status_code=503, detail="Knowledge base not initialized")
        paths = kb.get_indexed_paths()
        return StatusResponse(indexed_documents=len(paths), document_paths=paths)

    return app


# ---------------------------------------------------------------------------
# Standalone entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="SF Knowledge Base Server")
    parser.add_argument("--port", type=int, default=8000, help="Port to run on (default: 8000)")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--index-path", type=str, default="./sf-index.json", help="Path to save/load index state")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload for development")

    # Subcommands for non-server usage
    parser.add_argument("--search", type=str, help="Run a one-off search query and exit")
    parser.add_argument("--ask", type=str, help="Run a one-off RAG query and exit")
    parser.add_argument("--index-only", action="store_true", help="Index all data, export, and exit")

    args = parser.parse_args()

    if args.search or args.ask or args.index_only:
        # Non-server mode
        if os.path.exists(args.index_path):
            print(f"Loading index from {args.index_path}...")
            kb = SFKnowledgeBase.from_saved(args.index_path)
        else:
            print("Creating fresh index...")
            kb = SFKnowledgeBase.create()
            kb.load_sf_data()
            kb.export_index(args.index_path)
            print(f"Index saved to {args.index_path}")

        if args.index_only:
            print(f"Indexed {len(kb.get_indexed_paths())} documents. Done.")
        elif args.search:
            result = kb.search(args.search)
            print(result.raw_results)
        elif args.ask:
            result = kb.ask(args.ask)
            print(result.answer)
    else:
        # Server mode
        import uvicorn
        app = create_app(index_path=args.index_path)
        uvicorn.run(app, host=args.host, port=args.port, reload=args.reload)
