# AI Spotify Playlist Maker

Describe a vibe — "sad lofi chill", "energetic workout pop", "classical remixes" —
and this app asks Google Gemini for matching artists and genres, finds real tracks
on Spotify, and creates a private playlist in your account.

Available as a terminal app (`main.py`) or a desktop GUI (`gui.py`).

---

## Requirements

- Python 3.9+
- A Spotify account (Free does not work; Premium required)
- A Spotify developer app
- A Google Gemini API key

---

## Setup

### 1. Clone and install

```bash
git clone https://github.com/potat4190/AI_SpotifyPlaylistMaker.git
cd AI_SpotifyPlaylistMaker

python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

pip install -r requirements.txt
```

### 2. Create a Spotify app

1. Go to the [Spotify Developer Dashboard](https://developer.spotify.com/dashboard)
   and click **Create app**.
2. Give it any name and description.
3. Under **Redirect URIs**, add exactly:

   ```
   http://127.0.0.1:8888/callback
   ```

   (Spotify no longer accepts `localhost` — use the IP form.)
4. Check **Web API** under "Which API/SDKs are you planning to use?"
5. Save, then open **Settings** to copy your **Client ID** and **Client Secret**.

### 3. Get a Gemini API key

Create one at [Google AI Studio](https://aistudio.google.com/app/apikey).

### 4. Configure your environment

```bash
cp .env.example .env
```

Fill in `.env`:

```
SPOTIPY_CLIENT_ID=your_client_id
SPOTIPY_CLIENT_SECRET=your_client_secret
SPOTIPY_REDIRECT_URI=http://127.0.0.1:8888/callback
GEMINI_API_KEY=your_gemini_key
```

`.env` is gitignored. **Never commit it.**

---

## Usage

Terminal:

```bash
python main.py
```

GUI:

```bash
python gui.py
```

On first run, a browser window opens asking you to authorize the app. After you
approve, a token is cached locally in `.spotify_token_cache` so you won't be
asked again. That file is gitignored — it contains a refresh token that grants
access to your account, so treat it like a password.

---

## How it works

1. **Gemini** is prompted for 5 real artists and 3 real genres matching your theme.
2. **Spotify Search** pulls top tracks for each artist, then fills remaining slots
   using the genres as keywords.
3. A **private playlist** is created in your account and the track URIs are added
   in batches of 100.

Only the `playlist-modify-private` scope is requested — the app cannot read your
listening history, follow anyone, or control playback.

---

## Notes and limitations

- **Development mode.** A new Spotify app is limited to 25 users, each of whom you
  must add manually under *Settings → User Management*. Anyone else gets a 403.
  Public availability requires a [quota extension request](https://developer.spotify.com/documentation/web-api/concepts/quota-modes).
- **Genre matching is approximate.** Spotify's `genre:` search filter only applies
  to artist and album searches, not tracks, so genres are used as plain keywords.
- **Gemini can hallucinate.** Suggested artists occasionally don't exist on
  Spotify; those searches return nothing and are skipped silently.

---

## Troubleshooting

| Problem | Fix |
| --- | --- |
| `Missing environment variables` | You haven't created `.env`, or a key is blank. |
| `INVALID_CLIENT: Invalid redirect URI` | The URI in `.env` must match the dashboard **character for character**. |
| Browser opens but never redirects | Make sure nothing else is using port 8888. |
| Stuck logged in as the wrong account | Delete `.spotify_token_cache` and rerun. |
| `429 Too Many Requests` | Spotify rate limit — wait a few minutes. |

---

## License

MIT