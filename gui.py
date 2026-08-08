"""Tkinter GUI for the AI Spotify Playlist Maker."""

import queue
import threading
import tkinter as tk
from tkinter import font as tkfont
from tkinter import scrolledtext, ttk

from main import (
    ConfigError,
    add_songs_to_playlist,
    check_config,
    create_spotify_playlist,
    find_real_tracks,
    get_artists_and_genres,
)

PLACEHOLDER = "e.g., 'sad lofi chill', 'energetic workout pop'"

# Palette: Spotify-style dark mode (OLED-friendly), single accent, semantic roles.
BG = "#0B0B0F"
SURFACE = "#161318"
SURFACE_ALT = "#1E1B23"
BORDER = "#2A2730"
TEXT_PRIMARY = "#F5F5F7"
TEXT_MUTED = "#9C99A3"
ACCENT = "#1DB954"
ACCENT_HOVER = "#22D65F"
ACCENT_PRESSED = "#17A94A"
ACCENT_ON = "#0B0B0F"
DANGER = "#F0483E"

SPACE_XS = 4
SPACE_SM = 8
SPACE_MD = 16
SPACE_LG = 24
SPACE_XL = 32


class PlaylistCreatorGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("AI Playlist Creator")
        self.root.geometry("1040x720")
        self.root.minsize(760, 560)
        self.root.configure(bg=BG)

        self._load_fonts()
        self._build_styles()

        # Background threads push messages here; the Tk main loop drains it.
        # Touching widgets directly from a worker thread is not safe.
        self.log_queue = queue.Queue()
        self.is_processing = False

        self.setup_ui()
        self.root.after(80, self.drain_log_queue)

    # ---------------- fonts & ttk styling ----------------
    def _load_fonts(self):
        available = set(tkfont.families())
        heading_candidates = ["Poppins SemiBold", "Poppins", "Segoe UI Semibold", "Segoe UI"]
        body_candidates = ["Segoe UI", "Helvetica", "Arial"]
        mono_candidates = ["Cascadia Mono", "Consolas", "Courier New"]

        def pick(candidates, fallback):
            for name in candidates:
                if name in available:
                    return name
            return fallback

        self.font_heading = pick(heading_candidates, "TkDefaultFont")
        self.font_body = pick(body_candidates, "TkDefaultFont")
        self.font_mono = pick(mono_candidates, "TkFixedFont")

    def _build_styles(self):
        style = ttk.Style(self.root)
        style.theme_use("clam")

        style.configure(
            "Accent.TButton",
            background=ACCENT,
            foreground=ACCENT_ON,
            borderwidth=0,
            focusthickness=0,
            padding=(SPACE_LG, SPACE_SM + 2),
            font=(self.font_heading, 12, "bold"),
        )
        style.map(
            "Accent.TButton",
            background=[("disabled", "#3A3A40"), ("pressed", ACCENT_PRESSED), ("active", ACCENT_HOVER)],
            foreground=[("disabled", "#7A7A80")],
        )

        style.configure(
            "Vibe.TEntry",
            fieldbackground=SURFACE_ALT,
            foreground=TEXT_PRIMARY,
            insertcolor=ACCENT,
            borderwidth=0,
            padding=(SPACE_MD, SPACE_SM + 2),
        )
        style.map("Vibe.TEntry", fieldbackground=[("focus", "#252129")])

        style.configure(
            "App.Horizontal.TProgressbar",
            troughcolor=SURFACE_ALT,
            background=ACCENT,
            bordercolor=SURFACE_ALT,
            lightcolor=ACCENT,
            darkcolor=ACCENT,
            thickness=6,
        )

        style.configure("App.Vertical.TScrollbar", background=SURFACE_ALT, troughcolor=SURFACE, bordercolor=SURFACE, arrowcolor=TEXT_MUTED)

    # ---------------- UI construction ----------------
    def setup_ui(self):
        # ---- Header ----
        header = tk.Frame(self.root, bg=BG)
        header.pack(fill=tk.X, padx=SPACE_XL, pady=(SPACE_XL, SPACE_LG))

        badge = tk.Frame(header, bg=ACCENT, width=10, height=32)
        badge.pack(side=tk.LEFT, padx=(0, SPACE_MD))
        badge.pack_propagate(False)

        title_box = tk.Frame(header, bg=BG)
        title_box.pack(side=tk.LEFT, fill=tk.X, expand=True)

        tk.Label(
            title_box,
            text="AI Playlist Creator",
            font=(self.font_heading, 24, "bold"),
            bg=BG,
            fg=TEXT_PRIMARY,
            anchor=tk.W,
        ).pack(anchor=tk.W)

        tk.Label(
            title_box,
            text="Describe a vibe, get a Spotify playlist built by Gemini.",
            font=(self.font_body, 11),
            bg=BG,
            fg=TEXT_MUTED,
            anchor=tk.W,
        ).pack(anchor=tk.W, pady=(2, 0))

        self.status_dot = tk.Canvas(header, width=10, height=10, bg=BG, highlightthickness=0)
        self.status_dot.pack(side=tk.RIGHT, padx=(SPACE_SM, 0))
        self._draw_status_dot(TEXT_MUTED)

        self.status_label = tk.Label(
            header, text="Idle", font=(self.font_body, 10), bg=BG, fg=TEXT_MUTED
        )
        self.status_label.pack(side=tk.RIGHT)

        # ---- Input card ----
        card = tk.Frame(self.root, bg=SURFACE, highlightbackground=BORDER, highlightthickness=1)
        card.pack(fill=tk.X, padx=SPACE_XL, pady=(0, SPACE_LG))

        card_inner = tk.Frame(card, bg=SURFACE)
        card_inner.pack(fill=tk.X, padx=SPACE_LG, pady=SPACE_LG)
        card_inner.columnconfigure(0, weight=3)
        card_inner.columnconfigure(1, weight=1)

        # Vibe field
        vibe_col = tk.Frame(card_inner, bg=SURFACE)
        vibe_col.grid(row=0, column=0, sticky="ew", padx=(0, SPACE_MD))

        tk.Label(
            vibe_col,
            text="YOUR VIBE",
            font=(self.font_body, 10, "bold"),
            bg=SURFACE,
            fg=ACCENT,
        ).pack(anchor=tk.W, pady=(0, SPACE_SM))

        self.vibe_entry = ttk.Entry(vibe_col, style="Vibe.TEntry", font=(self.font_body, 12))
        self.vibe_entry.pack(fill=tk.X, ipady=4)
        self.vibe_entry.insert(0, PLACEHOLDER)
        self.vibe_entry.configure(foreground=TEXT_MUTED)
        self.vibe_entry.bind("<FocusIn>", self.on_vibe_focus_in)
        self.vibe_entry.bind("<FocusOut>", self.on_vibe_focus_out)
        self.vibe_entry.bind("<Return>", lambda _e: self.on_create_clicked())

        # Song count field
        songs_col = tk.Frame(card_inner, bg=SURFACE)
        songs_col.grid(row=0, column=1, sticky="ew")

        tk.Label(
            songs_col,
            text="SONGS (1-100)",
            font=(self.font_body, 10, "bold"),
            bg=SURFACE,
            fg=ACCENT,
        ).pack(anchor=tk.W, pady=(0, SPACE_SM))

        self.songs_entry = ttk.Entry(songs_col, style="Vibe.TEntry", font=(self.font_body, 12))
        self.songs_entry.pack(fill=tk.X, ipady=4)
        self.songs_entry.insert(0, "25")

        # ---- Action row ----
        action_row = tk.Frame(self.root, bg=BG)
        action_row.pack(fill=tk.X, padx=SPACE_XL, pady=(0, SPACE_SM))

        self.create_button = ttk.Button(
            action_row,
            text="Create Playlist",
            style="Accent.TButton",
            cursor="hand2",
            command=self.on_create_clicked,
        )
        self.create_button.pack(side=tk.LEFT)

        self.progress = ttk.Progressbar(
            action_row,
            style="App.Horizontal.TProgressbar",
            mode="indeterminate",
            length=200,
        )

        # ---- Output section ----
        output_header = tk.Frame(self.root, bg=BG)
        output_header.pack(fill=tk.X, padx=SPACE_XL, pady=(SPACE_MD, SPACE_SM))

        tk.Label(
            output_header,
            text="OUTPUT LOG",
            font=(self.font_body, 10, "bold"),
            bg=BG,
            fg=TEXT_MUTED,
        ).pack(side=tk.LEFT)

        output_card = tk.Frame(self.root, bg=SURFACE, highlightbackground=BORDER, highlightthickness=1)
        output_card.pack(fill=tk.BOTH, expand=True, padx=SPACE_XL, pady=(0, SPACE_XL))

        self.output_text = scrolledtext.ScrolledText(
            output_card,
            font=(self.font_mono, 10),
            bg=SURFACE,
            fg=TEXT_PRIMARY,
            insertbackground=ACCENT,
            relief=tk.FLAT,
            bd=0,
            wrap=tk.WORD,
            padx=SPACE_MD,
            pady=SPACE_MD,
        )
        self.output_text.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)
        self.output_text.tag_configure("error", foreground=DANGER)
        self.output_text.tag_configure("success", foreground=ACCENT)
        self.output_text.tag_configure("muted", foreground=TEXT_MUTED)
        self.output_text.config(state=tk.DISABLED)

        self._show_empty_state()

    def _draw_status_dot(self, color):
        self.status_dot.delete("all")
        self.status_dot.create_oval(1, 1, 9, 9, fill=color, outline="")

    def _show_empty_state(self):
        self.output_text.config(state=tk.NORMAL)
        self.output_text.insert(
            tk.END,
            "No output yet. Enter a vibe above and click Create Playlist to begin.\n",
            "muted",
        )
        self.output_text.config(state=tk.DISABLED)

    # ---------------- placeholder handling ----------------
    def on_vibe_focus_in(self, _event):
        if self.vibe_entry.get() == PLACEHOLDER:
            self.vibe_entry.delete(0, tk.END)
            self.vibe_entry.configure(foreground=TEXT_PRIMARY)

    def on_vibe_focus_out(self, _event):
        if self.vibe_entry.get() == "":
            self.vibe_entry.insert(0, PLACEHOLDER)
            self.vibe_entry.configure(foreground=TEXT_MUTED)

    # ---------------- thread-safe logging ----------------
    def log(self, message, tag=None):
        """Safe to call from any thread."""
        self.log_queue.put((str(message), tag))

    def drain_log_queue(self):
        """Runs on the Tk main loop; moves queued messages into the widget."""
        try:
            while True:
                message, tag = self.log_queue.get_nowait()
                self.output_text.config(state=tk.NORMAL)
                if tag:
                    self.output_text.insert(tk.END, message + "\n", tag)
                else:
                    self.output_text.insert(tk.END, message + "\n")
                self.output_text.see(tk.END)
                self.output_text.config(state=tk.DISABLED)
        except queue.Empty:
            pass
        self.root.after(80, self.drain_log_queue)

    # ---------------- actions ----------------
    def on_create_clicked(self):
        if self.is_processing:
            return

        vibe = self.vibe_entry.get().strip()
        if vibe in (PLACEHOLDER, ""):
            self.log("Please enter a vibe first.", "error")
            return

        try:
            check_config()
        except ConfigError as exc:
            self.log(f"Configuration error: {exc}", "error")
            return

        songs_input = self.songs_entry.get().strip()
        total_limit = int(songs_input) if songs_input.isdigit() else 25
        total_limit = max(1, min(total_limit, 100))

        self.output_text.config(state=tk.NORMAL)
        self.output_text.delete("1.0", tk.END)
        self.output_text.config(state=tk.DISABLED)

        self.log("AI Playlist Creator (Gemini 2.5 Flash)", "muted")
        self.log(f"Vibe: {vibe}")
        self.log(f"Songs: {total_limit}\n")

        self.is_processing = True
        self.create_button.config(state=tk.DISABLED)
        self.progress.pack(side=tk.LEFT, padx=(SPACE_MD, 0), fill=tk.X, expand=False)
        self.progress.start(12)
        self._draw_status_dot(ACCENT)
        self.status_label.config(text="Processing...", fg=ACCENT)

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
                self.log("Gemini didn't return usable results. Try rephrasing.", "error")
                return

            self.log(f"Artists: {', '.join(artists) or '(none)'}")
            self.log(f"Genres: {', '.join(genres) or '(none)'}")

            tracks, premium_required = find_real_tracks(
                artists, genres, total_limit=total_limit, log=self.log
            )
            if not tracks:
                if not premium_required:
                    self.log("No songs found for this vibe.", "error")
                return
            self.log(f"Found {len(tracks)} tracks.")

            playlist_name = f"{vibe.title()} (AI Mix)"
            playlist_id = create_spotify_playlist(playlist_name)
            self.log(f"Created playlist: {playlist_name}")

            added = add_songs_to_playlist(playlist_id, tracks)
            self.log(f"Added {added} songs.")
            self.log(f"Playlist '{playlist_name}' is ready on your Spotify.", "success")

        except Exception as exc:  # surfaced to the user rather than swallowed
            self.log(f"Error: {exc}", "error")
        finally:
            self.root.after(0, self._reset_after_run)

    def _reset_after_run(self):
        self.is_processing = False
        self.create_button.config(state=tk.NORMAL)
        self.progress.stop()
        self.progress.pack_forget()
        self._draw_status_dot(TEXT_MUTED)
        self.status_label.config(text="Idle", fg=TEXT_MUTED)


if __name__ == "__main__":
    root = tk.Tk()
    PlaylistCreatorGUI(root)
    root.mainloop()
