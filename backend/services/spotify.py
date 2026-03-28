"""
Spotify mood-to-playlist mapping and embed URL generation.

Uses Spotify iframe embeds (zero auth needed).
Maps journey segment moods to curated Spotify playlists.
"""

# Curated playlist IDs for different journey moods
MOOD_PLAYLISTS = {
    # Calm / departure vibes
    "departure": {
        "playlist_id": "37i9dQZF1DX4sWSpwq3LiO",  # Peaceful Piano
        "name": "Peaceful Piano",
        "mood": "calm, reflective departure",
    },
    # Urban commute / transit ride
    "transit_urban": {
        "playlist_id": "37i9dQZF1DX4OzrY981I1W",  # Lo-Fi Beats
        "name": "Lo-Fi Beats",
        "mood": "chill urban commute",
    },
    # Walking / exploration
    "walking": {
        "playlist_id": "37i9dQZF1DWZjqjZMudx9T",  # Walk Like A Badass
        "name": "Walk Like A Badass",
        "mood": "confident walking energy",
    },
    # Anticipation / building excitement
    "anticipation": {
        "playlist_id": "37i9dQZF1DX3rxVfibe1L0",  # Mood Booster
        "name": "Mood Booster",
        "mood": "building excitement, anticipation",
    },
    # Arrival / destination energy
    "arrival": {
        "playlist_id": "37i9dQZF1DXdPec7aLTmlC",  # Happy Hits
        "name": "Happy Hits",
        "mood": "celebratory arrival energy",
    },
    # Scenic / nature
    "scenic": {
        "playlist_id": "37i9dQZF1DX4PP3DA4J0N8",  # Nature Sounds
        "name": "Nature Sounds",
        "mood": "peaceful nature, scenic views",
    },
    # Night / evening vibes
    "evening": {
        "playlist_id": "37i9dQZF1DX2pSTOxoPbx9",  # Late Night Vibes
        "name": "Late Night Vibes",
        "mood": "evening atmosphere",
    },
    # Energetic / exploration
    "explore": {
        "playlist_id": "37i9dQZF1DX0BcQWzuB7ZO",  # Dance Hits
        "name": "Dance Hits",
        "mood": "energetic exploration",
    },
    # Coffee shop / cafe
    "cafe": {
        "playlist_id": "37i9dQZF1DX6VdMW310YC7",  # Chill Tracks
        "name": "Chill Tracks",
        "mood": "cafe, relaxed hanging out",
    },
    # Cultural / historic
    "cultural": {
        "playlist_id": "37i9dQZF1DWWEJlAGA9gs0",  # Classical Essentials
        "name": "Classical Essentials",
        "mood": "cultural, historic appreciation",
    },
}


def get_embed_url(playlist_id: str, theme: int = 0) -> str:
    """Get Spotify embed iframe URL. theme=0 for dark, theme=1 for light."""
    return f"https://open.spotify.com/embed/playlist/{playlist_id}?utm_source=generator&theme={theme}"


def get_track_embed_url(track_id: str, theme: int = 0) -> str:
    """Get Spotify embed URL for a single track."""
    return f"https://open.spotify.com/embed/track/{track_id}?utm_source=generator&theme={theme}"


def select_mood_for_segment(segment_type: str, segment_index: int, total_segments: int, is_evening: bool = False) -> dict:
    """
    Select the best mood/playlist for a journey segment.

    Args:
        segment_type: "walking", "transit", "arrival", "departure", "explore"
        segment_index: position in the journey (0-based)
        total_segments: total number of segments
        is_evening: whether the journey is happening in the evening
    """
    if segment_index == 0:
        mood_key = "departure"
    elif segment_index == total_segments - 1:
        mood_key = "arrival"
    elif segment_type == "WALKING":
        mood_key = "walking"
    elif segment_type == "TRANSIT":
        # Build anticipation as we get closer to destination
        if segment_index >= total_segments - 2:
            mood_key = "anticipation"
        else:
            mood_key = "transit_urban"
    else:
        mood_key = "explore"

    if is_evening:
        mood_key = "evening"

    playlist = MOOD_PLAYLISTS.get(mood_key, MOOD_PLAYLISTS["explore"])
    return {
        "mood_key": mood_key,
        "playlist_id": playlist["playlist_id"],
        "playlist_name": playlist["name"],
        "mood_description": playlist["mood"],
        "embed_url": get_embed_url(playlist["playlist_id"]),
    }


def get_destination_playlist(destination_type: str) -> dict:
    """Get a playlist appropriate for the destination."""
    type_mapping = {
        "park": "scenic",
        "nature": "scenic",
        "beach": "scenic",
        "museum": "cultural",
        "historic": "cultural",
        "restaurant": "cafe",
        "cafe": "cafe",
        "bar": "evening",
        "viewpoint": "scenic",
        "landmark": "anticipation",
    }
    mood_key = type_mapping.get(destination_type, "explore")
    playlist = MOOD_PLAYLISTS[mood_key]
    return {
        "mood_key": mood_key,
        "playlist_id": playlist["playlist_id"],
        "playlist_name": playlist["name"],
        "mood_description": playlist["mood"],
        "embed_url": get_embed_url(playlist["playlist_id"]),
    }
