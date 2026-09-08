"""Spotify playback and playlist lookup by tokens, spelling and meaning."""

import os
import time

import numpy as np
import spotipy
from dotenv import load_dotenv
from rapidfuzz import fuzz
from sentence_transformers import SentenceTransformer
from spotipy.oauth2 import SpotifyOAuth


SCOPES = [
    "user-read-playback-state",
    "user-modify-playback-state",
    "playlist-read-private",
    "playlist-read-collaborative",
]
FUZZY_MIN_SCORE = 75.0
FUZZY_MIN_MARGIN = 10.0
PLAYBACK_MIN_SCORE = 70.0

PlaylistScore = tuple[dict | None, float]


def _normalize_name(name: str) -> str:
    return name.lower().replace("playlist", "").strip()


def _find_exact_token_match(
    playlists: list[dict], requested_name: str,
) -> dict | None:
    """Accept a token subset only when it identifies one playlist."""
    requested_tokens = set(_normalize_name(requested_name).split())
    if not requested_tokens:
        return None

    matches = [
        playlist for playlist in playlists
        if requested_tokens.issubset(_normalize_name(playlist["name"]).split())
    ]
    return matches[0] if len(matches) == 1 else None


def _find_top_fuzzy_matches(
    playlists: list[dict], requested_name: str,
) -> tuple[PlaylistScore, PlaylistScore]:
    requested = _normalize_name(requested_name)
    scored = sorted(
        ((playlist, float(fuzz.ratio(requested, _normalize_name(playlist["name"]))))
         for playlist in playlists),
        key=lambda item: item[1],
        reverse=True,
    )
    best = scored[0] if scored else (None, 0.0)
    runner_up = scored[1] if len(scored) > 1 else (None, 0.0)
    return best, runner_up


class SpotifyClient:
    def __init__(self) -> None:
        load_dotenv()
        self.client = spotipy.Spotify(
            auth_manager=SpotifyOAuth(
                client_id=os.environ["SPOTIFY_CLIENT_ID"],
                client_secret=os.environ["SPOTIFY_CLIENT_SECRET"],
                redirect_uri=os.environ["SPOTIFY_REDIRECT_URI"],
                scope=" ".join(SCOPES),
                cache_path=".spotify_cache",
                open_browser=False,
            ),
        )
        self.embedding_model = SentenceTransformer(
            "sentence-transformers/all-MiniLM-L6-v2"
        )

    def get_devices(self) -> list[dict]:
        response = self.client.devices()
        return response.get("devices", [])

    def current_playback(self) -> dict | None:
        return self.client.current_playback()

    def set_shuffle(self, enabled: bool, device_id: str | None = None) -> None:
        self.client.shuffle(enabled, device_id=device_id)

    def find_best_playlist(self, name: str) -> tuple[dict | None, str, float]:
        """Return a playlist, matching method and score on a 0–100 scale.

        Scores are matching heuristics, not calibrated probabilities.
        """
        if not _normalize_name(name):
            return None, "none", 0.0

        playlists = self._get_playlists()
        if not playlists:
            return None, "none", 0.0

        token_match = _find_exact_token_match(playlists, name)
        if token_match is not None:
            return token_match, "token_match", 100.0

        (best, best_score), (_, runner_up_score) = _find_top_fuzzy_matches(playlists, name)
        if (best is not None and best_score >= FUZZY_MIN_SCORE
                and best_score - runner_up_score >= FUZZY_MIN_MARGIN):
            return best, "fuzzy", best_score

        playlist, score = self._find_semantic_match(playlists, name)
        return playlist, "semantic", score

    def play_playlist(self, name: str, shuffle: bool = False) -> str:
        playlist, _, score = self.find_best_playlist(name)
        if playlist is None or score < PLAYBACK_MIN_SCORE:
            return f"Could not confidently find playlist: {name}"

        try:
            device = self._select_device()
        except spotipy.SpotifyException as error:
            return f"Could not list Spotify devices (HTTP {error.http_status})."
        if device is None:
            return "No usable Spotify device found. Open Spotify on LENOVOJAKUB and try again."

        device_id = device["id"]
        device_name = device.get("name") or device_id
        try:
            if not device.get("is_active"):
                self.client.transfer_playback(device_id=device_id, force_play=False)
            self._start_playlist(device_id, playlist["uri"])
        except spotipy.SpotifyException as error:
            return (
                f"Could not start Spotify playback on {device_name} "
                f"(HTTP {error.http_status}). Open Spotify on that device and try again."
            )

        try:
            self.set_shuffle(shuffle, device_id=device_id)
        except spotipy.SpotifyException as error:
            return (
                f"Playing playlist {playlist['name']} on {device_name}, "
                f"but could not set shuffle (HTTP {error.http_status})."
            )
        return (
            f"Playing playlist {playlist['name']} "
            f"with shuffle {'on' if shuffle else 'off'} "
            f"(match score: {score:.0f})."
        )

    def _select_device(self) -> dict | None:
        devices = [
            device for device in self.get_devices()
            if device.get("id") and not device.get("is_restricted")
        ]
        return max(
            devices,
            key=lambda device: (
                (device.get("name") or "").casefold() == "lenovojakub",
                bool(device.get("is_active")),
            ),
            default=None,
        )

    def _start_playlist(self, device_id: str, context_uri: str) -> None:
        """Retry a not-ready player twice, without delaying successful requests."""
        for attempt in range(3):
            try:
                self.client.start_playback(device_id=device_id, context_uri=context_uri)
                return
            except spotipy.SpotifyException as error:
                if error.http_status != 404 or attempt == 2:
                    raise
                time.sleep(0.25 * (attempt + 1))

    def _get_playlists(self) -> list[dict]:
        """Fetch each page once for a playlist lookup."""
        playlists = []
        page = self.client.current_user_playlists(limit=50)
        while page:
            playlists.extend(page["items"])
            page = self.client.next(page) if page["next"] else None
        return playlists

    def _find_semantic_match(
        self, playlists: list[dict], requested_name: str,
    ) -> PlaylistScore:
        if not playlists:
            return None, 0.0

        texts = [requested_name, *(playlist["name"] for playlist in playlists)]
        embeddings = self.embedding_model.encode(texts, normalize_embeddings=True)
        similarities = embeddings[1:] @ embeddings[0]
        best_index = int(np.argmax(similarities))
        score = float(np.clip(similarities[best_index], 0.0, 1.0)) * 100.0
        return playlists[best_index], score
