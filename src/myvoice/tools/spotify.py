from agents import function_tool

from myvoice.integrations.spotify import SpotifyClient


spotify = SpotifyClient()


@function_tool
def play_spotify_playlist(
    playlist_name: str,
    shuffle: bool = False,
) -> str:
    """
    Play a Spotify playlist by name.

    Args:
        playlist_name: Name of the Spotify playlist to play.
        shuffle: Whether shuffle mode should be enabled.
    """

    result = spotify.play_playlist(
        name=playlist_name,
        shuffle=shuffle,
    )

    return result