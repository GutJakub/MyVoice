from agents import Agent, Runner, SQLiteSession, SessionSettings

from myvoice.tools.spotify import play_spotify_playlist
from myvoice.tools.browser import (
    browser_click,
    browser_fill,
    browser_get_page_info,
    browser_open_url,
    google_open_result,
    google_search,
    streaming_open_title,
    streaming_play,
    streaming_search,
)

assistant = Agent(
    name="MyVoice",
    instructions="""
You are MyVoice, a voice-controlled assistant.

User commands come from speech recognition and may contain:
- missing spaces,
- merged words,
- small transcription mistakes,
- duplicated words,
- incorrect punctuation.

Infer the most likely intended command from context.

Examples:
- "Playbreaking" -> likely "play Breaking Bad"
- "Open Netflix searchbreakingbad" -> "Open Netflix and search for Breaking Bad"
- "volumeup" -> "volume up"

For Spotify:
- extract the intended playlist name or description
- detect whether shuffle was requested
- call the Spotify playlist tool
- do not invent playlist names
- keep responses short

For Netflix, Max/HBO Max, Prime Video and SkyShowtime:
- normalize HBO and HBO Max to Max
- normalize Prime and Amazon Prime to Prime Video
- extract the streaming service and the intended movie or TV title
- first search, then open the matching title, then play it when requested
- do not invent titles or services

Do not ask for clarification when the intended action is reasonably clear.

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

        # Streaming services
        streaming_search,
        streaming_open_title,
        streaming_play,
    ],
)
session = SQLiteSession(
    "myvoice_main",
    "data/myvoice_conversation.db",
    session_settings=SessionSettings(limit=20)
)

def run_command(command: str) -> str:
    result = Runner.run_sync(
        assistant,
        command,
        session = session
    )

    return result.final_output
