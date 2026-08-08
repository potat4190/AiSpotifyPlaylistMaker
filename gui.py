"""Tkinter GUI for the AI Spotify Playlist Maker."""

import queue
import threading
import tkinter as tk
from tkinter import scrolledtext

from main import (
    ConfigError,
    add_songs_to_playlist,
    check_config,
    create_spotify_playlist,
    find_real_tracks,
    get_artists_and_genres,
)

PLACEHOLDER = "e.g., 'sad lofi chill', 'energetic workout pop'"


class PlaylistCreatorGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Spotify AI Playlist Creator")
        self.root.geometry("1000x700")
        self.root.configure(bg="#000000")

        self.spotify_green = "#1DB954"
        self.bg_dark = "#000000"
        self.bg_secondary = "#191414"
        self.text_color = "#FFFFFF"

        # Background threads push messages here; the Tk main loop drains it.
        # Touching widgets directly from a worker thread is not safe.
        self.log_queue = queue.Queue()

        self.setup_ui()
        self.root.after(100, self.drain_log_queue)

    # ---------------- UI construction ----------------
    def setup_ui(self):
        header_frame = tk.Frame(self.root, bg=self.spotify_green, height=80)
        header_frame.pack(fill=tk.X)
        header_frame.pack_propagate(False)

        tk.Label(
            header_frame,
            text="AI Playlist Creator",
            font=("Helvetica", 32, "bold"),
            bg=self.spotify_green,
            fg=self.bg_dark,
        ).pack(pady=15)

        input_frame = tk.Frame(self.root, bg=self.bg_secondary, height=150)
        input_frame.pack(fill=tk.X, padx=20, pady=20)
        input_frame.pack_propagate(False)

        left_frame = tk.Frame(input_frame, bg=self.bg_secondary)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10)

        tk.Label(
            left_frame,
            text="Your Vibe",
            font=("Helvetica", 14, "bold"),
            bg=self.bg_secondary,
            fg=self.spotify_green,
        ).pack(anchor=tk.W, pady=(0, 5))

        self.vibe_entry = tk.Entry(
            left_frame,
            font=("Helvetica", 12),
            bg="#282828",
            fg=self.text_color,
            insertbackground=self.spotify_green,
            relief=tk.FLAT,
            bd=0,
        )
        self.vibe_entry.pack(fill=tk.X, ipady=12)
        self.vibe_entry.insert(0, PLACEHOLDER)
        self.vibe_entry.bind("<FocusIn>", self.on_vibe_focus_in)
        self.vibe_entry.bind("<FocusOut>", self.on_vibe_focus_out)
        self.vibe_entry.bind("<Return>", lambda _e: self.on_create_clicked())

        right_frame = tk.Frame(input_frame, bg=self.bg_secondary)
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=10)

        tk.Label(
            right_frame,
            text="Number of Songs",
            font=("Helvetica", 14, "bold"),
            bg=self.bg_secondary,
            fg=self.spotify_green,
        ).pack(anchor=tk.W, pady=(0, 5))

        self.songs_entry = tk.Entry(
            right_frame,
            font=("Helvetica", 12),
            bg="#282828",
            fg=self.text_color,
            insertbackground=self.spotify_green,
            relief=tk.FLAT,
            bd=0,
        )
        self.songs_entry.pack(fill=tk.X, ipady=12)
        self.songs_entry.insert(0, "25")

        button_frame = tk.Frame(self.root, bg=self.bg_dark)
        button_frame.pack(fill=tk.X, padx=20, pady=10)

        self.create_button = tk.Button(
            button_frame,
            text="Create Playlist",
            font=("Helvetica", 14, "bold"),
            bg=self.spotify_green,
            fg=self.bg_dark,
            activebackground="#1ed760",
            activeforeground=self.bg_dark,
            relief=tk.FLAT,
            bd=0,
            padx=20,
            pady=10,
            cursor="hand2",
            command=self.on_create_clicked,
        )
        self.create_button.pack(side=tk.LEFT, padx=5)

        self.loading_label = tk.Label(
            button_frame,
            text="",
            font=("Helvetica", 11),
            bg=self.bg_dark,
            fg=self.spotify_green,
        )
        self.loading_label.pack(side=tk.LEFT, padx=10)

        tk.Label(
            self.root,
            text="Playlist Creation Output",
            font=("Helvetica", 12, "bold"),
            bg=self.bg_dark,
            fg=self.spotify_green,
            anchor=tk.W,
        ).pack(fill=tk.X, padx=20, pady=(10, 5))

        self.output_text = scrolledtext.ScrolledText(
            self.root,
            font=("Courier", 10),
            bg=self.bg_secondary,
            fg=self.text_color,
            insertbackground=self.spotify_green,
            relief=tk.FLAT,
            bd=1,
            wrap=tk.WORD,
        )
        self.output_text.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 20))
        self.output_text.config(state=tk.DISABLED)

    # ---------------- placeholder handling ----------------
    def on_vibe_focus_in(self, _event):
        if self.vibe_entry.get() == PLACEHOLDER:
            self.vibe_entry.delete(0, tk.END)

    def on_vibe_focus_out(self, _event):
        if self.vibe_entry.get() == "":
            self.vibe_entry.insert(0, PLACEHOLDER)

    # ---------------- thread-safe logging ----------------
    def log(self, message):
        """Safe to call from any thread."""
        self.log_queue.put(str(message))

    def drain_log_queue(self):
        """Runs on the Tk main loop; moves queued messages into the widget."""
        try:
            while True:
                message = self.log_queue.get_nowait()
                self.output_text.config(state=tk.NORMAL)
                self.output_text.insert(tk.END, message + "\n")
                self.output_text.see(tk.END)
                self.output_text.config(state=tk.DISABLED)
        except queue.Empty:
            pass
        self.root.after(100, self.drain_log_queue)

    # ---------------- actions ----------------
    def on_create_clicked(self):
        vibe = self.vibe_entry.get().strip()
        if vibe in (PLACEHOLDER, ""):
            self.log("Please enter a vibe first.")
            return

        try:
            check_config()
        except ConfigError as exc:
            self.log(f"Configuration error: {exc}")
            return

        songs_input = self.songs_entry.get().strip()
        total_limit = int(songs_input) if songs_input.isdigit() else 25
        total_limit = max(1, min(total_limit, 100))

        self.output_text.config(state=tk.NORMAL)
        self.output_text.delete("1.0", tk.END)
        self.output_text.config(state=tk.DISABLED)

        self.log("AI Playlist Creator (Gemini 2.5 Flash)")
        self.log(f"Vibe: {vibe}")
        self.log(f"Songs: {total_limit}\n")

        self.create_button.config(state=tk.DISABLED)
        self.loading_label.config(text="Processing...")

        threading.Thread(
            target=self.create_playlist_thread,
            args=(vibe, total_limit),
            daemon=True,
        ).start()

    def create_playlist_thread(self, vibe, total_limit):
        try:
            self.log("Asking Gemini for artists and genres...")
            artists, genres = get_artists_and_genres(vibe)
            if not artists and not genres:
                self.log("Gemini didn't return usable results. Try rephrasing.")
                return

            self.log(f"Artists: {', '.join(artists) or '(none)'}")
            self.log(f"Genres: {', '.join(genres) or '(none)'}")

            tracks = find_real_tracks(artists, genres, total_limit=total_limit)
            if not tracks:
                self.log("No songs found for this vibe.")
                return
            self.log(f"Found {len(tracks)} tracks.")

            playlist_name = f"{vibe.title()} (AI Mix)"
            playlist_id = create_spotify_playlist(playlist_name)
            self.log(f"Created playlist: {playlist_name}")

            added = add_songs_to_playlist(playlist_id, tracks)
            self.log(f"Added {added} songs.")
            self.log(f"Playlist '{playlist_name}' is ready on your Spotify.")

        except Exception as exc:  # surfaced to the user rather than swallowed
            self.log(f"Error: {exc}")
        finally:
            self.root.after(0, lambda: self.create_button.config(state=tk.NORMAL))
            self.root.after(0, lambda: self.loading_label.config(text=""))


if __name__ == "__main__":
    root = tk.Tk()
    PlaylistCreatorGUI(root)
    root.mainloop()