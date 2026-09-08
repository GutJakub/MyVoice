from agents import Agent, Runner

from myvoice.tools.spotify import play_spotify_playlist


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
    ],
)


def run_command(command: str) -> str:
    result = Runner.run_sync(
        assistant,
        command,
    )

    return result.final_output