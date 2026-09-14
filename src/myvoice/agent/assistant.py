from agents import Agent, Runner

from myvoice.tools.spotify import play_spotify_playlist
from myvoice.tools.browser import (
    browser_click,
    browser_fill,
    browser_get_page_info,
    browser_open_url,
    google_open_result,
    google_search,
    netflix_open_title,
    netflix_play,
    netflix_search,
)

assistant = Agent(
    name="MyVoice",
    instructions="""
You are MyVoice, a desktop voice assistant.

Interpret short spoken commands and use the available tools.

For Spotify:
- extract the intended playlist name or description
- detect whether shuffle was requested
- call the Spotify playlist tool
- do not invent playlist names
- keep responses short
""",
    tools=[
        play_spotify_playlist,
        # Browser
        browser_open_url,
        browser_get_page_info,
        browser_click,
        browser_fill,

        # Google
        google_search,
        google_open_result,

        # Netflix
        netflix_search,
        netflix_open_title,
        netflix_play,
    ],
)


def run_command(command: str) -> str:
    result = Runner.run_sync(
        assistant,
        command,
    )

    return result.final_output