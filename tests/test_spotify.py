import unittest
from unittest.mock import Mock

import numpy as np

from myvoice.integrations.spotify import (
    SpotifyClient,
    _find_exact_token_match,
    _find_top_fuzzy_matches,
)


from myvoice.integrations.spotify import SpotifyClient

def get_devices(self) -> list[dict]:
    response = self.client.devices()
    return response.get("devices", [])

def main() -> None:
    spotify = SpotifyClient()

    devices = spotify.get_devices()

    for device in devices:
        print(
            device["name"],
            "| id:", device["id"],
            "| active:", device["is_active"],
            "| restricted:", device["is_restricted"],
            "| type:", device["type"],
        )


if __name__ == "__main__":
    main()
