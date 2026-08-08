"""AI Spotify Playlist Maker — CLI entry point.

Uses Gemini to suggest real artists/genres for a theme, searches Spotify for
matching tracks, and creates a private playlist in the user's account.
"""

import os
import re
import sys

import spotipy
from spotipy.oauth2 import SpotifyOAuth
from google import genai
from dotenv import load_dotenv

load_dotenv()

GEMINI_MODEL = "gemini-2.5-flash"
SPOTIFY_SCOPE = "playlist-modify-private"

REQUIRED_ENV = [
    "SPOTIPY_CLIENT_ID",
    "SPOTIPY_CLIENT_SECRET",
    "SPOTIPY_REDIRECT_URI",
    "GEMINI_API_KEY",
]


class ConfigError(RuntimeError):
    """Raised when required credentials are missing."""


def check_config():
    """Fail fast with a readable message if any credential is missing."""
    missing = [k for k in REQUIRED_ENV if not os.getenv(k)]
    if missing:
        raise ConfigError(
            "Missing environment variables: "
            + ", ".join(missing)
            + "\nCopy .env.example to .env and fill in your keys. See README.md."
        )


# ----------------------------------------------------------
# Clients are created lazily so that importing this module
# never triggers a browser OAuth flow or a network call.
# ----------------------------------------------------------
_sp_client = None
_gemini_client = None


def get_spotify():
    global _sp_client
    if _sp_client is None:
        check_config()
        _sp_client = spotipy.Spotify(
            auth_manager=SpotifyOAuth(
                client_id=os.getenv("SPOTIPY_CLIENT_ID"),
                client_secret=os.getenv("SPOTIPY_CLIENT_SECRET"),
                redirect_uri=os.getenv("SPOTIPY_REDIRECT_URI"),
                scope=SPOTIFY_SCOPE,
                cache_path=os.getenv("SPOTIPY_CACHE_PATH", ".spotify_token_cache"),
            )
        )
    return _sp_client


def get_gemini():
    global _gemini_client
    if _gemini_client is None:
        check_config()
        _gemini_client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
    return _gemini_client


# ----------------------------------------------------------
# STEP 1 — Ask Gemini for real artists + genres
# ----------------------------------------------------------
def get_artists_and_genres(prompt: str):
    print("Searching for real artists and genres related to your vibe...")

    client = get_gemini()
    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=(
            f"List 5 popular real artists and 3 real genres that match the vibe "
            f"'{prompt}'. Only include artists and genres that exist on Spotify. "
            f"Format strictly as:\n"
            f"Artists: name1, name2, ...\nGenres: genre1, genre2, ..."
        ),
    )
    text = (response.text or "").strip()
    if not text:
        return [], []

    print(f"\nGemini's suggestions:\n{text}\n")

    artist_match = re.search(r"Artists:\s*(.*)", text)
    genre_match = re.search(r"Genres:\s*(.*)", text)

    artists = (
        [a.strip() for a in artist_match.group(1).split(",") if a.strip()]
        if artist_match
        else []
    )
    genres = (
        [g.strip() for g in genre_match.group(1).split(",") if g.strip()]
        if genre_match
        else []
    )

    return artists, genres


# ----------------------------------------------------------
# STEP 2 — Create a Spotify playlist
# ----------------------------------------------------------
def create_spotify_playlist(title: str) -> str:
    sp = get_spotify()
    user_id = sp.current_user()["id"]
    playlist = sp.user_playlist_create(user=user_id, name=title, public=False)
    print(f"Created playlist: {title}")
    return playlist["id"]


# ----------------------------------------------------------
# STEP 3 — Search real tracks by artist + genre
#
# Returns track URIs directly, so we never have to re-search
# by "Artist - Title" string (which loses matches).
# ----------------------------------------------------------
def find_real_tracks(artists, genres, total_limit: int = 25):
    print("Searching Spotify for real tracks...")
    sp = get_spotify()
    tracks = []
    seen = set()

    def collect(query, limit):
        try:
            results = sp.search(q=query, type="track", limit=limit, market="US")
        except spotipy.SpotifyException as exc:
            print(f"  (skipped '{query}': {exc.msg})")
            return
        for item in results["tracks"]["items"]:
            uri = item["uri"]
            if uri in seen:
                continue
            seen.add(uri)
            tracks.append(
                {"uri": uri, "label": f"{item['artists'][0]['name']} - {item['name']}"}
            )

    # Per-artist top results
    per_artist = max(1, total_limit // max(len(artists), 1))
    for artist in artists:
        if len(tracks) >= total_limit:
            break
        collect(f'artist:"{artist}"', min(per_artist + 2, 50))

    # Fill remaining slots with genre searches.
    # Spotify's `genre:` filter only applies to artist/album searches, so we
    # use the genre as a plain keyword for track search instead.
    for genre in genres:
        if len(tracks) >= total_limit:
            break
        collect(genre, 20)

    tracks = tracks[:total_limit]
    print(f"Found {len(tracks)} tracks.")
    return tracks


# ----------------------------------------------------------
# STEP 4 — Add songs to the playlist (batched, 100 per request)
# ----------------------------------------------------------
def add_songs_to_playlist(playlist_id: str, tracks) -> int:
    print("\nAdding songs to your Spotify playlist...")
    sp = get_spotify()
    uris = [t["uri"] if isinstance(t, dict) else t for t in tracks]

    added = 0
    for i in range(0, len(uris), 100):
        batch = uris[i : i + 100]
        try:
            sp.playlist_add_items(playlist_id, batch)
            added += len(batch)
        except spotipy.SpotifyException as exc:
            print(f"  Failed to add a batch of {len(batch)}: {exc.msg}")

    for t in tracks[:added]:
        print(f"  Added: {t['label'] if isinstance(t, dict) else t}")

    print(f"\nDone. Added {added} songs.\n")
    return added


# ----------------------------------------------------------
# MAIN PROGRAM
# ----------------------------------------------------------
def main():
    print("AI Playlist Creator (Gemini 2.5 Flash)")

    try:
        check_config()
    except ConfigError as exc:
        print(f"\nConfiguration error:\n{exc}\n")
        sys.exit(1)

    theme = input(
        "Describe your vibe (e.g. 'classical remixes', 'sad lofi chill'): "
    ).strip()
    if not theme:
        print("No vibe given. Exiting.")
        return

    num_songs_input = input("How many songs? (default 25): ").strip()
    total_limit = int(num_songs_input) if num_songs_input.isdigit() else 25
    total_limit = max(1, min(total_limit, 100))

    artists, genres = get_artists_and_genres(theme)
    if not artists and not genres:
        print("Gemini didn't return usable results. Try rephrasing your vibe.")
        return

    tracks = find_real_tracks(artists, genres, total_limit=total_limit)
    if not tracks:
        print("No songs found for this vibe.")
        return

    playlist_name = f"{theme.title()} (AI Mix)"
    playlist_id = create_spotify_playlist(playlist_name)
    add_songs_to_playlist(playlist_id, tracks)

    print(f"Playlist '{playlist_name}' is ready on your Spotify.")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--gui":
        import tkinter as tk

        from gui import PlaylistCreatorGUI

        root = tk.Tk()
        PlaylistCreatorGUI(root)
        root.mainloop()
    else:
        main()